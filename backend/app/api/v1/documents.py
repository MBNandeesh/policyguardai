from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import logging
import os
from app.config import settings
from app.api.v1.auth import require_officer
from app.documents import service
from datetime import datetime, timezone

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
CHUNK_SIZE = 1024 * 1024  # stream 1MB at a time to keep memory usage low


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("tender"),
    officer=Depends(require_officer),
):
    # validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    document_type = (document_type or "tender").strip().lower()
    if document_type not in ("tender", "bidder"):
        raise HTTPException(status_code=400, detail="document_type must be 'tender' or 'bidder'")

    storage_root = settings.storage_path
    os.makedirs(storage_root, exist_ok=True)
    # save original (streamed to disk so large files don't blow up memory)
    temp_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    doc_dir = os.path.join(storage_root, "uploads", temp_id)
    os.makedirs(doc_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(doc_dir, safe_name)

    total = 0
    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File too large (max 200MB)",
                    )
                f.write(chunk)
    except HTTPException:
        os.remove(file_path)
        raise
    if total == 0:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Empty file")

    # try processing
    try:
        record = service.process_pdf(file_path, safe_name, document_type=document_type)
        return JSONResponse(status_code=200, content=record.model_dump(mode="json"))
    except Exception:
        # Log the full failure server-side; never echo raw exception text
        # back to the client (it can leak filesystem paths and internals).
        logger.exception("PDF processing failed for %s", safe_name)
        raise HTTPException(status_code=500, detail="Document processing failed")


@router.get("/documents/{document_id}/status")
def document_status(document_id: str):
    rec = service.get_document_record(document_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return rec.model_dump(mode="json")


@router.get("/documents/{document_id}")
def document_metadata(document_id: str):
    rec = service.get_document_record(document_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return rec.model_dump(mode="json")


@router.get("/documents/{document_id}/pages/{page_number}")
def document_page(document_id: str, page_number: int):
    page = service.get_page(document_id, page_number)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page.model_dump(mode="json")


@router.get("/documents/{document_id}/pages/{page_number}/elements")
def document_page_elements(document_id: str, page_number: int):
    page = service.get_page(document_id, page_number)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return [element.model_dump(mode="json") for element in page.elements]
