"""
Phase 8: Compliance Decision, Risk, and Explainability Layer Tests

Tests for decision aggregation, risk classification, explainability,
human review queue, and final compliance report generation.
"""

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.compliance.models import (
    DocumentEvidence,
    FindingStatus,
    Requirement,
    RequirementAssessment,
    Severity,
)
from app.compliance.phase8_service import (
    _classify_risk,
    _derive_overall_status,
    create_and_persist_explanations,
    generate_compliance_decision_report,
    get_compliance_decision_report,
    get_requirement_explanation,
)
from app.compliance.phase8_models import (
    OverallComplianceStatus,
    RiskLevel,
)
from app.compliance.service import evaluate_requirements_for_document
from app.documents.models import DocumentRecord, Page, PageBlock
from app.documents.service import save_json
from app.main import app
from app.regulatory.service import create_document, create_provision, create_source
from app.retrieval.service import RetrievalService, get_retrieval_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def phase8_environment(tmp_path, monkeypatch):
    """Set up isolated storage for Phase 8 tests."""
    import app.compliance.service as compliance_service
    import app.compliance.phase8_service as phase8_service
    import app.documents.service as document_service
    import app.regulatory.service as regulatory_service
    import app.retrieval.service as retrieval_service

    storage_root = str(tmp_path / "storage")
    monkeypatch.setattr(document_service, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(compliance_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance"))
    monkeypatch.setattr(phase8_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance", "phase8"))
    monkeypatch.setattr(regulatory_service, "STORAGE_ROOT", os.path.join(storage_root, "regulatory"))
    regulatory_service.ensure_directories()

    retrieval = RetrievalService(vector_store=__import__("app.retrieval.vector_store", fromlist=["LocalVectorStore"]).LocalVectorStore(os.path.join(storage_root, "retrieval")))
    retrieval_service.set_retrieval_service(retrieval)
    yield
    retrieval_service.set_retrieval_service(None)


def make_user_document(text: str, doc_id: str = "phase8-test-doc"):
    """Create a test user document with given text."""
    timestamp = datetime.now(timezone.utc)
    record = DocumentRecord(
        document_id=doc_id,
        filename="test.pdf",
        file_size=100,
        upload_time=timestamp,
        page_count=1,
        processing_status="processed",
        created_at=timestamp,
    )
    import app.documents.service as document_service

    doc_dir = os.path.join(document_service.STORAGE_ROOT, "documents", doc_id)
    os.makedirs(os.path.join(doc_dir, "pages"), exist_ok=True)
    save_json(os.path.join(doc_dir, "metadata.json"), record.model_dump(mode="json"))
    page = Page(
        document_id=doc_id,
        page_number=1,
        text=text,
        extraction_method="text",
        blocks=[PageBlock(text=text)],
    )
    save_json(os.path.join(doc_dir, "pages", "page_1.json"), page.model_dump(mode="json"))
    return doc_id


def make_authoritative_provision(text: str):
    """Create test regulatory authority provision."""
    source = create_source(
        title="Test Procurement Source",
        issuing_authority="Test Authority",
        jurisdiction="TEST",
        government_level="CENTRAL",
        source_type="RULE",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://test.gov/rule",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    document = create_document(
        source_id=source["source_id"],
        title="Test Procurement Document",
        issuing_authority="Test Authority",
        jurisdiction="TEST",
        government_level="CENTRAL",
        document_type="RULE",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-01-01",
        official_url=source["official_url"],
        status="ACTIVE",
        ingestion_status="READY",
    )
    provision = create_provision(
        document_id=document["document_id"],
        source_id=source["source_id"],
        parent_id=None,
        provision_type="RULE",
        provision_number="Rule 1",
        heading="Test requirement",
        text=text,
        raw_text=text,
        normalized_text=text,
        page_number=1,
        source_locator="p.1",
        official_url=source["official_url"],
    )
    return source, document, provision


class TestPhase8RiskClassification:
    """Test risk classification logic."""

    def test_critical_risk_for_mandatory_potential_non_compliance(self):
        """Potential non-compliance with HIGH severity = CRITICAL risk."""
        # Create mock regulatory basis
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessment = RequirementAssessment(
            assessment_id="test-1",
            requirement_id="req-1",
            document_id="doc-1",
            status=FindingStatus.POTENTIAL_NON_COMPLIANCE,
            severity=Severity.HIGH,
            title="Test",
            description="Test requirement",
            regulatory_basis=regulatory_basis,
            confidence="HIGH",
            created_at=datetime.now(timezone.utc),
        )
        risk = _classify_risk(assessment, mandatory=True)
        assert risk == RiskLevel.CRITICAL

    def test_high_risk_for_mandatory_insufficient_evidence(self):
        """Mandatory requirement with insufficient evidence = HIGH risk."""
        assessment = RequirementAssessment(
            assessment_id="test-2",
            requirement_id="req-2",
            document_id="doc-1",
            status=FindingStatus.INSUFFICIENT_EVIDENCE,
            severity=Severity.HIGH,
            title="Test",
            description="Test requirement",
            confidence="LOW",
            created_at=datetime.now(timezone.utc),
        )
        risk = _classify_risk(assessment, mandatory=True)
        assert risk == RiskLevel.HIGH

    def test_medium_risk_for_mandatory_requires_review(self):
        """Mandatory requirement requiring review = MEDIUM risk."""
        # Create mock regulatory basis
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessment = RequirementAssessment(
            assessment_id="test-3",
            requirement_id="req-3",
            document_id="doc-1",
            status=FindingStatus.REQUIRES_REVIEW,
            severity=Severity.MEDIUM,
            title="Test",
            description="Test requirement",
            regulatory_basis=regulatory_basis,
            confidence="MEDIUM",
            created_at=datetime.now(timezone.utc),
        )
        risk = _classify_risk(assessment, mandatory=True)
        assert risk == RiskLevel.MEDIUM

    def test_low_risk_for_mandatory_compliant(self):
        """Mandatory compliant requirement = LOW risk."""
        # Create mock regulatory basis
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessment = RequirementAssessment(
            assessment_id="test-4",
            requirement_id="req-4",
            document_id="doc-1",
            status=FindingStatus.COMPLIANT,
            severity=Severity.LOW,
            title="Test",
            description="Test requirement",
            regulatory_basis=regulatory_basis,
            confidence="HIGH",
            created_at=datetime.now(timezone.utc),
        )
        risk = _classify_risk(assessment, mandatory=True)
        assert risk == RiskLevel.LOW

    def test_info_risk_for_not_applicable(self):
        """Not applicable requirement = INFO risk."""
        assessment = RequirementAssessment(
            assessment_id="test-5",
            requirement_id="req-5",
            document_id="doc-1",
            status=FindingStatus.NOT_APPLICABLE,
            severity=Severity.LOW,
            title="Test",
            description="Test requirement",
            confidence="HIGH",
            created_at=datetime.now(timezone.utc),
        )
        risk = _classify_risk(assessment, mandatory=False)
        assert risk == RiskLevel.INFO


class TestPhase8DecisionAggregation:
    """Test overall compliance decision aggregation."""

    def test_all_compliant_requirements(self):
        """All compliant requirements => COMPLIANT status."""
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessments = [
            RequirementAssessment(
                assessment_id=f"test-{i}",
                requirement_id=f"req-{i}",
                document_id="doc-1",
                status=FindingStatus.COMPLIANT,
                severity=Severity.LOW,
                title=f"Requirement {i}",
                description=f"Description {i}",
                regulatory_basis=regulatory_basis,
                confidence="HIGH",
                created_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]
        status, risk = _derive_overall_status(assessments)
        assert status == OverallComplianceStatus.COMPLIANT
        assert risk == RiskLevel.LOW

    def test_potential_non_compliance_high_severity(self):
        """Any potential non-compliance with HIGH severity => HIGH_RISK."""
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessments = [
            RequirementAssessment(
                assessment_id="test-1",
                requirement_id="req-1",
                document_id="doc-1",
                status=FindingStatus.COMPLIANT,
                severity=Severity.LOW,
                title="Compliant",
                description="Compliant requirement",
                regulatory_basis=regulatory_basis,
                confidence="HIGH",
                created_at=datetime.now(timezone.utc),
            ),
            RequirementAssessment(
                assessment_id="test-2",
                requirement_id="req-2",
                document_id="doc-1",
                status=FindingStatus.POTENTIAL_NON_COMPLIANCE,
                severity=Severity.HIGH,
                title="Non-compliant",
                description="Non-compliant requirement",
                regulatory_basis=regulatory_basis,
                confidence="HIGH",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        status, risk = _derive_overall_status(assessments)
        assert status == OverallComplianceStatus.HIGH_RISK
        assert risk == RiskLevel.CRITICAL

    def test_insufficient_evidence_requires_review(self):
        """Insufficient evidence => REVIEW_REQUIRED."""
        assessments = [
            RequirementAssessment(
                assessment_id="test-1",
                requirement_id="req-1",
                document_id="doc-1",
                status=FindingStatus.INSUFFICIENT_EVIDENCE,
                severity=Severity.MEDIUM,
                title="Missing evidence",
                description="Requirement lacking evidence",
                confidence="LOW",
                created_at=datetime.now(timezone.utc),
            )
        ]
        status, risk = _derive_overall_status(assessments)
        assert status == OverallComplianceStatus.REVIEW_REQUIRED

    def test_not_applicable_excluded_from_decision(self):
        """Not-applicable requirements don't affect overall status."""
        from app.compliance.models import RegulatoryEvidence
        regulatory_basis = [
            RegulatoryEvidence(
                source_id="src-1",
                document_id="doc-1",
                provision_id="prov-1",
                provision_number="Rule 1",
                text="Test provision",
            )
        ]
        assessments = [
            RequirementAssessment(
                assessment_id="test-1",
                requirement_id="req-1",
                document_id="doc-1",
                status=FindingStatus.NOT_APPLICABLE,
                severity=Severity.LOW,
                title="Optional",
                description="Optional requirement",
                confidence="HIGH",
                created_at=datetime.now(timezone.utc),
            ),
            RequirementAssessment(
                assessment_id="test-2",
                requirement_id="req-2",
                document_id="doc-1",
                status=FindingStatus.COMPLIANT,
                severity=Severity.LOW,
                title="Compliant",
                description="Compliant requirement",
                regulatory_basis=regulatory_basis,
                confidence="HIGH",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        status, risk = _derive_overall_status(assessments)
        assert status == OverallComplianceStatus.COMPLIANT


class TestPhase8ReportGeneration:
    """Test compliance decision report generation."""

    def test_generate_report_all_compliant(self):
        """Generate report with all compliant requirements."""
        document_id = make_user_document("The bidder must submit GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        # Evaluate requirements
        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        # Generate Phase 8 decision report
        report = generate_compliance_decision_report(analysis_id, document_id)

        assert report.analysis_id == analysis_id
        assert report.document_id == document_id
        assert report.total_requirements > 0
        assert len(report.findings) == report.total_requirements
        total_statuses = (
            report.compliant_count
            + report.requires_review_count
            + report.potential_non_compliance_count
            + report.insufficient_evidence_count
            + report.unknown_count
        )
        assert total_statuses == report.applicable_requirements
        assert report.applicable_requirements <= report.total_requirements
        assert report.overall_status in [
            OverallComplianceStatus.COMPLIANT,
            OverallComplianceStatus.REVIEW_REQUIRED,
        ]

    def test_generate_report_with_non_compliance(self):
        """Generate report with potential non-compliance findings."""
        document_id = make_user_document("The bidder must submit GST certificate and will not submit.")
        make_authoritative_provision("The bidder must submit GST certificate.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)

        assert report.analysis_id == analysis_id
        assert report.document_id == document_id
        assert report.total_requirements > 0
        assert len(report.findings) == report.total_requirements
        assert report.potential_non_compliance_count > 0 or report.requires_review_count > 0
        assert any(
            f.status in [FindingStatus.POTENTIAL_NON_COMPLIANCE.value, FindingStatus.REQUIRES_REVIEW.value]
            for f in report.findings
        )

    def test_report_persistence_and_retrieval(self):
        """Test that reports are persisted and can be retrieved using get_compliance_decision_report."""
        document_id = make_user_document("The bidder must submit GST registration and PAN.")
        make_authoritative_provision("The bidder must submit GST registration and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        # Generate report
        report = generate_compliance_decision_report(analysis_id, document_id)
        report_id = report.report_id

        assert report_id
        # Real Phase 8 retrieval
        retrieved = get_compliance_decision_report(report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id
        assert retrieved.document_id == report.document_id
        assert retrieved.analysis_id == report.analysis_id
        assert retrieved.overall_status == report.overall_status
        assert retrieved.overall_risk == report.overall_risk
        assert retrieved.total_requirements == report.total_requirements
        assert retrieved.total_requirements > 0
        assert retrieved.applicable_requirements == report.applicable_requirements
        assert len(retrieved.findings) == len(report.findings)
        assert len(retrieved.findings) == report.total_requirements
        assert len(retrieved.human_review_queue) == len(report.human_review_queue)


class TestPhase8HumanReviewQueue:
    """Test human review queue generation."""

    def test_review_queue_includes_requires_review_status(self):
        """Requirements with reviewable status are in review queue."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)

        assert report.total_requirements > 0
        reviewable_statuses = {
            FindingStatus.REQUIRES_REVIEW.value,
            FindingStatus.POTENTIAL_NON_COMPLIANCE.value,
            FindingStatus.INSUFFICIENT_EVIDENCE.value,
            FindingStatus.UNKNOWN.value,
        }
        expected_review_count = sum(1 for f in report.findings if f.status in reviewable_statuses)
        assert len(report.human_review_queue) == expected_review_count
        assert all(item.status in reviewable_statuses for item in report.human_review_queue)

    def test_high_priority_items_identified(self):
        """High-risk items are identified as high priority."""
        document_id = make_user_document("The bidder must submit GST certificate and will not submit.")
        make_authoritative_provision("The bidder must submit GST certificate.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)

        assert report.total_requirements > 0
        assert len(report.high_priority_items) > 0
        # High priority items should have priority=1,2,3...
        for item in report.high_priority_items:
            assert item.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
            assert any(q.review_item_id == item.review_item_id for q in report.human_review_queue)

    def test_human_review_queue_persisted_in_report_and_retrievable(self):
        """Test that human review queue is persisted inside ComplianceDecisionReport (Option B)."""
        document_id = make_user_document("The bidder must submit GST registration and PAN.")
        make_authoritative_provision("The bidder must submit GST registration and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)
        assert report.total_requirements > 0

        # Retrieve report from storage
        retrieved = get_compliance_decision_report(report.report_id)
        assert retrieved is not None
        assert len(retrieved.human_review_queue) == len(report.human_review_queue)
        for original_item, retrieved_item in zip(report.human_review_queue, retrieved.human_review_queue):
            assert retrieved_item.review_item_id == original_item.review_item_id
            assert retrieved_item.requirement_id == original_item.requirement_id
            assert retrieved_item.status == original_item.status
            assert retrieved_item.risk_level == original_item.risk_level
            assert retrieved_item.priority == original_item.priority


class TestPhase8Explainability:
    """Test requirement explanation generation."""

    def test_create_explanations_for_analysis(self):
        """Create and persist explanations for all requirements."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        # Create explanations
        explanations = create_and_persist_explanations(analysis_id, document_id)

        assert isinstance(explanations, dict)
        assert len(explanations) == payload["report"]["total_requirements"]
        assert len(explanations) > 0
        assert set(explanations.keys()) == {a["requirement_id"] for a in payload["requirement_assessments"]}

    def test_explanation_contains_required_fields(self):
        """Explanations contain all required fields."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        explanations = create_and_persist_explanations(analysis_id, document_id)
        assert len(explanations) > 0

        for req_id, explanation in explanations.items():
            assert explanation.requirement_id
            assert explanation.requirement_title
            assert explanation.evaluation_status
            assert explanation.risk_level
            assert explanation.reason
            assert explanation.evidence_summary
            assert explanation.category
            assert isinstance(explanation.mandatory, bool)


class TestPhase8EvidenceTracing:
    """Test evidence traceability in explanations."""

    def test_evidence_trace_includes_sources(self):
        """Evidence traces include document and regulatory sources."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        explanations = create_and_persist_explanations(analysis_id, document_id)
        assert len(explanations) > 0

        for req_id, explanation in explanations.items():
            if explanation.evidence_trace:
                trace = explanation.evidence_trace
                assert trace.requirement_id
                assert trace.evaluation_status


class TestPhase8APIEndpoints:
    """Test Phase 8 API endpoints."""

    def test_compliance_decision_endpoint_structure(self):
        """Test /compliance/decision endpoint returns proper structure via real API call."""
        document_id = make_user_document("The bidder must submit GST registration and PAN.")
        make_authoritative_provision("The bidder must submit GST registration and PAN.")
        get_retrieval_service().build_index()

        response = client.post(
            "/api/v1/compliance/decision",
            json={"document_id": document_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "report_id" in data and data["report_id"]
        assert "analysis_id" in data and data["analysis_id"]
        assert data["document_id"] == document_id
        assert "overall_status" in data and data["overall_status"]
        assert "overall_risk" in data and data["overall_risk"]
        assert "total_requirements" in data and data["total_requirements"] > 0
        assert "findings" in data and isinstance(data["findings"], list)
        assert len(data["findings"]) == data["total_requirements"]
        assert "human_review_queue" in data and isinstance(data["human_review_queue"], list)

    def test_compliance_decision_covers_all_applicable_requirements_beyond_five(self):
        """Test that POST /compliance/decision covers ALL applicable requirements (>5) without truncation."""
        text = (
            "The bidder must submit GST registration certificate.\n"
            "The bidder must submit PAN card copy.\n"
            "The bidder must submit OEM authorization letter.\n"
            "The bidder must submit audited financial statements for turnover.\n"
            "The bidder must submit completion certificate for minimum experience.\n"
            "The bidder must submit Udyam registration certificate.\n"
            "The bidder must submit startup certificate for exemption."
        )
        document_id = make_user_document(text, doc_id="multi-req-doc")
        make_authoritative_provision("The bidder must submit GST registration certificate and PAN card copy.")
        get_retrieval_service().build_index()

        response = client.post(
            "/api/v1/compliance/decision",
            json={"document_id": document_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_requirements"] > 5
        assert len(data["findings"]) == data["total_requirements"]
        assert data["total_requirements"] >= 7

    def test_compliance_decision_error_handling_sanitized(self, monkeypatch):
        """Test that internal exceptions in /compliance/decision do not leak raw exception text."""
        document_id = make_user_document("The bidder must submit GST certificate.")

        import app.api.v1.compliance as compliance_api

        def broken_generate(*args, **kwargs):
            raise RuntimeError("SecretDatabasePassword@/internal/var/root/db.sock failed")

        monkeypatch.setattr(compliance_api, "generate_compliance_decision_report", broken_generate)

        response = client.post(
            "/api/v1/compliance/decision",
            json={"document_id": document_id},
        )
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Decision generation failed"
        assert "SecretDatabasePassword" not in response.text
        assert "db.sock" not in response.text
        assert "RuntimeError" not in response.text


class TestPhase8ReportStatistics:
    """Test compliance decision report statistics."""

    def test_status_counts_accurate(self):
        """Report status counts match actual assessments."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)

        # Sum of status counts should equal total applicable requirements
        total_statuses = (
            report.compliant_count
            + report.potential_non_compliance_count
            + report.insufficient_evidence_count
            + report.requires_review_count
            + report.unknown_count
        )
        assert report.total_requirements > 0
        assert total_statuses == report.applicable_requirements
        assert report.applicable_requirements <= report.total_requirements

    def test_risk_counts_accurate(self):
        """Report risk counts match actual assessments."""
        document_id = make_user_document("The bidder submits GST and PAN.")
        make_authoritative_provision("The bidder must submit GST and PAN.")
        get_retrieval_service().build_index()

        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, document_id)

        # Sum of risk counts should equal total findings
        total_risks = (
            report.critical_count
            + report.high_count
            + report.medium_count
            + report.low_count
            + report.info_count
        )
        assert report.total_requirements > 0
        assert total_risks == len(report.findings)
        assert total_risks == report.total_requirements


class TestPhase8Integration:
    """Integration tests for full Phase 8 workflow."""

    def test_end_to_end_decision_workflow(self):
        """Test end-to-end decision generation workflow."""
        # Create document
        document_id = make_user_document("The bidder must submit GST certificate and PAN.")
        make_authoritative_provision("The bidder must submit GST certificate and PAN.")
        get_retrieval_service().build_index()

        # Evaluate requirements
        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]
        assert analysis_id

        # Generate decision report
        report = generate_compliance_decision_report(analysis_id, document_id)
        assert report.report_id
        assert report.analysis_id == analysis_id
        assert report.document_id == document_id
        assert report.total_requirements > 0
        assert len(report.findings) == report.total_requirements

        # Create explanations
        explanations = create_and_persist_explanations(analysis_id, document_id)
        assert isinstance(explanations, dict)
        assert len(explanations) == report.total_requirements

        # Retrieve report
        retrieved = get_compliance_decision_report(report.report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id
        assert retrieved.document_id == report.document_id
        assert retrieved.analysis_id == report.analysis_id
        assert retrieved.overall_status == report.overall_status
        assert retrieved.overall_risk == report.overall_risk
        assert retrieved.total_requirements == report.total_requirements
        assert len(retrieved.findings) == len(report.findings)
        assert len(retrieved.human_review_queue) == len(report.human_review_queue)

    def test_optional_requirement_mandatory_flag_and_risk_preservation(self):
        """Test that optional requirements preserve mandatory=False and do not promote to mandatory risk."""
        tender_text = (
            "The bidder must submit GST certificate.\n"
            "The bidder may submit Udyam registration certificate if applicable."
        )
        document_id = make_user_document(tender_text, doc_id="opt-req-doc")
        make_authoritative_provision("The bidder must submit GST certificate.")
        get_retrieval_service().build_index()

        # Step 1: Verify Phase 6 Requirement extraction has both mandatory=True and mandatory=False
        from app.compliance.service import extract_requirements_for_document

        extracted = extract_requirements_for_document(document_id)
        reqs = {r["title"]: Requirement.model_validate(r) for r in extracted["requirements"]}

        mandatory_reqs = [r for r in reqs.values() if r.mandatory is True]
        optional_reqs = [r for r in reqs.values() if r.mandatory is False]
        assert len(mandatory_reqs) >= 1, "Expected at least one mandatory requirement"
        assert len(optional_reqs) >= 1, "Expected at least one optional requirement"

        optional_req = optional_reqs[0]
        mandatory_req = mandatory_reqs[0]
        assert optional_req.mandatory is False
        assert mandatory_req.mandatory is True

        # Step 2: Evaluate and generate Phase 8 report
        payload = evaluate_requirements_for_document(document_id)
        analysis_id = payload["analysis_id"]
        report = generate_compliance_decision_report(analysis_id, document_id)
        explanations = create_and_persist_explanations(analysis_id, document_id)

        # Step 3: Verify Phase 8 findings preserve mandatory flag
        finding_map = {f.requirement_id: f for f in report.findings}
        assert optional_req.requirement_id in finding_map
        assert mandatory_req.requirement_id in finding_map

        optional_finding = finding_map[optional_req.requirement_id]
        mandatory_finding = finding_map[mandatory_req.requirement_id]

        assert optional_finding.mandatory is False
        assert mandatory_finding.mandatory is True

        # Step 4: Verify explanations preserve mandatory and category
        assert optional_req.requirement_id in explanations
        assert mandatory_req.requirement_id in explanations

        optional_explanation = explanations[optional_req.requirement_id]
        mandatory_explanation = explanations[mandatory_req.requirement_id]

        assert optional_explanation.mandatory is False
        assert mandatory_explanation.mandatory is True
        assert optional_explanation.category == optional_req.category
        assert mandatory_explanation.category == mandatory_req.category

        # Step 5: Verify risk classification does NOT elevate optional requirement to CRITICAL/HIGH
        assert optional_finding.risk_level not in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        assert optional_explanation.risk_level not in [RiskLevel.CRITICAL, RiskLevel.HIGH]

