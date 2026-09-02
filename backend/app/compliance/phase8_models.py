"""
Phase 8: Compliance Decision, Risk, and Explainability Layer Models

This module defines models for Phase 8 compliance decision aggregation,
risk classification, explainability, and human review queue.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    """Risk classification for requirements and findings."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class OverallComplianceStatus(str, Enum):
    """Overall compliance status derived from requirement-level assessments."""
    COMPLIANT = "COMPLIANT"
    HIGH_RISK = "HIGH_RISK"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"


class EvidenceTrace(BaseModel):
    """Structured trace of evidence from requirement to final decision."""
    requirement_id: str
    requirement_title: str
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    document_evidence: Optional[Dict[str, Any]] = None
    regulatory_evidence: Optional[Dict[str, Any]] = None
    evaluation_status: str
    evaluation_confidence: Optional[str] = None


class RequirementExplanation(BaseModel):
    """Detailed explanation for a single requirement evaluation."""
    requirement_id: str
    requirement_title: str
    requirement_description: str
    category: str
    mandatory: bool
    evaluation_status: str
    risk_level: RiskLevel
    reason: str
    evidence_summary: str
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    regulatory_authority: Optional[str] = None
    regulatory_reference: Optional[str] = None
    regulatory_url: Optional[str] = None
    confidence: Optional[str] = None
    human_review_required: bool = False
    requires_review_reason: Optional[str] = None
    evidence_trace: Optional[EvidenceTrace] = None
    assessment_id: Optional[str] = None
    created_at: datetime


class HumanReviewItem(BaseModel):
    """Item requiring human officer review."""
    review_item_id: str
    requirement_id: str
    requirement_title: str
    assessment_id: Optional[str] = None
    document_id: str
    status: str
    risk_level: RiskLevel
    reason: str
    priority: int  # 1 = highest priority
    evidence_summary: str
    document_evidence_available: bool
    regulatory_evidence_available: bool
    confidence_level: Optional[str] = None
    suggested_action: str
    created_at: datetime


class ComplianceFinding(BaseModel):
    """A finding from the compliance decision report."""
    finding_id: str
    requirement_id: str
    requirement_title: str
    status: str
    risk_level: RiskLevel
    severity: str
    explanation: str
    evidence_available: bool
    regulatory_grounding: bool
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    mandatory: bool


class ComplianceDecisionReport(BaseModel):
    """Final compliance decision report aggregating all requirement assessments."""
    report_id: str
    document_id: str
    analysis_id: Optional[str] = None
    overall_status: OverallComplianceStatus
    overall_risk: RiskLevel
    
    # Summary statistics
    total_requirements: int = 0
    applicable_requirements: int = 0
    compliant_count: int = 0
    potential_non_compliance_count: int = 0
    insufficient_evidence_count: int = 0
    requires_review_count: int = 0
    unknown_count: int = 0
    
    # Risk distribution
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    # Detail
    findings: List[ComplianceFinding] = Field(default_factory=list)
    high_priority_items: List[HumanReviewItem] = Field(default_factory=list)
    human_review_queue: List[HumanReviewItem] = Field(default_factory=list)
    
    # Summary
    executive_summary: str = ""
    key_findings: List[str] = Field(default_factory=list)
    critical_issues: List[str] = Field(default_factory=list)
    
    # Metadata
    provenance: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    version: str = "1.0"
