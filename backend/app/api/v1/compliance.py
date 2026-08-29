from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.compliance.service import extract_requirements_for_document

router = APIRouter()


class DocumentRequest(BaseModel):
    document_id: str


@router.post("/compliance/requirements/extract")
def extract_requirements(req: DocumentRequest):
    document_id = (req.document_id or "").strip()
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    try:
        payload = extract_requirements_for_document(document_id)
        return JSONResponse(status_code=200, content=payload)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Extraction error")
