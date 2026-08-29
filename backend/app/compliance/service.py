from typing import List, Dict, Any, Optional, Tuple
import re
from .models import Requirement, deterministic_requirement_id
from app.documents.service import get_document_record, get_page


REQUIREMENT_CATEGORIES = {
    "eligibility",
    "financial",
    "technical",
    "experience",
    "registration",
    "tax",
    "statutory",
    "certification",
    "local_content",
    "msme",
    "startup",
    "oem_authorization",
    "document_submission",
    "declaration",
    "other",
}


# Deterministic rule patterns
MANDATORY_SIGNALS = re.compile(r"\b(shall|must|mandatory|required|compulsory|" r"bidder must submit|required to submit)\b", flags=re.IGNORECASE)
OPTIONAL_SIGNALS = re.compile(r"\b(may|optional|if applicable|wherever applicable)\b", flags=re.IGNORECASE)

EVIDENCE_MAP = [
    (re.compile(r"\bgst\b|gst registration", flags=re.IGNORECASE), ["GST Certificate"]),
    (re.compile(r"\budyam\b|msme|udyam", flags=re.IGNORECASE), ["Udyam/MSME Certificate"]),
    (re.compile(r"\bpan\b|pan card", flags=re.IGNORECASE), ["PAN Document"]),
    (re.compile(r"oem authorization|authorized dealer|manufacturer authorization", flags=re.IGNORECASE), ["OEM Authorization Letter"]),
    (re.compile(r"minimum experience|experience of at least|work order|completion certificate", flags=re.IGNORECASE), ["Work Order / Completion Certificate"]),
    (re.compile(r"turnover|annual turnover|financial year|audited financial statement", flags=re.IGNORECASE), ["Audited Financial Statements / CA Certificate"]),
]


def categorize_text(text: str) -> str:
    t = (text or "").lower()
    if "gst" in t or "tax" in t:
        return "tax"
    if "turnover" in t or "audited" in t or "financial" in t:
        return "financial"
    if "experience" in t or "work order" in t or "completion" in t:
        return "experience"
    if "udyam" in t or "msme" in t:
        return "msme"
    if "startup" in t:
        return "startup"
    if "oem" in t or "manufacturer" in t or "authorized" in t:
        return "oem_authorization"
    if "certificate" in t or "certification" in t:
        return "certification"
    if "registration" in t or "register" in t:
        return "registration"
    if "local content" in t or "make in india" in t:
        return "local_content"
    if "declaration" in t or "undertaking" in t:
        return "declaration"
    if "eligibility" in t or "eligible" in t:
        return "eligibility"
    if "document" in t or "submit" in t or "upload" in t:
        return "document_submission"
    return "other"


def detect_evidence_types(text: str) -> List[str]:
    types: List[str] = []
    for pattern, ev in EVIDENCE_MAP:
        if pattern.search(text or ""):
            types.extend(ev)
    return list(dict.fromkeys(types))


def is_mandatory(text: str) -> Tuple[bool, float, Dict[str, Any]]:
    if not text:
        return False, 0.0, {}
    strong = bool(MANDATORY_SIGNALS.search(text))
    weak = bool(OPTIONAL_SIGNALS.search(text))
    confidence = 0.9 if strong else (0.5 if weak else 0.6)
    metadata = {"signals": {"strong": strong, "weak": weak}}
    mandatory = strong and not weak
    return mandatory, confidence, metadata


def extract_requirements_from_text(document_id: str, text: str, page: Optional[int] = None) -> List[Requirement]:
    results: List[Requirement] = []
    if not text:
        return results

    # Split into candidate sentences/clauses
    candidates = re.split(r"(?<=[\.;\n])\s+", text)
    for cand in candidates:
        cand_clean = (cand or "").strip()
        if len(cand_clean) < 10:
            continue

        # Heuristics: look for requirement-like keywords
        if re.search(r"\bbidder\b|\bmust\b|\bshall\b|required to submit|mandatory|eligibility|certificate|required to submit|proof of|minimum", cand_clean, flags=re.IGNORECASE):
            category = categorize_text(cand_clean)
            mandatory, confidence, meta = is_mandatory(cand_clean)
            evidence_types = detect_evidence_types(cand_clean)
            req_id = deterministic_requirement_id(document_id or "", cand_clean)
            section = _find_section_for_sentence(text, cand_clean)
            req = Requirement(
                requirement_id=req_id,
                title=(cand_clean[:80] + "...") if len(cand_clean) > 80 else cand_clean,
                description=cand_clean,
                category=category,
                mandatory=mandatory,
                evidence_required=bool(evidence_types),
                evidence_types=evidence_types,
                source_document_id=document_id,
                source_page=page,
                source_section=section,
                source_text=cand_clean,
                regulatory_reference=None,
                confidence=confidence,
                metadata={"extraction_method": "rule_based", **meta},
            )
            results.append(req)

    return results


def _find_section_for_sentence(page_text: str, sentence: str) -> Optional[str]:
    if not page_text or not sentence:
        return None

    # If the sentence itself starts with a section-like heading, normalize and return it.
    m_self = re.match(r"^Section\s+\d+[:\.]?\s*(.*)$", sentence.strip(), flags=re.IGNORECASE)
    if m_self:
        title = m_self.group(1).strip()
        return title or sentence.strip()

    # Split into lines and scan: for any line that contains the sentence (or the sentence appears
    # across a small window starting at that line), walk backwards to find the most recent
    # heading-like line and return a normalized title.
    lines = [ln.rstrip() for ln in page_text.splitlines()]

    # helper to normalize a candidate heading line
    def _normalize_heading(cand: str) -> Optional[str]:
        if not cand or not cand.strip():
            return None
        if re.match(r"^Section\b", cand, flags=re.IGNORECASE):
            m = re.match(r"^Section\s+\d+[:\.]?\s*(.*)$", cand, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip() or cand.strip()
            return cand.strip()
        if cand.strip().endswith(":") or cand.strip().endswith("-"):
            return cand.strip().rstrip(":-").strip()
        simple = re.sub(r"[^A-Za-z0-9 ]+", "", cand)
        if 2 <= len(simple.split()) <= 6 and simple.upper() == simple:
            return cand.strip()
        return None

    # look for the sentence in each line or in a small multi-line window
    for i, ln in enumerate(lines):
        window = "\n".join(lines[i : i + 3])
        if sentence in ln or sentence in window:
            # search backwards up to 6 lines for a heading
            for j in range(i, max(i - 7, -1), -1):
                cand = lines[j]
                heading = _normalize_heading(cand)
                if heading:
                    return heading
            # no heading found above this sentence
            return None

    # fallback: if sentence appears somewhere in the joined text, map position to line index
    joined = "\n".join([l for l in lines if l.strip()])
    idx = joined.find(sentence)
    if idx == -1:
        return None
    cum = 0
    for i, ln in enumerate([l for l in lines if l.strip()]):
        cum += len(ln) + 1
        if cum > idx:
            for j in range(i - 1, max(i - 7, -1), -1):
                cand = lines[j]
                heading = _normalize_heading(cand)
                if heading:
                    return heading
            break
    return None


def extract_requirements_for_document(document_id: str) -> Dict[str, Any]:
    record = get_document_record(document_id)
    if record is None:
        raise ValueError("Document not found")

    requirements: List[Requirement] = []
    # iterate pages
    for p in range(1, (record.page_count or 0) + 1):
        page = get_page(document_id, p)
        if page is None:
            continue
        text = page.text or ""
        found = extract_requirements_from_text(document_id, text, page=p)
        requirements.extend(found)

    # Deterministic deduplication by requirement_id
    deduped: Dict[str, Requirement] = {}
    for r in requirements:
        if r.requirement_id in deduped:
            # merge provenance metadata
            existing = deduped[r.requirement_id]
            existing.metadata.setdefault("provenance", [])
            existing.metadata["provenance"].append({"document_id": r.source_document_id, "page": r.source_page, "section": r.source_section})
        else:
            r.metadata.setdefault("provenance", [{"document_id": r.source_document_id, "page": r.source_page, "section": r.source_section}])
            deduped[r.requirement_id] = r

    total = len(deduped)
    mandatory_count = sum(1 for r in deduped.values() if r.mandatory)
    optional_count = total - mandatory_count

    return {
        "document_id": document_id,
        "requirements": [r.model_dump(mode="json") for r in deduped.values()],
        "total_requirements": total,
        "mandatory_requirements": mandatory_count,
        "optional_requirements": optional_count,
        "extraction_metadata": {"method": "rule_based", "version": "0.1"},
    }
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
