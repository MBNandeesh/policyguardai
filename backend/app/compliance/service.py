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
