from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import os
from app.config import settings
from app.documents import service
from datetime import datetime

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    # validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    storage_root = settings.storage_path
    os.makedirs(storage_root, exist_ok=True)
    # save original
    temp_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    doc_dir = os.path.join(storage_root, "uploads", temp_id)
    os.makedirs(doc_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(doc_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    # try processing
    try:
        record = service.process_pdf(file_path, safe_name)
        return JSONResponse(status_code=200, content=record.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


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
