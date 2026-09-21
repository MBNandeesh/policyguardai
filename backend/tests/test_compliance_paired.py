import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.documents.models import DocumentRecord, Page, PageBlock
from app.documents.service import save_json
import app.documents.service as document_service
import app.compliance.service as compliance_service
import app.regulatory.service as regulatory_service
import app.retrieval.service as retrieval_service
from app.regulatory.service import create_document, create_provision, create_source
from app.retrieval.service import RetrievalService, get_retrieval_service
from app.retrieval.vector_store import LocalVectorStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def paired_environment(tmp_path, monkeypatch):
    storage_root = str(tmp_path / "storage")
    monkeypatch.setattr(document_service, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(compliance_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance"))
    monkeypatch.setattr(regulatory_service, "STORAGE_ROOT", os.path.join(storage_root, "regulatory"))
    regulatory_service.ensure_directories()

    retrieval = RetrievalService(vector_store=LocalVectorStore(os.path.join(storage_root, "retrieval")))
    retrieval_service.set_retrieval_service(retrieval)
    yield
    retrieval_service.set_retrieval_service(None)


def make_document(document_id: str, filename: str, text: str, document_type: str = "tender"):
    timestamp = datetime.now(timezone.utc)
    record = DocumentRecord(
        document_id=document_id,
        filename=filename,
        file_size=100,
        upload_time=timestamp,
        page_count=1,
        processing_status="processed",
        document_type=document_type,
        created_at=timestamp,
    )
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


def test_paired_decision_maps_tender_requirements_to_bidder_evidence():
    tender_text = "The bidder must submit GST registration and PAN."
    bidder_text = "The bidder must submit GST registration and PAN. GST certificate and PAN card are attached herewith."
    tender_id = make_document("paired-tender", "tender.pdf", tender_text, document_type="tender")
    bidder_id = make_document("paired-bidder", "bidder.pdf", bidder_text, document_type="bidder")
    make_authoritative_provision(tender_text)
    get_retrieval_service().build_index()

    response = client.post(
        "/api/v1/compliance/decision/paired",
        json={"tender_document_id": tender_id, "bidder_document_ids": [bidder_id]},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["tender_document_id"] == tender_id
    assert data["bidder_document_ids"] == [bidder_id]
    report = data["report"]
    assert report["total_requirements"] >= 1

    # The paired evaluation must have produced assessments with combined evidence.
    payload = data["report"]
    assessment_check = client.get(
        f"/api/v1/compliance/analyses/{data['analysis_id']}/requirements"
    )
    assert assessment_check.status_code == 200
    assessments = assessment_check.json()
    assert len(assessments) >= 1
    combined_docs = {
        ev["document_id"]
        for assessment in assessments
        for ev in assessment["document_evidence"]
    }
    assert bidder_id in combined_docs


def test_paired_decision_requires_tender_document():
    response = client.post(
        "/api/v1/compliance/decision/paired",
        json={"tender_document_id": "missing-doc", "bidder_document_ids": []},
    )
    assert response.status_code == 404


def test_paired_decision_rejects_missing_bidder_document():
    tender_id = make_document(
        "paired-tender-2", "tender.pdf", "The bidder must submit GST registration and PAN."
    )
    make_authoritative_provision("The bidder must submit GST registration and PAN.")
    get_retrieval_service().build_index()

    response = client.post(
        "/api/v1/compliance/decision/paired",
        json={"tender_document_id": tender_id, "bidder_document_ids": ["no-such-bidder"]},
    )
    assert response.status_code == 404


def test_upload_accepts_document_type():
    import io

    from PyPDF2 import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("bidder.pdf", pdf_bytes, "application/pdf")},
        data={"document_type": "bidder"},
    )
    assert response.status_code == 200
    assert response.json()["document_type"] == "bidder"
