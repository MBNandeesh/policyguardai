import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.documents.service import get_document_record, get_page
from app.regulatory.service import get_document, get_provision, get_source
from app.retrieval.models import RetrievalResult
from app.retrieval.service import get_retrieval_service

from .models import (
    AnalysisRequest,
    AnalysisResult,
    DocumentEvidence,
    Finding,
    FindingStatus,
    RegulatoryEvidence,
    Severity,
)


STORAGE_ROOT = os.path.join(settings.storage_path, "compliance")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _analysis_path(analysis_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "analyses", f"{analysis_id}.json")


def _write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def _read(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _document_evidence(document_id: str, page_count: int) -> List[DocumentEvidence]:
    evidence: List[DocumentEvidence] = []
    for page_number in range(1, page_count + 1):
        page = get_page(document_id, page_number)
        if page is None or not page.text.strip():
            continue
        evidence.append(
            DocumentEvidence(
                document_id=document_id,
                page_number=page_number,
                text=page.text,
                source_locator=f"p.{page_number}",
                content_hash=hashlib.sha256(page.text.encode("utf-8")).hexdigest(),
            )
        )
    return evidence


def _regulatory_evidence(result: RetrievalResult) -> RegulatoryEvidence:
    source = get_source(result.source_id)
    document = get_document(result.document_id)
    provision = get_provision(result.provision_id)
    if not source or not document or not provision:
        raise ValueError("Retrieved regulatory evidence does not resolve to Phase 3 records.")
    if (
        document.get("source_id") != result.source_id
        or provision.get("document_id") != result.document_id
        or provision.get("source_id") != result.source_id
    ):
        raise ValueError("Retrieved regulatory provenance relationship is invalid.")
    if source.get("source_domain") != "REGULATORY_AUTHORITY":
        raise ValueError("Only Phase 3 regulatory authority records may ground findings.")
    authoritative_text = (provision.get("normalized_text") or provision.get("text") or "").strip()
    if not result.text.strip() or result.text.strip() not in authoritative_text:
        raise ValueError("Retrieved regulatory text is not supported by the Phase 3 provision.")
    if result.provision_number != provision.get("provision_number"):
        raise ValueError("Retrieved provision number does not match the Phase 3 provision.")
    if result.official_url != provision.get("official_url") or result.official_url != source.get("official_url"):
        raise ValueError("Retrieved official URL does not match Phase 3 provenance.")
    if result.content_hash != provision.get("content_hash"):
        raise ValueError("Retrieved content hash does not match the Phase 3 provision.")
    return RegulatoryEvidence(
        source_id=result.source_id,
        document_id=result.document_id,
        provision_id=result.provision_id,
        provision_number=result.provision_number,
        heading=result.heading,
        text=result.text,
        page_number=result.page_number,
        official_url=result.official_url,
        source_locator=result.source_locator,
        content_hash=result.content_hash,
        chunk_id=result.chunk_id,
        similarity_score=result.similarity_score,
    )


def get_analysis(analysis_id: str) -> Optional[AnalysisResult]:
    payload = _read(_analysis_path(analysis_id))
    return AnalysisResult.model_validate(payload) if payload else None


def get_findings(analysis_id: str) -> List[Finding]:
    analysis = get_analysis(analysis_id)
    return analysis.findings if analysis else []


def analyze(request: AnalysisRequest) -> AnalysisResult:
    record = get_document_record(request.document_id)
    if record is None:
        raise ValueError("User document not found.")
    if record.processing_status != "processed":
        raise ValueError("User document processing is not available.")

    document_evidence = _document_evidence(request.document_id, record.page_count)
    analysis_id = str(uuid.uuid4())
    created_at = _now()
    retrieval = get_retrieval_service()
    if retrieval.vector_store.count() == 0:
        retrieval.build_index()
    query = f"{request.requested_scope}\n" + "\n".join(item.text for item in document_evidence)
    retrieved = retrieval.search_from_document(request.document_id, query, top_k=request.top_k)
    regulatory_basis = [_regulatory_evidence(item) for item in retrieved]

    if not regulatory_basis:
        finding = Finding(
            finding_id=str(uuid.uuid4()),
            document_id=request.document_id,
            analysis_id=analysis_id,
            category="GROUNDING",
            status=FindingStatus.INSUFFICIENT_EVIDENCE,
            severity=Severity.UNKNOWN,
            title="Authoritative regulatory evidence unavailable",
            description="No supporting evidence was found in the available authoritative regulatory sources.",
            document_evidence=document_evidence,
            confidence="UNKNOWN",
            requires_human_review=True,
            provenance={"source_required": True},
            created_at=created_at,
        )
        status = "INSUFFICIENT_EVIDENCE"
    else:
        finding = Finding(
            finding_id=str(uuid.uuid4()),
            document_id=request.document_id,
            analysis_id=analysis_id,
            category="PROCUREMENT_REVIEW",
            status=FindingStatus.REQUIRES_REVIEW,
            severity=Severity.UNKNOWN,
            title="Grounded procurement review required",
            description="Regulatory provisions were retrieved for human review; this analysis does not make a legal determination.",
            document_evidence=document_evidence,
            regulatory_basis=regulatory_basis,
            confidence="LOW",
            requires_human_review=True,
            provenance={"retrieval": "Phase 4", "authoritative_source": "Phase 3"},
            created_at=created_at,
        )
        status = "COMPLETED"

    result = AnalysisResult(
        analysis_id=analysis_id,
        document_id=request.document_id,
        requested_scope=request.requested_scope,
        status=status,
        findings=[finding],
        retrieved_regulatory_evidence=regulatory_basis,
        created_at=created_at,
    )
    _write(_analysis_path(analysis_id), result.model_dump(mode="json"))
    return result