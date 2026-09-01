from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib


class Requirement(BaseModel):
    requirement_id: str
    title: str
    description: str
    category: str
    mandatory: bool
    evidence_required: bool = True
    evidence_types: List[str] = Field(default_factory=list)
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    regulatory_reference: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


def deterministic_requirement_id(document_id: str, text: str) -> str:
    payload = f"{document_id}|{(text or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class FindingStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    POTENTIAL_NON_COMPLIANCE = "POTENTIAL_NON_COMPLIANCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class DocumentEvidence(BaseModel):
    document_id: str
    page_number: int
    text: str
    source_locator: str
    text_offset_start: Optional[int] = None
    text_offset_end: Optional[int] = None
    content_hash: str = ""


class RegulatoryEvidence(BaseModel):
    source_id: str
    document_id: str
    provision_id: str
    provision_number: str
    heading: str = ""
    text: str
    page_number: Optional[int] = None
    official_url: str = ""
    source_locator: Optional[str] = None
    content_hash: str = ""
    chunk_id: str = ""
    similarity_score: Optional[float] = None


class Finding(BaseModel):
    finding_id: str
    document_id: str
    analysis_id: str
    category: str
    status: FindingStatus
    severity: Severity
    title: str
    description: str
    document_evidence: List[DocumentEvidence] = Field(default_factory=list)
    regulatory_basis: List[RegulatoryEvidence] = Field(default_factory=list)
    confidence: str = "UNKNOWN"
    requires_human_review: bool = True
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @model_validator(mode="after")
    def require_basis_for_grounded_status(self):
        exempt = {
            FindingStatus.INSUFFICIENT_EVIDENCE,
            FindingStatus.UNKNOWN,
            FindingStatus.NOT_APPLICABLE,
            FindingStatus.REQUIRES_REVIEW,
        }
        if self.status not in exempt and not self.regulatory_basis:
            raise ValueError("Regulatory basis is required for this finding status.")
        return self


class AnalysisRequest(BaseModel):
    document_id: str = Field(min_length=1)
    requested_scope: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class AnalysisResult(BaseModel):
    analysis_id: str
    document_id: str
    requested_scope: str
    status: str
    findings: List[Finding] = Field(default_factory=list)
    retrieved_regulatory_evidence: List[RegulatoryEvidence] = Field(default_factory=list)
    created_at: datetime


class RequirementMatch(BaseModel):
    requirement_id: str
    document_id: str
    matched_provision_id: Optional[str] = None
    matched_document_id: Optional[str] = None
    matched_source_id: Optional[str] = None
    relationship_type: str = "related"
    similarity_score: Optional[float] = None
    confidence: str = "UNKNOWN"
    evidence: List[RegulatoryEvidence] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class RequirementAssessment(BaseModel):
    assessment_id: str
    requirement_id: str
    document_id: str
    analysis_id: Optional[str] = None
    status: FindingStatus
    severity: Severity = Severity.UNKNOWN
    title: str
    description: str
    document_evidence: List[DocumentEvidence] = Field(default_factory=list)
    regulatory_basis: List[RegulatoryEvidence] = Field(default_factory=list)
    confidence: str = "UNKNOWN"
    requires_human_review: bool = True
    explanation: str = ""
    created_at: datetime
    matches: List[RequirementMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_basis_for_grounded_status(self):
        exempt = {
            FindingStatus.INSUFFICIENT_EVIDENCE,
            FindingStatus.UNKNOWN,
            FindingStatus.NOT_APPLICABLE,
            FindingStatus.REQUIRES_REVIEW,
        }
        if self.status not in exempt and not self.regulatory_basis:
            raise ValueError("Regulatory basis is required for this requirement status.")
        return self


class RequirementReport(BaseModel):
    analysis_id: str
    document_id: str
    total_requirements: int = 0
    compliant_count: int = 0
    potential_non_compliance_count: int = 0
    insufficient_evidence_count: int = 0
    requires_review_count: int = 0
    not_applicable_count: int = 0
    summary: str = ""
    requirement_assessments: List[RequirementAssessment] = Field(default_factory=list)
    created_at: datetime


class RequirementEvaluationRequest(BaseModel):
    document_id: str = Field(min_length=1)
    requirement_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
