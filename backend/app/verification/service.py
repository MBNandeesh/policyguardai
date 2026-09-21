"""Verification service: persistence + bidder summaries + staleness."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from app.config import settings

from .adapters import run_verification
from .models import (
    BidderVerificationSummary,
    VerificationDomain,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    VerificationTier,
)

STORAGE_ROOT = os.path.join(settings.storage_path, "verification")


def _result_path(verification_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "results", f"{verification_id}.json")


def _write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def _read(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def perform_verification(
    domain: VerificationDomain,
    bidder_id: str,
    identifier: str,
    supporting_document_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> VerificationResult:
    request = VerificationRequest(
        domain=domain,
        bidder_id=bidder_id,
        identifier=identifier,
        supporting_document_id=supporting_document_id,
        extra=extra or {},
    )
    result = run_verification(request)
    _write(_result_path(result.verification_id), result.model_dump(mode="json"))
    return result


def get_verification(verification_id: str) -> Optional[VerificationResult]:
    payload = _read(_result_path(verification_id))
    return VerificationResult.model_validate(payload) if payload else None


def list_verifications(bidder_id: Optional[str] = None, domain: Optional[VerificationDomain] = None) -> List[VerificationResult]:
    folder = os.path.join(STORAGE_ROOT, "results")
    if not os.path.exists(folder):
        return []
    results: List[VerificationResult] = []
    for filename in sorted(os.listdir(folder)):
        if not filename.endswith(".json"):
            continue
        payload = _read(os.path.join(folder, filename))
        if not payload:
            continue
        if bidder_id and payload.get("bidder_id") != bidder_id:
            continue
        if domain and payload.get("domain") != domain.value:
            continue
        results.append(VerificationResult.model_validate(payload))
    return results


def _overall_tier(results: List[VerificationResult]) -> VerificationTier:
    """Worst-tier-wins summary: T4 if anything unresolved, else lowest tier."""
    if not results:
        return VerificationTier.T4
    order = [VerificationTier.T1, VerificationTier.T2, VerificationTier.T3, VerificationTier.T4]
    worst = VerificationTier.T1
    for result in results:
        if result.status == VerificationStatus.NOT_APPLICABLE:
            continue
        if result.tier == VerificationTier.T4:
            return VerificationTier.T4
        if order.index(result.tier) > order.index(worst):
            worst = result.tier
    return worst


def bidder_summary(bidder_id: str) -> BidderVerificationSummary:
    results = list_verifications(bidder_id=bidder_id)
    verified = [r for r in results if r.status == VerificationStatus.VERIFIED]
    unresolved = [r for r in results if r.status not in {VerificationStatus.VERIFIED, VerificationStatus.NOT_APPLICABLE}]
    return BidderVerificationSummary(
        bidder_id=bidder_id,
        results=results,
        verified_count=len(verified),
        unresolved_count=len(unresolved),
        overall_tier=_overall_tier(results),
    )

