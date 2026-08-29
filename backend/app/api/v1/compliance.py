from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.compliance.service import extract_requirements_for_document
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.compliance.models import AnalysisRequest
from app.compliance.service import analyze, get_analysis, get_findings

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
@router.post("/compliance/analyze")
def create_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    try:
        return analyze(request).model_dump(mode="json")
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/compliance/analyses/{analysis_id}")
def analysis_detail(analysis_id: str) -> Dict[str, Any]:
    result = get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result.model_dump(mode="json")


@router.get("/compliance/analyses/{analysis_id}/findings")
def analysis_findings(analysis_id: str):
    if get_analysis(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return [finding.model_dump(mode="json") for finding in get_findings(analysis_id)]
