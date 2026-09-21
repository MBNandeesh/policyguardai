// Phase 8 Compliance Decision Models
export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
export type OverallComplianceStatus = 'COMPLIANT' | 'HIGH_RISK' | 'REVIEW_REQUIRED' | 'UNKNOWN'
export type FindingStatus =
  | 'COMPLIANT'
  | 'POTENTIAL_NON_COMPLIANCE'
  | 'REQUIRES_REVIEW'
  | 'INSUFFICIENT_EVIDENCE'
  | 'UNKNOWN'
  | 'NOT_APPLICABLE'
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'

export interface ComplianceFinding {
  finding_id: string
  requirement_id: string
  requirement_title: string
  status: FindingStatus
  risk_level: RiskLevel
  severity: Severity
  explanation: string
  evidence_available: boolean
  regulatory_grounding: boolean
  source_document_id?: string
  source_page?: number
  mandatory: boolean
}

export interface HumanReviewItem {
  review_item_id: string
  requirement_id: string
  requirement_title: string
  assessment_id?: string
  document_id: string
  status: FindingStatus
  risk_level: RiskLevel
  reason: string
  priority: number
  evidence_summary: string
  document_evidence_available: boolean
  regulatory_evidence_available: boolean
  confidence_level?: string
  suggested_action: string
  created_at: string
}

export interface ComplianceDecisionReport {
  report_id: string
  document_id: string
  analysis_id?: string
  overall_status: OverallComplianceStatus
  overall_risk: RiskLevel
  total_requirements: number
  applicable_requirements: number
  compliant_count: number
  potential_non_compliance_count: number
  insufficient_evidence_count: number
  requires_review_count: number
  unknown_count: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  info_count: number
  findings: ComplianceFinding[]
  high_priority_items: HumanReviewItem[]
  human_review_queue: HumanReviewItem[]
  executive_summary: string
  key_findings: string[]
  critical_issues: string[]
  provenance: Record<string, unknown>
  generated_at: string
  version: string
}

export interface RequirementExplanation {
  requirement_id: string
  requirement_title: string
  requirement_description: string
  category: string
  mandatory: boolean
  evaluation_status: FindingStatus
  risk_level: RiskLevel
  reason: string
  evidence_summary: string
  source_document_id?: string
  source_page?: number
  source_section?: string
  regulatory_authority?: string
  regulatory_reference?: string
  regulatory_url?: string
  confidence?: string
  human_review_required: boolean
  requires_review_reason?: string
  evidence_trace?: EvidenceTrace
  assessment_id?: string
  created_at: string
}

export interface EvidenceTrace {
  requirement_id: string
  requirement_title: string
  source_document_id?: string
  source_page?: number
  source_section?: string
  source_text?: string
  document_evidence?: Record<string, unknown>
  regulatory_evidence?: Record<string, unknown>
  evaluation_status: FindingStatus
  evaluation_confidence?: string
}

export interface DocumentRecord {
  document_id: string
  filename: string
  file_size: number
  page_count: number
  upload_time: string
  processing_status: string
  processing_error?: string
  extraction_method: string
  created_at: string
}

export interface RequirementAssessment {
  assessment_id: string
  requirement_id: string
  document_id: string
  status: FindingStatus
  severity: Severity
  title: string
  description: string
  confidence: string
  created_at: string
}

export interface ComplianceAnalysis {
  analysis_id: string
  document_id: string
  status: string
  created_at: string
}
