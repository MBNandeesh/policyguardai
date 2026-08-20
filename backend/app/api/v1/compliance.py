from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.compliance.models import AnalysisRequest
from app.compliance.service import analyze, get_analysis, get_findings

router = APIRouter()


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