import os
import uuid
import json
from datetime import datetime
from PyPDF2 import PdfReader
from app.config import settings
from .models import DocumentRecord, Page, PageBlock, PageElement
from .ocr_service import ocr_service


STORAGE_ROOT = settings.storage_path


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _coerce_elements(elements):
    normalized = []
    for element in elements or []:
        if isinstance(element, PageElement):
            normalized.append(element)
        else:
            normalized.append(PageElement(**element))
    return normalized


def process_pdf(file_path: str, filename: str) -> DocumentRecord:
    document_id = str(uuid.uuid4())
    doc_dir = os.path.join(STORAGE_ROOT, "documents", document_id)
    ensure_dir(doc_dir)

    upload_time = datetime.utcnow()
    record = DocumentRecord(
        document_id=document_id,
        filename=filename,
        file_size=os.path.getsize(file_path),
        upload_time=upload_time,
        page_count=0,
        processing_status="processing",
        processing_error=None,
        created_at=upload_time,
    )

    pages_dir = os.path.join(doc_dir, "pages")
    ensure_dir(pages_dir)

    try:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        record.page_count = page_count
        page_methods = []

        for i, page in enumerate(reader.pages, start=1):
            text = ""
            ocr_elements = []
            ocr_required = False
            extraction_method = "text"

            try:
                extracted = page.extract_text() or ""
            except Exception:
                extracted = ""

            if extracted and extracted.strip():
                text = extracted.strip()
            else:
                ocr_required = True

            if ocr_required:
                try:
                    ocr_result = ocr_service.extract_page(file_path, i, document_id)
                    ocr_text = (ocr_result.text or "").strip()
                    if ocr_text:
                        if text and text != ocr_text:
                            text = f"{text}\n{ocr_text}".strip()
                            extraction_method = "mixed"
                        else:
                            text = ocr_text
                            extraction_method = "ocr"
                        ocr_elements = _coerce_elements(ocr_result.elements)
                    else:
                        text = text or ""
                        extraction_method = "ocr" if text else "text"
                except Exception:
                    text = text or ""
                    extraction_method = "text" if text else "ocr"

            if not text:
                extraction_method = "ocr"

            page_obj = Page(
                document_id=document_id,
                page_number=i,
                text=text,
                extraction_method=extraction_method,
                ocr_required=ocr_required,
                processing_status="processed" if not ocr_required else "ocr_required",
                blocks=[PageBlock(text=text)] if text else [],
                elements=ocr_elements if ocr_elements else [],
            )
            page_methods.append(extraction_method)

            page_path = os.path.join(pages_dir, f"page_{i}.json")
            save_json(page_path, page_obj.model_dump(mode="json"))

        if page_methods and all(method == "text" for method in page_methods):
            record.extraction_method = "text"
        elif page_methods and any(method == "ocr" for method in page_methods):
            record.extraction_method = "ocr" if not any(method == "mixed" for method in page_methods) else "mixed"
        else:
            record.extraction_method = "mixed"

        record.processing_status = "processed"
        meta_path = os.path.join(doc_dir, "metadata.json")
        save_json(meta_path, record.model_dump(mode="json"))
        return record

    except Exception as e:
        record.processing_status = "error"
        record.processing_error = str(e)
        meta_path = os.path.join(doc_dir, "metadata.json")
        save_json(meta_path, record.model_dump(mode="json"))
        raise


def get_document_record(document_id: str) -> DocumentRecord | None:
    meta_path = os.path.join(STORAGE_ROOT, "documents", document_id, "metadata.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return DocumentRecord(**data)


def get_page(document_id: str, page_number: int) -> Page | None:
    page_path = os.path.join(STORAGE_ROOT, "documents", document_id, "pages", f"page_{page_number}.json")
    if not os.path.exists(page_path):
        return None
    with open(page_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return Page(**data)


def get_page_elements(document_id: str, page_number: int):
    page = get_page(document_id, page_number)
    if page is None:
        return []
    return [element.model_dump(mode="json") for element in page.elements]
