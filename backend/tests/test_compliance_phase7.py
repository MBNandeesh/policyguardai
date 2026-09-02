import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.compliance.models import FindingStatus, Requirement
from app.compliance.service import evaluate_requirement, evaluate_requirements_for_document
from app.documents.models import DocumentRecord, Page, PageBlock
from app.documents.service import save_json
from app.main import app
from app.regulatory.service import create_document, create_provision, create_source
from app.retrieval.service import RetrievalService, get_retrieval_service
from app.retrieval.vector_store import LocalVectorStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def phase7_environment(tmp_path, monkeypatch):
    import app.compliance.service as compliance_service
    import app.documents.service as document_service
    import app.regulatory.service as regulatory_service
    import app.retrieval.service as retrieval_service

    storage_root = str(tmp_path / "storage")
    monkeypatch.setattr(document_service, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(compliance_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance"))
    monkeypatch.setattr(regulatory_service, "STORAGE_ROOT", os.path.join(storage_root, "regulatory"))
    regulatory_service.ensure_directories()

    retrieval = RetrievalService(vector_store=LocalVectorStore(os.path.join(storage_root, "retrieval")))
    retrieval_service.set_retrieval_service(retrieval)
    yield
    retrieval_service.set_retrieval_service(None)


def make_user_document(text: str):
    document_id = "phase7-user-doc"
    timestamp = datetime.now(timezone.utc)
    record = DocumentRecord(
        document_id=document_id,
        filename="tender.pdf",
        file_size=100,
        upload_time=timestamp,
        page_count=1,
        processing_status="processed",
        created_at=timestamp,
    )
    import app.documents.service as document_service

    doc_dir = os.path.join(document_service.STORAGE_ROOT, "documents", document_id)
    os.makedirs(os.path.join(doc_dir, "pages"), exist_ok=True)
    save_json(os.path.join(doc_dir, "metadata.json"), record.model_dump(mode="json"))
    page = Page(
        document_id=document_id,
        page_number=1,
        text=text,
        extraction_method="text",
        blocks=[PageBlock(text=text)],
    )
    save_json(os.path.join(doc_dir, "pages", "page_1.json"), page.model_dump(mode="json"))
    return document_id


def make_authoritative_provision(text: str):
    source = create_source(
        title="Official Procurement Source",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="GFR",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/gfr",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    document = create_document(
        source_id=source["source_id"],
        title="Official Procurement Document",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="GFR",
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
        heading="Bid requirements",
        text=text,
        raw_text=text,
        normalized_text=text,
        page_number=1,
        source_locator="p.1",
        official_url=source["official_url"],
    )
    return source, document, provision


def test_phase7_requirement_evaluation_matches_regulatory_grounding():
    requirement_text = "The bidder must submit GST registration and PAN."
    document_id = make_user_document(requirement_text)
    _, _, provision = make_authoritative_provision(requirement_text)

    get_retrieval_service().build_index()
    payload = evaluate_requirements_for_document(document_id)

    assert payload["document_id"] == document_id
    assert payload["report"]["total_requirements"] >= 1
    assessment = payload["requirement_assessments"][0]
    assert assessment["status"] == FindingStatus.REQUIRES_REVIEW.value
    assert assessment["regulatory_basis"]
    assert assessment["regulatory_basis"][0]["provision_id"] == provision["provision_id"]


def test_phase7_requirement_potential_non_compliance_requires_grounded_negative_evidence():
    document_id = make_user_document("The bidder will not submit GST registration and PAN. No GST certificate or PAN was provided.")
    requirement = Requirement(
        requirement_id="phase7-potential-non-compliance",
        title="GST registration and PAN required",
        description="The bidder must submit GST registration and PAN.",
        category="tax",
        mandatory=True,
        evidence_required=True,
        evidence_types=["GST Certificate", "PAN Document"],
        source_document_id=document_id,
        source_page=1,
        source_text="The bidder will not submit GST registration and PAN. No GST certificate or PAN was provided.",
    )
    make_authoritative_provision("The bidder must submit GST registration and PAN.")
    get_retrieval_service().build_index()

    assessment = evaluate_requirement(document_id, requirement)

    assert assessment.status == FindingStatus.POTENTIAL_NON_COMPLIANCE
    assert assessment.regulatory_basis
    assert assessment.requires_human_review is True


def test_phase7_requirement_not_applicable_when_optional_and_conditioned():
    document_id = make_user_document("If applicable, the bidder may submit GST registration and PAN.")
    requirement = Requirement(
        requirement_id="phase7-not-applicable",
        title="Optional GST submission",
        description="If applicable, the bidder may submit GST registration and PAN.",
        category="tax",
        mandatory=False,
        evidence_required=False,
        evidence_types=["GST Certificate", "PAN Document"],
        source_document_id=document_id,
        source_page=1,
        source_text="If applicable, the bidder may submit GST registration and PAN.",
    )
    make_authoritative_provision("If applicable, the bidder may submit GST registration and PAN.")
    get_retrieval_service().build_index()

    assessment = evaluate_requirement(document_id, requirement)

    assert assessment.status == FindingStatus.NOT_APPLICABLE
    assert assessment.regulatory_basis
    assert assessment.requires_human_review is False


def test_phase7_requirement_compliant_with_grounded_authority():
    document_id = make_user_document("The bidder submits GST registration and PAN.")
    requirement = Requirement(
        requirement_id="phase7-compliant",
        title="GST registration and PAN required",
        description="The bidder must submit GST registration and PAN.",
        category="tax",
        mandatory=True,
        evidence_required=True,
        evidence_types=["GST Certificate", "PAN Document"],
        source_document_id=document_id,
        source_page=1,
        source_text="The bidder submits GST registration and PAN.",
    )
    make_authoritative_provision("The bidder must submit GST registration and PAN.")
    get_retrieval_service().build_index()

    assessment = evaluate_requirement(document_id, requirement)

    assert assessment.status == FindingStatus.REQUIRES_REVIEW
    assert assessment.regulatory_basis
    assert assessment.requires_human_review is True


def test_phase7_requirement_without_authority_is_insufficient_evidence():
    document_id = make_user_document("The bidder must submit a unicorn license certificate.")

    payload = evaluate_requirements_for_document(document_id)

    assessment = payload["requirement_assessments"][0]
    assert assessment["status"] == FindingStatus.INSUFFICIENT_EVIDENCE.value
    assert assessment["regulatory_basis"] == []
    assert assessment["requires_human_review"] is True


def test_phase7_requirement_report_is_persisted_and_retrievable():
    requirement_text = "The bidder must submit GST registration and PAN."
    document_id = make_user_document(requirement_text)
    make_authoritative_provision(requirement_text)
    get_retrieval_service().build_index()

    response = client.post(
        "/api/v1/compliance/requirements/evaluate",
        json={"document_id": document_id, "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    analysis_id = data["analysis_id"]
    assert data["report"]["total_requirements"] >= 1

    report_response = client.get(f"/api/v1/compliance/analyses/{analysis_id}/report")
    assert report_response.status_code == 200
    assert report_response.json()["analysis_id"] == analysis_id
    assert report_response.json()["total_requirements"] >= 1


def test_phase7_requirement_api_contract_and_deduplication():
    document_id = make_user_document("The bidder must submit GST registration and PAN.\nThe bidder must submit GST registration and PAN.")
    make_authoritative_provision("The bidder must submit GST registration and PAN.")
    get_retrieval_service().build_index()

    response = client.post(
        "/api/v1/compliance/requirements/evaluate",
        json={"document_id": document_id, "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["report"]["total_requirements"] == len(data["requirement_assessments"])
    assert len(data["requirement_assessments"]) >= 1
