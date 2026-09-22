"""Tests for endpoint protection and the PDF report download feature.

Covers:
- Protected endpoints reject unauthenticated requests (upload, analyze,
  decision, paired decision, extraction, evaluate, review actions, audit
  write/verify) while staying usable for a logged-in officer.
- Health endpoint stays public and reports OCR capability.
- Compliance decision report PDF download:
  * requires authentication
  * returns application/pdf with a sensible filename
  * PDF content contains the actual report ID/status/requirements
  * invalid report IDs return 404
- Production secret enforcement (POLICYGUARD_AUTH_SECRET / demo password).
"""

import io
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PyPDF2 import PdfReader

from app.main import app
from app.documents.models import DocumentRecord, Page, PageBlock
from app.documents.service import save_json
import app.documents.service as document_service
import app.compliance.service as compliance_service
import app.compliance.phase8_service as phase8_service
import app.regulatory.service as regulatory_service
import app.retrieval.service as retrieval_service
from app.regulatory.service import create_document, create_provision, create_source
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LocalVectorStore

client = TestClient(app)

PROTECTED_POST_ENDPOINTS = [
    ("/api/v1/documents/upload", None),
    ("/api/v1/compliance/analyze", {"document_id": "d", "requested_scope": "s"}),
    ("/api/v1/compliance/decision", {"document_id": "d"}),
    ("/api/v1/compliance/decision/paired", {"tender_document_id": "d", "bidder_document_ids": []}),
    ("/api/v1/compliance/requirements/extract", {"document_id": "d"}),
    ("/api/v1/compliance/requirements/evaluate", {"document_id": "d"}),
    ("/api/v1/review/actions", {"actor": "x", "action": "ACCEPT", "finding_id": "f", "reason": "r"}),
    ("/api/v1/audit/events", {"actor": "x", "action": "A", "entity_type": "t", "entity_id": "e"}),
]


def _officer_token() -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"officer_id": "officer-001", "password": "officer123"}
    )
    assert resp.status_code == 200
    return resp.json()["token"]


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_officer_token()}"}


def _minimal_pdf_bytes() -> bytes:
    from PyPDF2 import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


class TestProtectedEndpointsRejectAnonymous:
    @pytest.mark.parametrize("path,payload", PROTECTED_POST_ENDPOINTS)
    def test_anonymous_request_is_401(self, anon_client, path, payload):
        if path.endswith("/documents/upload"):
            resp = anon_client.post(
                path,
                files={"file": ("t.pdf", _minimal_pdf_bytes(), "application/pdf")},
                data={"document_type": "tender"},
            )
        else:
            resp = anon_client.post(path, json=payload)
        assert resp.status_code == 401, f"{path} did not reject anonymous access"

    def test_health_remains_public(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_reports_ocr_capability(self):
        resp = client.get("/api/v1/health")
        ocr = resp.json().get("ocr")
        assert isinstance(ocr, dict)
        assert isinstance(ocr.get("available"), bool)
        if ocr.get("available"):
            assert ocr.get("engine") == "tesseract"

    def test_public_read_endpoints_stay_public(self):
        # The frontend architecture relies on unauthenticated reads for
        # documents metadata, regulatory browsing and audit-trail rendering.
        for path in [
            "/api/v1/auth/officers",
            "/api/v1/regulations",
            "/api/v1/regulatory-sources",
            "/api/v1/audit/events",
        ]:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should stay public"


class TestAuthenticatedWorkflow:
    def test_upload_works_when_authenticated(self):
        resp = client.post(
            "/api/v1/documents/upload",
            headers=_auth_headers(),
            files={"file": ("t.pdf", _minimal_pdf_bytes(), "application/pdf")},
            data={"document_type": "tender"},
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "tender"


class TestReportDownload:
    @pytest.fixture(autouse=True)
    def environment(self, tmp_path, monkeypatch):
        storage_root = str(tmp_path / "storage")
        monkeypatch.setattr(document_service, "STORAGE_ROOT", storage_root)
        monkeypatch.setattr(compliance_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance"))
        monkeypatch.setattr(phase8_service, "STORAGE_ROOT", os.path.join(storage_root, "compliance", "phase8"))
        monkeypatch.setattr(regulatory_service, "STORAGE_ROOT", os.path.join(storage_root, "regulatory"))
        regulatory_service.ensure_directories()

        retrieval = RetrievalService(vector_store=LocalVectorStore(os.path.join(storage_root, "retrieval")))
        retrieval_service.set_retrieval_service(retrieval)
        self.headers = _auth_headers()
        self.report = self._make_report()
        yield
        retrieval_service.set_retrieval_service(None)

    def _make_document(self, document_id: str, text: str):
        timestamp = datetime.now(timezone.utc)
        record = DocumentRecord(
            document_id=document_id,
            filename="tender.pdf",
            file_size=100,
            upload_time=timestamp,
            page_count=1,
            processing_status="processed",
            document_type="tender",
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

    def _make_report(self):
        self._make_document(
            "dl-test-doc",
            "The bidder must submit GST registration and PAN.",
        )
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
        create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Bid requirements",
            text="The bidder must submit GST registration and PAN.",
            raw_text="The bidder must submit GST registration and PAN.",
            normalized_text="The bidder must submit GST registration and PAN.",
            page_number=1,
            source_locator="p.1",
            official_url=source["official_url"],
        )
        retrieval_service.get_retrieval_service().build_index()

        resp = client.post(
            "/api/v1/compliance/decision",
            headers=self.headers,
            json={"document_id": "dl-test-doc"},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_download_requires_authentication(self, anon_client):
        resp = anon_client.get(f"/api/v1/compliance/decision/{self.report['report_id']}/download")
        assert resp.status_code == 401

    def test_download_returns_pdf(self):
        resp = client.get(
            f"/api/v1/compliance/decision/{self.report['report_id']}/download",
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert "PolicyGuard_Compliance_Report_" in disposition
        assert ".pdf" in disposition

    def test_download_invalid_report_is_404(self):
        resp = client.get("/api/v1/compliance/decision/no-such-report/download", headers=self.headers)
        assert resp.status_code == 404

    def test_pdf_contains_actual_report_data(self):
        resp = client.get(
            f"/api/v1/compliance/decision/{self.report['report_id']}/download",
            headers=self.headers,
        )
        reader = PdfReader(io.BytesIO(resp.content))
        assert len(reader.pages) >= 1
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # The PDF must carry the real backend report data, not invented content.
        assert self.report["report_id"] in text
        assert self.report["overall_status"] in text
        assert self.report["overall_risk"] in text
        assert str(self.report["total_requirements"]) in text
        assert "PolicyGuard AI" in text
        # Responsible-AI disclaimer must be present.
        assert "advisory only" in text
        assert "authorized officer" in text

        # Every finding's requirement title appears in the PDF.
        titles = [f["requirement_title"] for f in self.report["findings"]]
        assert titles, "report should contain findings"
        assert all(title in text for title in titles), "requirement titles missing from PDF"

    def test_pdf_content_type_and_size_sane(self):
        resp = client.get(
            f"/api/v1/compliance/decision/{self.report['report_id']}/download",
            headers=self.headers,
        )
        assert resp.content.startswith(b"%PDF")
        assert len(resp.content) > 1000


class TestProductionCorsEnforcement:
    def test_production_refuses_wildcard_cors(self, monkeypatch):
        """main.py must refuse to start with CORS_ORIGINS='*' in production."""
        import importlib
        import app.config as config_module
        import app.main as main_module

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("POLICYGUARD_CORS_ORIGINS", "*")
        importlib.reload(config_module)
        with pytest.raises(RuntimeError, match="CORS"):
            importlib.reload(main_module)

    def test_production_accepts_explicit_origins(self, monkeypatch):
        import importlib
        import app.config as config_module
        import app.main as main_module

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("POLICYGUARD_CORS_ORIGINS", "https://policyguardai.vercel.app")
        importlib.reload(config_module)
        importlib.reload(main_module)  # must not raise

    def test_configured_origin_receives_cors_headers(self):
        from app.config import settings

        origin = settings.cors_origins.split(",")[0].strip()
        resp = client.options(
            "/api/v1/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            assert resp.headers.get("access-control-allow-origin") == origin


class TestProductionSecretEnforcement:
    def test_production_requires_auth_secret(self, monkeypatch):
        import app.auth.service as auth_service

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("POLICYGUARD_AUTH_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="POLICYGUARD_AUTH_SECRET"):
            auth_service._signing_key()

    def test_production_requires_demo_password(self, monkeypatch):
        import app.auth.service as auth_service

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("POLICYGUARD_DEMO_PASSWORD", raising=False)
        with pytest.raises(RuntimeError, match="POLICYGUARD_DEMO_PASSWORD"):
            auth_service._resolve_demo_password()

    def test_production_uses_env_configured_password(self, monkeypatch):
        import app.auth.service as auth_service

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("POLICYGUARD_DEMO_PASSWORD", "strong-env-password")
        assert auth_service._resolve_demo_password() == "strong-env-password"

    def test_development_falls_back_to_demo_password(self, monkeypatch):
        import app.auth.service as auth_service

        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("POLICYGUARD_DEMO_PASSWORD", raising=False)
        assert auth_service._resolve_demo_password() == "officer123"

    def test_demo_password_not_printed_in_login_responses(self):
        resp = client.post(
            "/api/v1/auth/login", json={"officer_id": "officer-001", "password": "officer123"}
        )
        assert resp.status_code == 200
        assert "officer123" not in resp.text
