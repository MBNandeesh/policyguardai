"""
Paired (Tender + Bidder) compliance evaluation.

The tender PDF (NIT/RFP) states the requirements. The bidder PDF(s) contain the
bidder's submitted evidence. This module maps requirements extracted from the
tender document onto evidence gathered from BOTH the tender and the bidder
documents, then evaluates each requirement with the same deterministic,
regulatorily-grounded logic as the single-document flow (Phase 7 rules).
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.documents.service import get_document_record, get_page

from .models import (
    DocumentEvidence,
    FindingStatus,
    Requirement,
    RequirementAssessment,
)
from .service import (
    _derive_requirement_status,
    _match_requirement_to_regulations,
    _now,
    _requirement_report_from_assessments,
    _requirement_document_evidence,
    extract_requirements_for_document,
)


def _normalize_content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def _bidder_document_evidence(
    bidder_document_ids: List[str],
    requirement: Requirement,
) -> Tuple[List[DocumentEvidence], List[str]]:
    """
    Gather evidence for a tender requirement from the bidder's submitted PDFs.

    Preference order per bidder document:
    1. The tender page containing the requirement's source text (requirement
       answer location, if the bidder echoed the tender wording).
    2. Any page containing a key phrase from the requirement description.
    3. The first non-empty page as a fallback so the requirement always has
       traceable bidder evidence.
    """
    evidence: List[DocumentEvidence] = []
    contributing_docs: List[str] = []

    source_text = (requirement.source_text or requirement.description or "").strip()

    for bidder_document_id in bidder_document_ids:
        record = get_document_record(bidder_document_id)
        if record is None:
            continue

        pages: List[Tuple[int, str]] = []
        for page_number in range(1, (record.page_count or 0) + 1):
            page = get_page(bidder_document_id, page_number)
            if page is None:
                continue
            pages.append((page_number, page.text or ""))

        non_empty = [(p, t) for p, t in pages if t.strip()]
        if not non_empty:
            continue

        selected_page: Optional[int] = None
        selected_text: Optional[str] = None

        # 1. Requirement source text echoed in the bidder document.
        if source_text:
            for page_number, text in non_empty:
                if source_text.lower() in text.lower():
                    selected_page, selected_text = page_number, text
                    break

        # 2. Key phrase from the requirement description (>= 6 chars words).
        if selected_page is None:
            key_phrases = [
                phrase.strip().lower()
                for phrase in source_text.replace(";", ".").replace("\n", ".").split(".")
                if len(phrase.strip()) >= 6
            ]
            for phrase in key_phrases:
                for page_number, text in non_empty:
                    if phrase in text.lower():
                        selected_page, selected_text = page_number, text
                        break
                if selected_page is not None:
                    break

        # 3. Fallback: first non-empty page.
        if selected_page is None:
            selected_page, selected_text = non_empty[0]

        contributing_docs.append(bidder_document_id)
        evidence.append(
            DocumentEvidence(
                document_id=bidder_document_id,
                page_number=selected_page,
                text=selected_text,
                source_locator=f"p.{selected_page}",
                content_hash=_normalize_content_hash(selected_text or ""),
            )
        )

    return evidence, contributing_docs


def evaluate_requirements_paired(
    tender_document_id: str,
    bidder_document_ids: Optional[List[str]] = None,
    analysis_id: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Evaluate tender requirements against tender + bidder document evidence.

    - Requirements are extracted from the tender document only.
    - Document evidence combines the tender's own evidence and the bidder
      documents' evidence for the same requirement.
    - Regulatory grounding, status derivation, and persistence follow the
      existing deterministic Phase 7 logic.
    """
    tender_record = get_document_record(tender_document_id)
    if tender_record is None:
        raise ValueError("Tender document not found.")

    bidders: List[str] = []
    for bidder_document_id in bidder_document_ids or []:
        bidder_id = (bidder_document_id or "").strip()
        if not bidder_id or bidder_id == tender_document_id:
            continue
        if get_document_record(bidder_id) is None:
            raise ValueError(f"Bidder document not found: {bidder_id}")
        bidders.append(bidder_id)

    payload = extract_requirements_for_document(tender_document_id)
    requirements = [Requirement.model_validate(item) for item in payload.get("requirements", [])]

    if analysis_id is None:
        analysis_id = str(uuid.uuid4())

    assessments: List[RequirementAssessment] = []
    for requirement in requirements:
        tender_evidence = _requirement_document_evidence(tender_document_id, requirement)
        bidder_evidence, contributing_docs = _bidder_document_evidence(bidders, requirement)
        combined_evidence = tender_evidence + bidder_evidence

        matches, regulatory_basis = _match_requirement_to_regulations(
            tender_document_id, requirement, top_k=top_k
        )
        status, severity, explanation = _derive_requirement_status(
            requirement, combined_evidence, regulatory_basis
        )

        if bidders:
            if contributing_docs:
                explanation += (
                    f" Tender requirement mapped to {len(contributing_docs)} bidder document(s): "
                    + ", ".join(contributing_docs)
                    + "."
                )
            else:
                explanation += " No bidder document provided matching evidence for this requirement."

        assessment = RequirementAssessment(
            assessment_id=str(uuid.uuid4()),
            requirement_id=requirement.requirement_id,
            document_id=tender_document_id,
            analysis_id=analysis_id,
            status=status,
            severity=severity,
            title=requirement.title,
            description=requirement.description,
            document_evidence=combined_evidence,
            regulatory_basis=regulatory_basis,
            confidence="LOW" if not regulatory_basis else "MEDIUM",
            requires_human_review=status in {
                FindingStatus.REQUIRES_REVIEW,
                FindingStatus.INSUFFICIENT_EVIDENCE,
                FindingStatus.POTENTIAL_NON_COMPLIANCE,
            },
            explanation=explanation,
            created_at=_now(),
            matches=matches,
        )
        # Persist alongside the other requirement assessments.
        from .service import _requirement_assessment_path, _write

        _write(
            _requirement_assessment_path(assessment.assessment_id),
            assessment.model_dump(mode="json"),
        )
        assessments.append(assessment)

    report = _requirement_report_from_assessments(analysis_id, tender_document_id, assessments)

    return {
        "analysis_id": analysis_id,
        "tender_document_id": tender_document_id,
        "bidder_document_ids": bidders,
        "requirement_assessments": [a.model_dump(mode="json") for a in assessments],
        "report": report.model_dump(mode="json"),
    }
