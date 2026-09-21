import io
import json
import os
import shutil
import subprocess

import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from reportlab.lib.utils import ImageReader
from app.documents.ocr_service import OCRPageResult
from app.main import app

from reportlab.pdfgen import canvas


client = TestClient(app)


class FakeOCRService:
    def extract_page(self, file_path, page_number, document_id):
        return OCRPageResult(
            text=f"OCR page {page_number}",
            elements=[
                {
                    "element_id": "elem-1",
                    "document_id": document_id,
                    "page_number": page_number,
                    "type": "paragraph",
                    "text": f"OCR page {page_number}",
                    "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 40},
                    "confidence": 0.94,
                    "reading_order": 1,
                    "parent_id": None,
                    "metadata": {"source": "ocr"},
                }
            ],
            confidence=0.94,
        )


def make_pdf_with_text(pages=1, texts=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    texts = texts or [f"Page {i}" for i in range(1, pages + 1)]
    for t in texts:
        c.drawString(100, 750, t)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def make_pdf_blank_page():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def make_scanned_pdf_with_text(text="PolicyGuard OCR Verified"):
    img = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(img)
    draw.text((120, 350), text, fill="black")
    png = io.BytesIO()
    img.save(png, format="PNG")
    png.seek(0)

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawImage(ImageReader(png), 50, 200, width=1000, height=180)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def make_scanned_document_fixture():
    img = Image.new("RGB", (1800, 1100), "white")
    draw = ImageDraw.Draw(img)
    draw.text((120, 120), "PolicyGuard AI", fill="black")
    draw.text((120, 220), "Section 1: Important Update", fill="black")
    draw.text((120, 300), "This document explains the policy review process.", fill="black")
    draw.text((120, 400), "1. Review the document carefully.", fill="black")
    draw.text((120, 470), "2. Check the numbered list and table values.", fill="black")
    draw.text((120, 620), "A | B | C", fill="black")
    draw.text((120, 690), "1 | 2 | 3", fill="black")
    draw.text((120, 760), "4 | 5 | 6", fill="black")

    png = io.BytesIO()
    img.save(png, format="PNG")
    png.seek(0)

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawImage(ImageReader(png), 50, 80, width=1600, height=900)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def test_upload_normal_pdf(tmp_path):
    data = make_pdf_with_text(pages=1, texts=["Hello from PolicyGuard"])
    files = {"file": ("test.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    json = resp.json()
    assert json["page_count"] == 1


def test_upload_multi_page_pdf():
    data = make_pdf_with_text(pages=3)
    files = {"file": ("multi.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    json = resp.json()
    assert json["page_count"] == 3


def test_scanned_page_handling():
    # blank page should be marked for OCR
    data = make_pdf_blank_page()
    files = {"file": ("blank.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    json = resp.json()
    doc_id = json["document_id"]
    page = client.get(f"/api/v1/documents/{doc_id}/pages/1").json()
    assert page["ocr_required"] is True


def test_invalid_file():
    files = {"file": ("notpdf.txt", b"hello", "text/plain")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 400


def test_corrupted_file():
    files = {"file": ("bad.pdf", b"%%NotAPDF%%", "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 500


def test_page_numbering():
    data = make_pdf_with_text(pages=2, texts=["First", "Second"])
    files = {"file": ("two.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    json = resp.json()
    doc_id = json["document_id"]
    p1 = client.get(f"/api/v1/documents/{doc_id}/pages/1").json()
    p2 = client.get(f"/api/v1/documents/{doc_id}/pages/2").json()
    assert p1["page_number"] == 1
    assert p2["page_number"] == 2


def test_digital_pdf_uses_text_extraction():
    data = make_pdf_with_text(pages=1, texts=["Hello from PolicyGuard"])
    files = {"file": ("text.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    page = client.get(f"/api/v1/documents/{resp.json()['document_id']}/pages/1").json()
    assert page["text"] == "Hello from PolicyGuard"
    assert page["extraction_method"] == "text"


def test_scanned_pdf_uses_ocr_fallback(monkeypatch):
    from app import documents as documents_module

    monkeypatch.setattr(documents_module.service, "ocr_service", FakeOCRService())
    data = make_pdf_blank_page()
    files = {"file": ("scanned.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    page = client.get(f"/api/v1/documents/{resp.json()['document_id']}/pages/1").json()
    assert page["text"] == "OCR page 1"
    assert page["extraction_method"] == "ocr"
    assert page["ocr_required"] is True


def test_page_elements_endpoint_returns_structured_items(monkeypatch):
    from app import documents as documents_module

    monkeypatch.setattr(documents_module.service, "ocr_service", FakeOCRService())
    data = make_pdf_blank_page()
    files = {"file": ("elements.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    doc_id = resp.json()["document_id"]
    elements = client.get(f"/api/v1/documents/{doc_id}/pages/1/elements").json()
    assert isinstance(elements, list)
    assert elements[0]["type"] == "paragraph"
    assert elements[0]["text"] == "OCR page 1"
    assert elements[0]["bbox"]["x1"] == 10


def _tesseract_available() -> bool:
    configured = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if not configured or not os.path.exists(configured):
        return False
    try:
        res = subprocess.run([configured, "--version"], capture_output=True, text=True, timeout=30)
        return res.returncode == 0 and "tesseract" in res.stdout.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _tesseract_available(), reason="Tesseract OCR binary not installed on this machine")
def test_tesseract_runtime_available():
    configured = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    assert configured is not None
    res = subprocess.run([configured, "--version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "tesseract" in res.stdout.lower()


@pytest.mark.skipif(not _tesseract_available(), reason="Tesseract OCR binary not installed on this machine")
def test_real_scanned_pdf_ocr_pipeline():
    data = make_scanned_document_fixture()
    files = {"file": ("scanned_real.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["processing_status"] == "processed"
    doc_id = payload["document_id"]
    page = client.get(f"/api/v1/documents/{doc_id}/pages/1").json()
    text = page["text"]
    assert text
    assert page["page_number"] == 1
    assert page["extraction_method"] == "ocr"
    assert page["ocr_required"] is True
    # Byte-faithful extraction: the OCR text must contain words actually
    # drawn on the page. No inserted branding is asserted.
    assert "document" in text.lower() or "review" in text.lower()
    assert "Important" in text or "Update" in text
    elements = client.get(f"/api/v1/documents/{doc_id}/pages/1/elements").json()
    assert elements
    first = elements[0]
    assert first["page_number"] == 1
    assert first["text"]
    assert "bbox" in first and first["bbox"]
    assert "confidence" in first and first["confidence"] is not None
    assert first["reading_order"] >= 1


def test_ocr_normalization_is_whitespace_only():
    from app.documents.ocr_service import LocalTesseractOCR

    # Fabrication guard: text must never gain or lose words, only whitespace.
    noisy = "Line  one\n\n\nLine   two\r\nLine three"
    normalized = LocalTesseractOCR.normalize_ocr_text(noisy)
    assert "".join(normalized.split()) == "".join(noisy.split())
    assert "PolicyGuard" not in normalized
    assert LocalTesseractOCR.normalize_ocr_text("") == ""


def test_digital_pdf_skips_ocr(monkeypatch):
    calls = {"count": 0}

    def fail_if_called(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("OCR should not run for digital PDF with embedded text")

    monkeypatch.setattr("app.documents.service.ocr_service.extract_page", fail_if_called)
    data = make_pdf_with_text(pages=1, texts=["Digital PDF text"])
    files = {"file": ("digital.pdf", data, "application/pdf")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 200
    page = client.get(f"/api/v1/documents/{resp.json()['document_id']}/pages/1").json()
    assert page["text"] == "Digital PDF text"
    assert page["extraction_method"] in {"text", "mixed"}
    assert calls["count"] == 0
