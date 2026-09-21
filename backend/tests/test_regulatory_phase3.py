import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.regulatory.service import (
    create_document,
    create_provision,
    create_source,
    get_document,
    get_provision,
    list_documents,
    list_sources,
    search_provisions,
)


@pytest.fixture(autouse=True)
def reset_registry(tmp_path, monkeypatch):
    import app.regulatory.service as service

    monkeypatch.setattr(service, "STORAGE_ROOT", str(tmp_path / "regulatory"))
    service.ensure_directories()
    yield


def test_source_creation_and_uniqueness():
    source = create_source(
        title="General Financial Rules 2017",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="GFR",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/gfr-2017",
        publication_date="2017-01-01",
        effective_date="2017-04-01",
        version="2017",
        status="UNKNOWN",
        ingestion_status="SOURCE_REQUIRED",
    )
    assert source["source_id"]
    assert source["ingestion_status"] == "SOURCE_REQUIRED"

    with pytest.raises(ValueError):
        create_source(
            title="General Financial Rules 2017",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/gfr-2017",
            publication_date="2017-01-01",
            effective_date="2017-04-01",
            version="2017",
            status="UNKNOWN",
            ingestion_status="SOURCE_REQUIRED",
        )


def test_document_and_source_relationship():
    source = create_source(
        title="Procurement Manual 2024",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="PROCUREMENT_MANUAL",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/proc-manual-2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    document = create_document(
        source_id=source["source_id"],
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="PROCUREMENT_MANUAL",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        official_url="https://example.gov.in/proc-manual-2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    assert document["source_id"] == source["source_id"]
    assert document["document_id"]


def test_provision_hierarchy_and_parent_child_links():
    source = create_source(
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="PROCUREMENT_MANUAL",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/proc-manual",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    document = create_document(
        source_id=source["source_id"],
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="PROCUREMENT_MANUAL",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        official_url="https://example.gov.in/proc-manual",
        status="ACTIVE",
        ingestion_status="READY",
    )

    chapter = create_provision(
        document_id=document["document_id"],
        parent_id=None,
        provision_type="CHAPTER",
        provision_number="Chapter 1",
        heading="General Principles",
        text="General principles apply to procurement.",
        raw_text="General principles apply to procurement.",
        normalized_text="General principles apply to procurement.",
        page_number=1,
        source_locator="p.1",
        source_id=source["source_id"],
        official_url="https://example.gov.in/proc-manual",
    )
    rule = create_provision(
        document_id=document["document_id"],
        parent_id=chapter["provision_id"],
        provision_type="RULE",
        provision_number="Rule 1",
        heading="Procurement Process",
        text="Procurement must follow the approved process.",
        raw_text="Procurement must follow the approved process.",
        normalized_text="Procurement must follow the approved process.",
        page_number=2,
        source_locator="p.2",
        source_id=source["source_id"],
        official_url="https://example.gov.in/proc-manual",
    )
    assert chapter["parent_id"] is None
    assert rule["parent_id"] == chapter["provision_id"]
    assert get_provision(rule["provision_id"])["parent_id"] == chapter["provision_id"]


def test_version_handling_and_active_superseded_versions():
    source = create_source(
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="PROCUREMENT_MANUAL",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/proc-manual",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    doc1 = create_document(
        source_id=source["source_id"],
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="PROCUREMENT_MANUAL",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        official_url="https://example.gov.in/proc-manual",
        status="ACTIVE",
        ingestion_status="READY",
    )
    doc2 = create_document(
        source_id=source["source_id"],
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="PROCUREMENT_MANUAL",
        version="2025",
        publication_date="2025-01-01",
        effective_date="2025-02-01",
        official_url="https://example.gov.in/proc-manual",
        status="SUPERSEDED",
        ingestion_status="READY",
    )
    assert doc1["status"] == "ACTIVE"
    assert doc2["status"] == "SUPERSEDED"


def test_provenance_and_hashes_are_preserved():
    source = create_source(
        title="General Financial Rules",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="GFR",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/gfr",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        version="2024",
        status="UNKNOWN",
        ingestion_status="SOURCE_REQUIRED",
    )
    document = create_document(
        source_id=source["source_id"],
        title="General Financial Rules",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="GFR",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        official_url="https://example.gov.in/gfr",
        status="UNKNOWN",
        ingestion_status="SOURCE_REQUIRED",
    )
    provision = create_provision(
        document_id=document["document_id"],
        parent_id=None,
        provision_type="SECTION",
        provision_number="Section 1",
        heading="Authority",
        text="The authority for the rules is the Department of Expenditure.",
        raw_text="The authority for the rules is the Department of Expenditure.",
        normalized_text="The authority for the rules is the Department of Expenditure.",
        page_number=5,
        source_locator="p.5",
        source_id=source["source_id"],
        official_url="https://example.gov.in/gfr",
    )
    assert provision["source_id"] == source["source_id"]
    assert provision["official_url"] == "https://example.gov.in/gfr"
    assert provision["content_hash"]
    assert provision["raw_text"]
    assert provision["normalized_text"]


def test_user_tender_cannot_become_regulatory_source():
    with pytest.raises(ValueError):
        create_source(
            title="Uploaded Tender Document",
            issuing_authority="Private Vendor",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="OFFICIAL_PORTAL",
            authority_level="SECONDARY_SOURCE",
            official_url="https://example.gov.in/tender",
            publication_date="2024-01-01",
            effective_date="2024-02-01",
            version="1",
            status="ACTIVE",
            ingestion_status="READY",
            source_domain="DOCUMENT_EVIDENCE",
        )


def test_unsupported_source_rejection_and_missing_source_handling():
    with pytest.raises(ValueError):
        create_source(
            title="Wikipedia Summary",
            issuing_authority="Wikipedia",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="SECONDARY_SOURCE",
            official_url="https://wikipedia.org",
            publication_date="2024-01-01",
            effective_date="2024-02-01",
            version="2024",
            status="UNKNOWN",
            ingestion_status="SOURCE_REQUIRED",
        )

    source = create_source(
        title="Official GFR Source Pending Verification",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="GFR",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="",
        publication_date="",
        effective_date="",
        version="UNKNOWN",
        status="UNKNOWN",
        ingestion_status="SOURCE_REQUIRED",
    )
    assert source["status"] == "UNKNOWN"
    assert source["ingestion_status"] == "SOURCE_REQUIRED"


def test_deterministic_regulatory_search():
    source = create_source(
        title="Procurement Manual 2024",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        source_type="PROCUREMENT_MANUAL",
        authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
        official_url="https://example.gov.in/proc-manual",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        version="2024",
        status="ACTIVE",
        ingestion_status="READY",
    )
    document = create_document(
        source_id=source["source_id"],
        title="Manual for Procurement of Goods",
        issuing_authority="Department of Expenditure",
        jurisdiction="INDIA",
        government_level="CENTRAL GOVERNMENT",
        document_type="PROCUREMENT_MANUAL",
        version="2024",
        publication_date="2024-01-01",
        effective_date="2024-02-01",
        official_url="https://example.gov.in/proc-manual",
        status="ACTIVE",
        ingestion_status="READY",
    )
    create_provision(
        document_id=document["document_id"],
        parent_id=None,
        provision_type="RULE",
        provision_number="Rule 5",
        heading="Procurement Process",
        text="The procurement process must be transparent.",
        raw_text="The procurement process must be transparent.",
        normalized_text="The procurement process must be transparent.",
        page_number=10,
        source_locator="p.10",
        source_id=source["source_id"],
        official_url="https://example.gov.in/proc-manual",
    )
    results = search_provisions("procurement")
    assert len(results) >= 1
    assert results[0]["document_title"] == "Manual for Procurement of Goods"
    assert results[0]["provision_number"] == "Rule 5"


def test_regulatory_api_endpoints():
    client = TestClient(app)
    sources = client.get("/api/v1/regulatory-sources")
    assert sources.status_code == 200
    payload = sources.json()
    assert isinstance(payload, list)

    regs = client.get("/api/v1/regulations")
    assert regs.status_code == 200
    assert isinstance(regs.json(), list)

    search = client.get("/api/v1/regulations/search?q=procurement")
    assert search.status_code == 200
    data = search.json()
    assert isinstance(data, list)


def test_no_placeholder_sources_seeded_automatically():
    """The registry must start empty: no placeholder/unverified GFR source may
    be auto-seeded. Verified regulatory content is loaded explicitly."""
    assert list_sources() == []
    assert list_documents() == []
