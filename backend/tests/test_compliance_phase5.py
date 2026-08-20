import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.compliance.models import (
    AnalysisRequest,
    DocumentEvidence,
    Finding,
    FindingStatus,
    RegulatoryEvidence,
    Severity,
)
from app.compliance.service import _regulatory_evidence, analyze
from app.documents.models import DocumentRecord, Page, PageBlock
from app.documents.service import save_json
from app.main import app
from app.regulatory.service import create_document, create_provision, create_source
from app.retrieval.models import RetrievalResult
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LocalVectorStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def phase5_environment(tmp_path, monkeypatch):
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


def make_user_document(text="Tender requires three bids"):
    document_id = "user-document-1"
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


def make_authoritative_provision():
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
        heading="Bid process",
        text="Procurement bids should be evaluated using documented criteria.",
        raw_text="Procurement bids should be evaluated using documented criteria.",
        normalized_text="Procurement bids should be evaluated using documented criteria.",
        page_number=1,
        source_locator="p.1",
        official_url=source["official_url"],
    )
    return source, document, provision


def test_analysis_creation_separates_evidence_and_persists():
    document_id = make_user_document()
    _, regulatory_document, provision = make_authoritative_provision()

    from app.retrieval.service import get_retrieval_service

    get_retrieval_service().build_index()
    result = analyze(AnalysisRequest(document_id=document_id, requested_scope="bid evaluation"))

    assert result.status == "COMPLETED"
    finding = result.findings[0]
    assert finding.status == FindingStatus.REQUIRES_REVIEW
    assert finding.requires_human_review is True
    assert finding.document_evidence[0].document_id == document_id
    assert finding.regulatory_basis[0].document_id == regulatory_document["document_id"]
    assert finding.regulatory_basis[0].provision_id == provision["provision_id"]
    assert finding.document_evidence[0].document_id != finding.regulatory_basis[0].document_id

    response = client.get(f"/api/v1/compliance/analyses/{result.analysis_id}")
    assert response.status_code == 200
    assert response.json()["analysis_id"] == result.analysis_id
    findings_response = client.get(f"/api/v1/compliance/analyses/{result.analysis_id}/findings")
    assert findings_response.status_code == 200
    assert findings_response.json()[0]["requires_human_review"] is True


def test_analysis_requires_processed_valid_document():
    response = client.post(
        "/api/v1/compliance/analyze",
        json={"document_id": "missing", "requested_scope": "procurement"},
    )
    assert response.status_code == 404


def test_insufficient_evidence_is_explicit():
    document_id = make_user_document()
    result = analyze(AnalysisRequest(document_id=document_id, requested_scope="unavailable scope"))
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.findings[0].status == FindingStatus.INSUFFICIENT_EVIDENCE
    assert result.findings[0].regulatory_basis == []
    assert result.findings[0].severity == Severity.UNKNOWN


def test_finding_rejects_ungrounded_status():
    with pytest.raises(ValueError, match="Regulatory basis"):
        Finding(
            finding_id="f",
            document_id="d",
            analysis_id="a",
            category="test",
            status=FindingStatus.POTENTIAL_NON_COMPLIANCE,
            severity=Severity.MEDIUM,
            title="Unsupported claim",
            description="This claim has no authority.",
            created_at=datetime.now(timezone.utc),
        )


def test_unsupported_regulatory_citation_is_rejected():
    result = RetrievalResult(
        chunk_id="fake",
        document_id="fake-document",
        source_id="fake-source",
        provision_id="fake-provision",
        provision_number="Rule X",
        heading="Fake",
        text="Invented requirement",
        page_number=1,
        source_locator="p.1",
        official_url="https://fake.invalid",
        version="UNKNOWN",
        status="ACTIVE",
        content_hash="fake",
    )
    with pytest.raises(ValueError, match="does not resolve"):
        _regulatory_evidence(result)


def test_tampered_regulatory_text_is_rejected():
    source, document, provision = make_authoritative_provision()
    result = RetrievalResult(
        chunk_id="fake",
        document_id=document["document_id"],
        source_id=source["source_id"],
        provision_id=provision["provision_id"],
        provision_number=provision["provision_number"],
        heading=provision["heading"],
        text="Invented requirement",
        page_number=provision["page_number"],
        source_locator=provision["source_locator"],
        official_url=provision["official_url"],
        version="2024",
        status="ACTIVE",
        content_hash=provision["content_hash"],
    )
    with pytest.raises(ValueError, match="not supported"):
        _regulatory_evidence(result)


def test_api_analysis_endpoint_returns_grounded_provenance():
    document_id = make_user_document()
    make_authoritative_provision()
    from app.retrieval.service import get_retrieval_service

    get_retrieval_service().build_index()
    response = client.post(
        "/api/v1/compliance/analyze",
        json={"document_id": document_id, "requested_scope": "procurement"},
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["regulatory_basis"][0]["source_id"]
    assert finding["regulatory_basis"][0]["official_url"] == "https://example.gov.in/gfr"