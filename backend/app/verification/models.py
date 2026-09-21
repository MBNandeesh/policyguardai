"""Verification domain models: portal adapters, trust tiers, adapter modes.

Implements the SIH26100 verification layer and the plan's honesty contract:
- Every adapter declares its mode (LIVE / INTEGRATION_READY / DOCUMENT / MOCK /
  FUTURE) and the API surfaces that mode verbatim - no fake LIVE claims.
- Every verification result carries a T1-T4 verification tier and full
  provenance (source portal, request payload hash, timestamp, staleness).
- MOCK results are labelled as such and never asserted as authoritative.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdapterMode(str, Enum):
    """How a verification is actually performed. Rendered on screen verbatim."""

    LIVE = "LIVE"                          # real portal/API call
    INTEGRATION_READY = "INTEGRATION_READY"  # API contract built, credentials pending
    DOCUMENT = "DOCUMENT"                  # checked against uploaded document evidence
    MOCK = "MOCK"                          # simulated for demo/dev only
    FUTURE = "FUTURE"                      # designed, not implemented


class VerificationTier(str, Enum):
    """T1-T4 trust ladder for a verification result."""

    T1 = "T1"  # Authoritatively Verified - live portal/API
    T2 = "T2"  # Document Verified - validated uploaded document
    T3 = "T3"  # Self-Declaration Checked - declaration only
    T4 = "T4"  # Unresolved / Conflict


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    MISMATCH = "MISMATCH"
    EXPIRED = "EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationDomain(str, Enum):
    """The SIH26100 statutory/regulatory verification domains."""

    UDYAM = "UDYAM"                # Udyam/MSME registration
    GST = "GST"                    # GST registration + return filing
    PAN = "PAN"                    # PAN + Income Tax compliance
    MCA = "MCA"                    # MCA21 company master data
    EPFO = "EPFO"                  # EPFO compliance
    ESIC = "ESIC"                  # ESIC compliance
    STARTUP_INDIA = "STARTUP_INDIA"
    NSIC = "NSIC"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    DIGILOCKER = "DIGILOCKER"
    BLACKLIST = "BLACKLIST"        # blacklisting / debarment status
    MAKE_IN_INDIA = "MAKE_IN_INDIA"  # local content


# Portal metadata: where the truth would come from in LIVE mode.
PORTAL_REGISTRY: Dict[VerificationDomain, Dict[str, str]] = {
    VerificationDomain.UDYAM: {"portal": "Udyam Registration Portal", "official_url": "https://udyamregistration.gov.in"},
    VerificationDomain.GST: {"portal": "GSTN / GST Public Portal", "official_url": "https://www.gst.gov.in"},
    VerificationDomain.PAN: {"portal": "Income Tax e-Filing (PAN)", "official_url": "https://www.incometax.gov.in"},
    VerificationDomain.MCA: {"portal": "MCA21 Master Data", "official_url": "https://www.mca.gov.in"},
    VerificationDomain.EPFO: {"portal": "EPFO (TRRN/ECR)", "official_url": "https://www.epfindia.gov.in"},
    VerificationDomain.ESIC: {"portal": "ESIC Portal", "official_url": "https://www.esic.gov.in"},
    VerificationDomain.STARTUP_INDIA: {"portal": "Startup India (DPIIT)", "official_url": "https://www.startupindia.gov.in"},
    VerificationDomain.NSIC: {"portal": "NSIC Portal", "official_url": "https://www.nsic.co.in"},
    VerificationDomain.OEM_AUTHORIZATION: {"portal": "OEM / GeM Seller Records", "official_url": "https://gem.gov.in"},
    VerificationDomain.DIGILOCKER: {"portal": "DigiLocker", "official_url": "https://www.digilocker.gov.in"},
    VerificationDomain.BLACKLIST: {"portal": "GeM Blacklist / Debarment List", "official_url": "https://gem.gov.in"},
    VerificationDomain.MAKE_IN_INDIA: {"portal": "GeM Local Content (Class I/II Supplier)", "official_url": "https://gem.gov.in"},
}


class VerificationRequest(BaseModel):
    domain: VerificationDomain
    bidder_id: str
    identifier: str = Field(..., description="Registration number / GSTIN / PAN / CIN etc.")
    supporting_document_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    verification_id: str
    domain: VerificationDomain
    bidder_id: str
    identifier: str
    status: VerificationStatus
    tier: VerificationTier
    mode: AdapterMode
    portal: str = ""
    official_url: str = ""
    summary: str
    checked_fields: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stale_after_hours: int = 72
    provenance: Dict[str, Any] = Field(default_factory=dict)
    request_payload_hash: str = ""

    @property
    def is_stale(self) -> bool:
        age_hours = (datetime.now(timezone.utc) - self.checked_at).total_seconds() / 3600
        return age_hours > self.stale_after_hours


class BidderVerificationSummary(BaseModel):
    bidder_id: str
    results: List[VerificationResult]
    verified_count: int
    unresolved_count: int
    overall_tier: VerificationTier
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
