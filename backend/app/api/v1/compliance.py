from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.compliance.models import AnalysisRequest, RequirementEvaluationRequest
from app.compliance.service import extract_requirements_for_document
from app.compliance.service import (
    analyze,
    evaluate_requirements_for_document,
    get_analysis,
    get_findings,
    get_requirement_assessment,
    get_requirement_assessments_for_analysis,
    get_requirement_report,
)

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


@router.post("/compliance/requirements/evaluate")
def evaluate_requirements(request: RequirementEvaluationRequest) -> Dict[str, Any]:
    try:
        return evaluate_requirements_for_document(
            document_id=request.document_id,
            requirement_ids=request.requirement_ids,
            top_k=request.top_k,
        )
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


@router.get("/compliance/analyses/{analysis_id}/requirements")
def analysis_requirements(analysis_id: str):
    assessments = get_requirement_assessments_for_analysis(analysis_id)
    return [assessment.model_dump(mode="json") for assessment in assessments]


@router.get("/compliance/requirements/assessments/{assessment_id}")
def requirement_assessment_detail(assessment_id: str):
    assessment = get_requirement_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Requirement assessment not found")
    return assessment.model_dump(mode="json")


@router.get("/compliance/analyses/{analysis_id}/report")
def requirement_report(analysis_id: str):
    report = get_requirement_report(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Requirement report not found")
    return report.model_dump(mode="json")
