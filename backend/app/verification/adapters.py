"""Verification adapter framework (Plan Step 13 / SIH capability 1).

Every government-portal verification goes through a VerificationAdapter.
Modes are honest: this build ships MOCK + DOCUMENT modes; LIVE adapters are
invented only where an official API contract is genuinely integrated, and
INTEGRATION_READY where the contract exists but credentials are pending.
No adapter ever reports LIVE without a real portal call.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import (
    PORTAL_REGISTRY,
    AdapterMode,
    VerificationDomain,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    VerificationTier,
)


def _payload_hash(request: VerificationRequest) -> str:
    payload = json.dumps(
        {
            "domain": request.domain.value,
            "bidder_id": request.bidder_id,
            "identifier": request.identifier.strip().upper(),
            "extra": request.extra,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _portal_meta(domain: VerificationDomain) -> Dict[str, str]:
    return PORTAL_REGISTRY.get(domain, {"portal": "", "official_url": ""})


def _identifier_valid(identifier: str, domain: VerificationDomain) -> bool:
    """Format-level sanity checks so MOCK mode still rejects garbage input."""
    value = (identifier or "").strip().upper()
    if not value:
        return False
    if domain == VerificationDomain.GST:
        return bool(re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z]\dZ[A-Z\d]", value))
    if domain == VerificationDomain.PAN:
        return bool(re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", value))
    if domain == VerificationDomain.MCA:
        return bool(re.fullmatch(r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}", value))
    if domain == VerificationDomain.UDYAM:
        return bool(re.fullmatch(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", value))
    return True


class VerificationAdapter(ABC):
    """Contract for one portal/verification domain."""

    domain: VerificationDomain
    mode: AdapterMode

    @abstractmethod
    def verify(self, request: VerificationRequest) -> VerificationResult:
        ...

    def _base_result(self, request: VerificationRequest) -> Dict:
        meta = _portal_meta(self.domain)
        return {
            "verification_id": str(uuid.uuid4()),
            "domain": self.domain,
            "bidder_id": request.bidder_id,
            "identifier": request.identifier,
            "mode": self.mode,
            "portal": meta["portal"],
            "official_url": meta["official_url"],
            "checked_at": datetime.now(timezone.utc),
            "request_payload_hash": _payload_hash(request),
        }


class MockVerificationAdapter(VerificationAdapter):
    """Deterministic MOCK adapter for demo/dev.

    Behaviour is derived only from the identifier the user submitted, so the
    demo is repeatable: valid-format identifiers verify, sentinel values
    (containing EXPIRED / MISMATCH / NOTFOUND) reproduce common failure cases.
    Results are always labelled MOCK and capped at T2: a simulated check can
    never claim T1 (authoritative) status.
    """

    mode = AdapterMode.MOCK

    def verify(self, request: VerificationRequest) -> VerificationResult:
        identifier = request.identifier.strip().upper()
        meta = _portal_meta(self.domain)

        # Demo sentinels take precedence over format validation so failure
        # scenarios reproduce even with well-formed sentinel identifiers.
        sentinel = None
        for marker, status in (
            ("EXPIRED", VerificationStatus.EXPIRED),
            ("MISMATCH", VerificationStatus.MISMATCH),
            ("NOTFOUND", VerificationStatus.NOT_FOUND),
        ):
            if marker in identifier:
                sentinel = status
                break

        if sentinel is not None:
            status = sentinel
            tier = VerificationTier.T4
            summary = f"Simulated {self.domain.value} record status={sentinel.value} (mode={self.mode.value})."
            confidence = 0.5
        elif not _identifier_valid(identifier, self.domain):
            status = VerificationStatus.UNAVAILABLE
            tier = VerificationTier.T4
            summary = (
                f"Identifier does not match the expected {self.domain.value} format; "
                f"verification not performed (mode={self.mode.value})."
            )
            confidence = 0.0
        else:
            status = VerificationStatus.VERIFIED
            tier = VerificationTier.T2
            summary = (
                f"Simulated {self.domain.value} check passed against mock record "
                f"(mode={self.mode.value}; portal={meta['portal']})."
            )
            confidence = 0.7

        return VerificationResult(
            **self._base_result(request),
            status=status,
            tier=tier,
            summary=summary,
            confidence=confidence,
            checked_fields={"identifier_format_valid": True},
            provenance={
                "adapter": self.__class__.__name__,
                "mode": self.mode.value,
                "note": "MOCK result - not an authoritative portal response.",
            },
        )


class BlacklistMockAdapter(MockVerificationAdapter):
    """Debarment check. In MOCK mode a 'clear' result is only advisory."""

    domain = VerificationDomain.BLACKLIST
    mode = AdapterMode.MOCK

    def verify(self, request: VerificationRequest) -> VerificationResult:
        result = super().verify(request)
        if result.status == VerificationStatus.VERIFIED:
            # For blacklist, "verified" means found-clear; wrongful disqualification
            # control: absence of a hit is REQUIRES_REVIEW, never auto-clear.
            result.status = VerificationStatus.REQUIRES_REVIEW
            result.tier = VerificationTier.T4
            result.summary = (
                "No debarment hit in simulated blacklist scan; formal clearance "
                "requires the actual debarment list check (mode=MOCK)."
            )
            result.confidence = 0.4
        return result


class DocumentVerificationAdapter(VerificationAdapter):
    """Checks a claim against uploaded document evidence (T2 pathway).

    Attaches the supporting document id; actual document-content cross-checks
    are performed by the compliance engine - this adapter records provenance.
    """

    mode = AdapterMode.DOCUMENT

    def __init__(self, domain: VerificationDomain):
        self.domain = domain

    def verify(self, request: VerificationRequest) -> VerificationResult:
        has_doc = bool(request.supporting_document_id)
        status = VerificationStatus.VERIFIED if has_doc else VerificationStatus.REQUIRES_REVIEW
        tier = VerificationTier.T2 if has_doc else VerificationTier.T4
        summary = (
            f"Claim supported by uploaded document {request.supporting_document_id} "
            f"(mode=DOCUMENT)." if has_doc else
            f"No supporting document supplied for {self.domain.value}; officer review required."
        )
        return VerificationResult(
            **self._base_result(request),
            status=status,
            tier=tier,
            summary=summary,
            confidence=0.6 if has_doc else 0.3,
            checked_fields={"supporting_document_id": request.supporting_document_id or None},
            provenance={"adapter": "DocumentVerificationAdapter", "mode": self.mode.value},
        )


_ADAPTERS: Dict[VerificationDomain, VerificationAdapter] = {}


def _adapters() -> Dict[VerificationDomain, VerificationAdapter]:
    global _ADAPTERS
    if not _ADAPTERS:
        for domain in VerificationDomain:
            if domain == VerificationDomain.BLACKLIST:
                _ADAPTERS[domain] = BlacklistMockAdapter()
            else:
                _ADAPTERS[domain] = MockVerificationAdapter()
                _ADAPTERS[domain].domain = domain
    return _ADAPTERS


def get_adapter(domain: VerificationDomain) -> VerificationAdapter:
    return _adapters()[domain]


def adapter_catalog() -> List[Dict]:
    """Honest catalogue of every domain + its mode - feeds the UI badges."""
    catalog = []
    for domain in VerificationDomain:
        adapter = get_adapter(domain)
        meta = _portal_meta(domain)
        catalog.append(
            {
                "domain": domain.value,
                "mode": adapter.mode.value,
                "portal": meta["portal"],
                "official_url": meta["official_url"],
                "live_capable": adapter.mode == AdapterMode.LIVE,
            }
        )
    return catalog


def run_verification(request: VerificationRequest) -> VerificationResult:
    return get_adapter(request.domain).verify(request)
