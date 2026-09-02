"""
Phase 8: Compliance Decision, Risk, and Explainability Layer Service

This module implements deterministic logic for:
- Decision aggregation from requirement assessments
- Risk classification
- Explainability and evidence tracing
- Human review queue generation
- Final compliance report creation
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.compliance.models import (
    FindingStatus,
    RequirementAssessment,
    Severity,
)
from app.compliance.service import (
    get_requirement_assessment,
    get_requirement_assessments_for_analysis,
    get_requirement_report,
)

from .phase8_models import (
    ComplianceDecisionReport,
    ComplianceFinding,
    EvidenceTrace,
    HumanReviewItem,
    OverallComplianceStatus,
    RequirementExplanation,
    RiskLevel,
)


STORAGE_ROOT = os.path.join(settings.storage_path, "compliance", "phase8")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _phase8_report_path(report_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "reports", f"{report_id}.json")


def _phase8_explanation_path(requirement_id: str, analysis_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "explanations", f"{analysis_id}_{requirement_id}.json")


def _phase8_review_queue_path(analysis_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "review_queues", f"{analysis_id}.json")


def _write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def _read(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _classify_risk(
    assessment: RequirementAssessment,
    mandatory: bool,
    confidence: Optional[str] = None,
) -> RiskLevel:
    """
    Deterministically classify risk based on:
    - Evaluation status
    - Mandatory flag
    - Severity
    - Confidence level
    """
    status = assessment.status
    severity = assessment.severity

    # CRITICAL risks
    if status == FindingStatus.POTENTIAL_NON_COMPLIANCE and mandatory and severity in (Severity.CRITICAL, Severity.HIGH):
        return RiskLevel.CRITICAL
    if status == FindingStatus.POTENTIAL_NON_COMPLIANCE and mandatory:
        return RiskLevel.HIGH

    # HIGH risks
    if status == FindingStatus.INSUFFICIENT_EVIDENCE and mandatory and severity in (Severity.CRITICAL, Severity.HIGH):
        return RiskLevel.HIGH
    if status == FindingStatus.REQUIRES_REVIEW and mandatory and severity == Severity.HIGH:
        return RiskLevel.HIGH
    if status == FindingStatus.UNKNOWN and mandatory:
        return RiskLevel.HIGH

    # MEDIUM risks
    if status == FindingStatus.INSUFFICIENT_EVIDENCE and mandatory:
        return RiskLevel.MEDIUM
    if status == FindingStatus.REQUIRES_REVIEW and mandatory:
        return RiskLevel.MEDIUM
    if status == FindingStatus.REQUIRES_REVIEW and not mandatory and confidence == "LOW":
        return RiskLevel.MEDIUM

    # LOW risks
    if status == FindingStatus.COMPLIANT and mandatory:
        return RiskLevel.LOW
    if status == FindingStatus.NOT_APPLICABLE:
        return RiskLevel.INFO
    if status == FindingStatus.COMPLIANT and not mandatory:
        return RiskLevel.INFO

    # Default
    return RiskLevel.MEDIUM


def _derive_overall_status(assessments: List[RequirementAssessment]) -> Tuple[OverallComplianceStatus, RiskLevel]:
    """
    Deterministically derive overall compliance status from requirement assessments.

    Rules:
    - Any CRITICAL/HIGH unresolved non-compliance => HIGH_RISK
    - Unresolved potential non-compliance => REVIEW_REQUIRED
    - Insufficient evidence or UNKNOWN => REVIEW_REQUIRED
    - All applicable requirements compliant => COMPLIANT
    - Not-applicable requirements don't negatively affect result
    """
    if not assessments:
        return OverallComplianceStatus.UNKNOWN, RiskLevel.INFO

    # Filter to applicable requirements
    applicable = [a for a in assessments if a.status != FindingStatus.NOT_APPLICABLE]

    if not applicable:
        return OverallComplianceStatus.COMPLIANT, RiskLevel.INFO

    # Check for critical/high non-compliance
    for assessment in applicable:
        if assessment.status == FindingStatus.POTENTIAL_NON_COMPLIANCE:
            if assessment.severity in (Severity.CRITICAL, Severity.HIGH):
                return OverallComplianceStatus.HIGH_RISK, RiskLevel.CRITICAL
            else:
                return OverallComplianceStatus.REVIEW_REQUIRED, RiskLevel.HIGH

    # Check for unresolved/unknown statuses
    for assessment in applicable:
        if assessment.status in (
            FindingStatus.INSUFFICIENT_EVIDENCE,
            FindingStatus.UNKNOWN,
            FindingStatus.REQUIRES_REVIEW,
        ):
            return OverallComplianceStatus.REVIEW_REQUIRED, RiskLevel.HIGH

    # All applicable requirements are compliant
    all_compliant = all(a.status == FindingStatus.COMPLIANT for a in applicable)
    if all_compliant:
        return OverallComplianceStatus.COMPLIANT, RiskLevel.LOW

    return OverallComplianceStatus.UNKNOWN, RiskLevel.MEDIUM


def _build_evidence_trace(assessment: RequirementAssessment) -> Optional[EvidenceTrace]:
    """Build evidence traceability from requirement to decision."""
    if not assessment:
        return None

    doc_evidence_summary = None
    if assessment.document_evidence:
        doc_evidence_summary = {
            "count": len(assessment.document_evidence),
            "pages": [de.page_number for de in assessment.document_evidence],
            "locators": [de.source_locator for de in assessment.document_evidence],
        }

    reg_evidence_summary = None
    if assessment.regulatory_basis:
        reg_evidence_summary = {
            "count": len(assessment.regulatory_basis),
            "sources": list(set(re.source_id for re in assessment.regulatory_basis)),
            "provisions": [
                {
                    "provision_id": re.provision_id,
                    "provision_number": re.provision_number,
                    "url": re.official_url,
                }
                for re in assessment.regulatory_basis
            ],
        }

    return EvidenceTrace(
        requirement_id=assessment.requirement_id,
        requirement_title=assessment.title,
        source_document_id=assessment.document_id,
        source_page=None,  # Not available at assessment level
        source_section=None,
        source_text=None,
        document_evidence=doc_evidence_summary,
        regulatory_evidence=reg_evidence_summary,
        evaluation_status=assessment.status.value,
        evaluation_confidence=assessment.confidence,
    )


def _build_requirement_explanation(assessment: RequirementAssessment) -> RequirementExplanation:
    """Build detailed explanation for a requirement evaluation."""
    risk_level = _classify_risk(assessment, mandatory=True, confidence=assessment.confidence)

    # Determine reason
    reason = assessment.explanation or "No explanation available."

    # Evidence summary
    evidence_parts = []
    if assessment.document_evidence:
        evidence_parts.append(
            f"Document evidence from {len(assessment.document_evidence)} section(s) ("
            + ", ".join(de.source_locator for de in assessment.document_evidence)
            + ")"
        )
    if assessment.regulatory_basis:
        evidence_parts.append(
            f"Regulatory authority from {len(assessment.regulatory_basis)} provision(s)"
        )
    evidence_summary = "; ".join(evidence_parts) if evidence_parts else "No evidence available"

    # Regulatory info
    reg_authority = None
    reg_reference = None
    reg_url = None
    if assessment.regulatory_basis:
        first_reg = assessment.regulatory_basis[0]
        reg_reference = first_reg.provision_number
        reg_url = first_reg.official_url or None

    # Human review reason
    human_review_required = assessment.requires_human_review
    human_review_reason = None
    if human_review_required:
        if assessment.status == FindingStatus.REQUIRES_REVIEW:
            human_review_reason = "Requirement evaluation requires human compliance officer review"
        elif assessment.status == FindingStatus.INSUFFICIENT_EVIDENCE:
            human_review_reason = "Insufficient evidence to determine compliance status"
        elif assessment.status == FindingStatus.POTENTIAL_NON_COMPLIANCE:
            human_review_reason = "Potential non-compliance detected; human review required"

    evidence_trace = _build_evidence_trace(assessment)

    return RequirementExplanation(
        requirement_id=assessment.requirement_id,
        requirement_title=assessment.title,
        requirement_description=assessment.description,
        category="UNKNOWN",  # Not stored in assessment
        mandatory=True,  # Not stored in assessment
        evaluation_status=assessment.status.value,
        risk_level=risk_level,
        reason=reason,
        evidence_summary=evidence_summary,
        source_document_id=assessment.document_id,
        source_page=None,
        source_section=None,
        regulatory_authority=reg_authority,
        regulatory_reference=reg_reference,
        regulatory_url=reg_url,
        confidence=assessment.confidence,
        human_review_required=human_review_required,
        requires_review_reason=human_review_reason,
        evidence_trace=evidence_trace,
        assessment_id=assessment.assessment_id,
        created_at=_now(),
    )


def _build_human_review_items(assessments: List[RequirementAssessment]) -> List[HumanReviewItem]:
    """Identify items requiring human officer review."""
    review_items: List[HumanReviewItem] = []
    priority = 1

    # Sort by priority: CRITICAL/HIGH first, then REQUIRES_REVIEW, then INSUFFICIENT_EVIDENCE
    sorted_assessments = sorted(
        assessments,
        key=lambda a: (
            a.status not in (FindingStatus.POTENTIAL_NON_COMPLIANCE, FindingStatus.REQUIRES_REVIEW),
            a.severity != Severity.CRITICAL,
            a.severity != Severity.HIGH,
        ),
    )

    for assessment in sorted_assessments:
        # Include items that require review
        if not assessment.requires_human_review:
            continue

        risk_level = _classify_risk(assessment, mandatory=True, confidence=assessment.confidence)

        reason = ""
        suggested_action = ""

        if assessment.status == FindingStatus.POTENTIAL_NON_COMPLIANCE:
            reason = "Potential non-compliance detected"
            suggested_action = "Review evidence and make compliance determination"
        elif assessment.status == FindingStatus.REQUIRES_REVIEW:
            reason = "Compliance evaluation requires human review"
            suggested_action = "Review regulatory basis and make compliance determination"
        elif assessment.status == FindingStatus.INSUFFICIENT_EVIDENCE:
            reason = "Insufficient evidence to determine compliance"
            suggested_action = "Request additional evidence or mark as non-compliant"
        elif assessment.status == FindingStatus.UNKNOWN:
            reason = "Compliance status unknown"
            suggested_action = "Investigate and determine compliance status"

        evidence_summary = ""
        if assessment.document_evidence or assessment.regulatory_basis:
            evidence_parts = []
            if assessment.document_evidence:
                evidence_parts.append(f"Document: {len(assessment.document_evidence)} section(s)")
            if assessment.regulatory_basis:
                evidence_parts.append(f"Regulatory: {len(assessment.regulatory_basis)} provision(s)")
            evidence_summary = ", ".join(evidence_parts)

        item = HumanReviewItem(
            review_item_id=str(uuid.uuid4()),
            requirement_id=assessment.requirement_id,
            requirement_title=assessment.title,
            assessment_id=assessment.assessment_id,
            document_id=assessment.document_id,
            status=assessment.status.value,
            risk_level=risk_level,
            reason=reason,
            priority=priority,
            evidence_summary=evidence_summary,
            document_evidence_available=bool(assessment.document_evidence),
            regulatory_evidence_available=bool(assessment.regulatory_basis),
            confidence_level=assessment.confidence,
            suggested_action=suggested_action,
            created_at=_now(),
        )
        review_items.append(item)
        priority += 1

    return review_items


def _build_compliance_findings(assessments: List[RequirementAssessment]) -> List[ComplianceFinding]:
    """Build compliance findings from requirement assessments."""
    findings: List[ComplianceFinding] = []

    for assessment in assessments:
        risk_level = _classify_risk(assessment, mandatory=True, confidence=assessment.confidence)

        finding = ComplianceFinding(
            finding_id=str(uuid.uuid4()),
            requirement_id=assessment.requirement_id,
            requirement_title=assessment.title,
            status=assessment.status.value,
            risk_level=risk_level,
            severity=assessment.severity.value,
            explanation=assessment.explanation,
            evidence_available=bool(assessment.document_evidence or assessment.regulatory_basis),
            regulatory_grounding=bool(assessment.regulatory_basis),
            source_document_id=assessment.document_id,
            source_page=None,
            mandatory=True,  # Not stored in assessment
        )
        findings.append(finding)

    return findings


def generate_compliance_decision_report(analysis_id: str, document_id: str) -> ComplianceDecisionReport:
    """
    Generate a final compliance decision report from requirement assessments.
    """
    # Retrieve all assessments for this analysis
    assessments = get_requirement_assessments_for_analysis(analysis_id)

    if not assessments:
        # No assessments - create a report indicating unknown status
        return ComplianceDecisionReport(
            report_id=str(uuid.uuid4()),
            document_id=document_id,
            analysis_id=analysis_id,
            overall_status=OverallComplianceStatus.UNKNOWN,
            overall_risk=RiskLevel.INFO,
            total_requirements=0,
            applicable_requirements=0,
            findings=[],
            high_priority_items=[],
            human_review_queue=[],
            executive_summary="No requirement assessments available.",
            generated_at=_now(),
        )

    # Count statuses
    status_counts = {
        FindingStatus.COMPLIANT: 0,
        FindingStatus.POTENTIAL_NON_COMPLIANCE: 0,
        FindingStatus.INSUFFICIENT_EVIDENCE: 0,
        FindingStatus.REQUIRES_REVIEW: 0,
        FindingStatus.NOT_APPLICABLE: 0,
        FindingStatus.UNKNOWN: 0,
    }
    for assessment in assessments:
        status_counts[assessment.status] = status_counts.get(assessment.status, 0) + 1

    # Classify risk for each assessment
    risk_counts = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 0,
        RiskLevel.MEDIUM: 0,
        RiskLevel.LOW: 0,
        RiskLevel.INFO: 0,
    }
    for assessment in assessments:
        risk = _classify_risk(assessment, mandatory=True, confidence=assessment.confidence)
        risk_counts[risk] += 1

    # Derive overall status
    overall_status, overall_risk = _derive_overall_status(assessments)

    # Build findings
    findings = _build_compliance_findings(assessments)

    # Build human review queue
    review_items = _build_human_review_items(assessments)

    # High priority items (CRITICAL/HIGH risk)
    high_priority = [item for item in review_items if item.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)]

    # Generate key findings
    key_findings: List[str] = []
    if status_counts[FindingStatus.POTENTIAL_NON_COMPLIANCE] > 0:
        key_findings.append(
            f"{status_counts[FindingStatus.POTENTIAL_NON_COMPLIANCE]} requirement(s) show potential non-compliance"
        )
    if status_counts[FindingStatus.INSUFFICIENT_EVIDENCE] > 0:
        key_findings.append(
            f"{status_counts[FindingStatus.INSUFFICIENT_EVIDENCE]} requirement(s) lack sufficient evidence"
        )
    if status_counts[FindingStatus.REQUIRES_REVIEW] > 0:
        key_findings.append(
            f"{status_counts[FindingStatus.REQUIRES_REVIEW]} requirement(s) require human review"
        )
    if status_counts[FindingStatus.COMPLIANT] > 0:
        key_findings.append(
            f"{status_counts[FindingStatus.COMPLIANT]} requirement(s) are compliant"
        )

    # Critical issues
    critical_issues: List[str] = []
    for finding in findings:
        if finding.risk_level == RiskLevel.CRITICAL:
            critical_issues.append(
                f"CRITICAL: {finding.requirement_title} - {finding.explanation}"
            )

    # Executive summary
    applicable_count = len(
        [a for a in assessments if a.status != FindingStatus.NOT_APPLICABLE]
    )
    if overall_status == OverallComplianceStatus.COMPLIANT:
        executive_summary = f"Document is compliant. All {applicable_count} applicable requirements met."
    elif overall_status == OverallComplianceStatus.HIGH_RISK:
        executive_summary = (
            f"Document has high-risk compliance issues. "
            f"{status_counts[FindingStatus.POTENTIAL_NON_COMPLIANCE]} potential non-compliance(s) found. "
            f"Human review required."
        )
    elif overall_status == OverallComplianceStatus.REVIEW_REQUIRED:
        executive_summary = (
            f"Document requires compliance review. "
            f"{status_counts[FindingStatus.REQUIRES_REVIEW]} requirement(s) need review, "
            f"{status_counts[FindingStatus.INSUFFICIENT_EVIDENCE]} lack evidence. "
            f"Human officer decision required."
        )
    else:
        executive_summary = "Compliance status unknown. Review required."

    report = ComplianceDecisionReport(
        report_id=str(uuid.uuid4()),
        document_id=document_id,
        analysis_id=analysis_id,
        overall_status=overall_status,
        overall_risk=overall_risk,
        total_requirements=len(assessments),
        applicable_requirements=applicable_count,
        compliant_count=status_counts[FindingStatus.COMPLIANT],
        potential_non_compliance_count=status_counts[FindingStatus.POTENTIAL_NON_COMPLIANCE],
        insufficient_evidence_count=status_counts[FindingStatus.INSUFFICIENT_EVIDENCE],
        requires_review_count=status_counts[FindingStatus.REQUIRES_REVIEW],
        unknown_count=status_counts[FindingStatus.UNKNOWN],
        critical_count=risk_counts[RiskLevel.CRITICAL],
        high_count=risk_counts[RiskLevel.HIGH],
        medium_count=risk_counts[RiskLevel.MEDIUM],
        low_count=risk_counts[RiskLevel.LOW],
        info_count=risk_counts[RiskLevel.INFO],
        findings=findings,
        high_priority_items=high_priority,
        human_review_queue=review_items,
        executive_summary=executive_summary,
        key_findings=key_findings,
        critical_issues=critical_issues,
        provenance={
            "analysis_id": analysis_id,
            "document_id": document_id,
            "phase": "8",
            "generated_at_timestamp": _now().isoformat(),
        },
        generated_at=_now(),
    )

    # Persist report
    _write(_phase8_report_path(report.report_id), report.model_dump(mode="json"))

    return report


def get_requirement_explanation(requirement_id: str, analysis_id: str) -> Optional[RequirementExplanation]:
    """Retrieve explanation for a requirement evaluation."""
    payload = _read(_phase8_explanation_path(requirement_id, analysis_id))
    return RequirementExplanation.model_validate(payload) if payload else None


def get_compliance_decision_report(report_id: str) -> Optional[ComplianceDecisionReport]:
    """Retrieve a compliance decision report."""
    payload = _read(_phase8_report_path(report_id))
    return ComplianceDecisionReport.model_validate(payload) if payload else None


def create_and_persist_explanations(analysis_id: str) -> Dict[str, RequirementExplanation]:
    """Create and persist explanations for all requirements in an analysis."""
    assessments = get_requirement_assessments_for_analysis(analysis_id)
    explanations: Dict[str, RequirementExplanation] = {}

    for assessment in assessments:
        explanation = _build_requirement_explanation(assessment)
        explanations[assessment.requirement_id] = explanation
        _write(
            _phase8_explanation_path(assessment.requirement_id, analysis_id),
            explanation.model_dump(mode="json"),
        )

    return explanations
