import logging
from typing import Any, Dict, List

from pydantic import Field

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.v1.auth import require_officer
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
from app.compliance.phase8_service import (
    generate_compliance_decision_report,
    get_compliance_decision_report,
    get_requirement_explanation,
    create_and_persist_explanations,
)
from app.compliance.paired_service import evaluate_requirements_paired

router = APIRouter()
logger = logging.getLogger(__name__)


def _download_response(report_id: str) -> Response:
    """Generate the officer-facing PDF for a compliance decision report."""
    from app.compliance.report_pdf import render_decision_report_pdf

    pdf_bytes = render_decision_report_pdf(report_id)
    filename = f"PolicyGuard_Compliance_Report_{report_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class DocumentRequest(BaseModel):
    document_id: str


@router.post("/compliance/requirements/extract")
def extract_requirements(req: DocumentRequest, officer=Depends(require_officer)):
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
def create_analysis(request: AnalysisRequest, officer=Depends(require_officer)) -> Dict[str, Any]:
    try:
        return analyze(request).model_dump(mode="json")
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/compliance/requirements/evaluate")
def evaluate_requirements(request: RequirementEvaluationRequest, officer=Depends(require_officer)) -> Dict[str, Any]:
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


# Phase 8: Compliance Decision, Risk, and Explainability Layer


@router.post("/compliance/decision")
def generate_decision(request: DocumentRequest, officer=Depends(require_officer)) -> Dict[str, Any]:
    """
    Generate a compliance decision report for a document's requirement assessments.
    
    This endpoint aggregates Phase 7 requirement assessments into an overall
    compliance decision with risk classification and human review queue.
    """
    document_id = (request.document_id or "").strip()
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    try:
        # Get or create assessments for this document covering all applicable requirements
        payload = evaluate_requirements_for_document(
            document_id=document_id,
            requirement_ids=None,
        )
        analysis_id = payload.get("analysis_id")
        
        # Generate Phase 8 decision report
        report = generate_compliance_decision_report(analysis_id, document_id)
        
        # Create and persist explanations
        create_and_persist_explanations(analysis_id, document_id)
        
        return report.model_dump(mode="json")
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)
    except Exception:
        logger.exception("Compliance decision generation failed for document_id=%s", document_id)
        raise HTTPException(status_code=500, detail="Decision generation failed")


class PairedDecisionRequest(BaseModel):
    tender_document_id: str
    bidder_document_ids: List[str] = Field(default_factory=list)


@router.post("/compliance/decision/paired")
def generate_paired_decision(request: PairedDecisionRequest, officer=Depends(require_officer)) -> Dict[str, Any]:
    """
    Generate a compliance decision report by mapping requirements from the
    tender PDF onto evidence gathered from BOTH the tender and bidder PDF(s).

    Requirements are extracted from the tender document. Evidence is collected
    from the tender and each bidder document, evaluated with the same
    deterministic grounded logic, and aggregated into a Phase 8 decision
    report with risk classification and human review queue.
    """
    tender_document_id = (request.tender_document_id or "").strip()
    if not tender_document_id:
        raise HTTPException(status_code=400, detail="tender_document_id is required")
    try:
        payload = evaluate_requirements_paired(
            tender_document_id=tender_document_id,
            bidder_document_ids=[b for b in (request.bidder_document_ids or []) if (b or "").strip()],
        )
        analysis_id = payload["analysis_id"]

        report = generate_compliance_decision_report(analysis_id, tender_document_id)
        create_and_persist_explanations(analysis_id, tender_document_id)

        return {
            "report": report.model_dump(mode="json"),
            "analysis_id": analysis_id,
            "tender_document_id": tender_document_id,
            "bidder_document_ids": payload.get("bidder_document_ids", []),
        }
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)
    except Exception:
        logger.exception("Paired compliance decision failed for tender_document_id=%s", tender_document_id)
        raise HTTPException(status_code=500, detail="Paired decision generation failed")


@router.get("/compliance/decision/{report_id}")
def get_decision_report(report_id: str) -> Dict[str, Any]:
    """Retrieve a compliance decision report."""
    report = get_compliance_decision_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Compliance decision report not found")
    return report.model_dump(mode="json")


@router.get("/compliance/requirements/{requirement_id}/explanation")
def get_requirement_explanation_endpoint(
    requirement_id: str, analysis_id: str
) -> Dict[str, Any]:
    """
    Retrieve detailed explanation for a requirement evaluation.
    
    Query parameters:
    - analysis_id: The analysis ID for which the explanation applies
    """
    explanation = get_requirement_explanation(requirement_id, analysis_id)
    if explanation is None:
        raise HTTPException(status_code=404, detail="Requirement explanation not found")
    return explanation.model_dump(mode="json")


@router.get("/compliance/decision/{report_id}/download")
def download_decision_report(report_id: str, officer=Depends(require_officer)):
    """Download a compliance decision report as a PDF (officer-authenticated).

    The PDF is rendered from the persisted backend report data only - the
    decision engine is not re-run and no new information is invented.
    """
    if get_compliance_decision_report(report_id) is None:
        raise HTTPException(status_code=404, detail="Compliance decision report not found")
    try:
        return _download_response(report_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("PDF render failed for report_id=%s", report_id)
        raise HTTPException(status_code=500, detail="Report PDF generation failed")
