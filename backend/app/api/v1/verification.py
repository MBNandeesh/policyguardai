"""Verification API: portal-adapter verification for bidder compliance.

SIH26100 capabilities 1-2, 12-14: portal checks with honest adapter modes,
T1-T4 tiers, compliance scoring and an auditable record of every check.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.verification import service as verification_service
from app.verification.adapters import adapter_catalog
from app.verification.models import VerificationDomain, VerificationStatus

router = APIRouter(tags=["verification"])


class VerificationIn(BaseModel):
    domain: VerificationDomain
    bidder_id: str
    identifier: str
    supporting_document_id: Optional[str] = None


class ScoreComponent(BaseModel):
    domain: str
    status: str
    tier: str
    mode: str
    weight: float
    contributed: float


class ComplianceScore(BaseModel):
    bidder_id: str
    score: float
    max_score: float = 100.0
    risk_level: str
    recommendation: str
    components: List[ScoreComponent]
    unresolved_domains: List[str]
    generated_from_mode: str


class VerificationOut(BaseModel):
    verification_id: str
    domain: str
    bidder_id: str
    identifier: str
    status: str
    tier: str
    mode: str
    portal: str
    official_url: str
    summary: str
    confidence: float
    checked_at: str
    stale_after_hours: int
    is_stale: bool


def _out(result) -> VerificationOut:
    return VerificationOut(
        verification_id=result.verification_id,
        domain=result.domain.value,
        bidder_id=result.bidder_id,
        identifier=result.identifier,
        status=result.status.value,
        tier=result.tier.value,
        mode=result.mode.value,
        portal=result.portal,
        official_url=result.official_url,
        summary=result.summary,
        confidence=result.confidence,
        checked_at=result.checked_at.isoformat(),
        stale_after_hours=result.stale_after_hours,
        is_stale=result.is_stale,
    )


@router.get("/verification/catalog")
def get_adapter_catalog():
    """Every verification domain with its honest adapter mode (LIVE/MOCK/...)."""
    return adapter_catalog()


@router.post("/verification/run", response_model=VerificationOut)
def run_check(payload: VerificationIn):
    result = verification_service.perform_verification(
        domain=payload.domain,
        bidder_id=payload.bidder_id,
        identifier=payload.identifier,
        supporting_document_id=payload.supporting_document_id,
    )
    return _out(result)


@router.get("/verification/results")
def list_results(bidder_id: Optional[str] = None, domain: Optional[VerificationDomain] = None):
    results = verification_service.list_verifications(bidder_id=bidder_id, domain=domain)
    return [_out(r) for r in results]


@router.get("/verification/results/{verification_id}", response_model=VerificationOut)
def get_result(verification_id: str):
    result = verification_service.get_verification(verification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Verification result not found")
    return _out(result)


@router.get("/verification/bidders/{bidder_id}/summary")
def bidder_summary(bidder_id: str):
    summary = verification_service.bidder_summary(bidder_id)
    return {
        "bidder_id": summary.bidder_id,
        "verified_count": summary.verified_count,
        "unresolved_count": summary.unresolved_count,
        "overall_tier": summary.overall_tier.value,
        "results": [_out(r) for r in summary.results],
        "generated_at": summary.generated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Compliance score, risk level and AI recommendation (SIH capabilities 12-13)
# ---------------------------------------------------------------------------

# Domain weights for the compliance score (sum = 100).
DOMAIN_WEIGHTS = {
    VerificationDomain.UDYAM: 8,
    VerificationDomain.GST: 12,
    VerificationDomain.PAN: 10,
    VerificationDomain.MCA: 8,
    VerificationDomain.EPFO: 8,
    VerificationDomain.ESIC: 6,
    VerificationDomain.STARTUP_INDIA: 6,
    VerificationDomain.NSIC: 6,
    VerificationDomain.OEM_AUTHORIZATION: 10,
    VerificationDomain.DIGILOCKER: 6,
    VerificationDomain.BLACKLIST: 12,
    VerificationDomain.MAKE_IN_INDIA: 8,
}

TIER_MULTIPLIER = {"T1": 1.0, "T2": 0.8, "T3": 0.5, "T4": 0.0}

STATUS_CONTRIBUTION = {
    VerificationStatus.VERIFIED: 1.0,
    VerificationStatus.REQUIRES_REVIEW: 0.3,
    VerificationStatus.MISMATCH: 0.0,
    VerificationStatus.EXPIRED: 0.0,
    VerificationStatus.NOT_FOUND: 0.0,
    VerificationStatus.NOT_VERIFIED: 0.0,
    VerificationStatus.UNAVAILABLE: 0.0,
    VerificationStatus.NOT_APPLICABLE: 1.0,
}


@router.get("/verification/bidders/{bidder_id}/score", response_model=ComplianceScore)
def compliance_score(bidder_id: str):
    """Deterministic compliance score + risk level + advisory recommendation.

    The score is advisory decision support only: the qualification decision
    always remains with the Procurement Officer (SIH26100 constraint).
    """
    results = verification_service.list_verifications(bidder_id=bidder_id)
    latest_by_domain = {}
    for result in results:
        key = result.domain
        if key not in latest_by_domain or result.checked_at > latest_by_domain[key].checked_at:
            latest_by_domain[key] = result

    components: List[ScoreComponent] = []
    unresolved_domains: List[str] = []
    total = 0.0
    max_total = 0.0
    modes_used = set()

    for domain, weight in DOMAIN_WEIGHTS.items():
        result = latest_by_domain.get(domain)
        if result is None:
            unresolved_domains.append(domain.value)
            components.append(
                ScoreComponent(domain=domain.value, status="NOT_CHECKED", tier="T4", mode="NONE", weight=float(weight), contributed=0.0)
            )
            max_total += weight
            continue

        modes_used.add(result.mode.value)
        contribution = (
            weight
            * STATUS_CONTRIBUTION.get(result.status, 0.0)
            * TIER_MULTIPLIER.get(result.tier.value, 0.0)
        )
        total += contribution
        max_total += weight
        if result.status != VerificationStatus.VERIFIED:
            unresolved_domains.append(domain.value)
        components.append(
            ScoreComponent(
                domain=domain.value,
                status=result.status.value,
                tier=result.tier.value,
                mode=result.mode.value,
                weight=float(weight),
                contributed=round(contribution, 2),
            )
        )

    score = round(total, 2)
    failed_domains = [
        c.domain for c in components
        if c.status in {"MISMATCH", "EXPIRED", "NOT_FOUND", "NOT_VERIFIED", "UNAVAILABLE"}
    ]
    if not latest_by_domain:
        risk_level = "UNKNOWN"
        recommendation = "No verifications performed yet. Run portal verification checks for this bidder."
    elif failed_domains:
        risk_level = "HIGH"
        recommendation = (
            "One or more verifications explicitly failed or are expired ("
            + ", ".join(failed_domains)
            + "). Officer review required before any qualification."
        )
    elif score >= 80:
        risk_level = "LOW"
        recommendation = "All major checks passed at sufficient tier. Officer may proceed with standard evaluation."
    elif score >= 50:
        risk_level = "MEDIUM"
        recommendation = "Some verifications unresolved. Review flagged domains and request missing documents before decision."
    else:
        risk_level = "MEDIUM"
        recommendation = "Most verification domains not yet checked. Run the remaining portal verifications to complete the assessment."

    return ComplianceScore(
        bidder_id=bidder_id,
        score=score,
        risk_level=risk_level,
        recommendation=recommendation,
        components=components,
        unresolved_domains=unresolved_domains,
        generated_from_mode="/".join(sorted(modes_used)) if modes_used else "NONE",
    )
