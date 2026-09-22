import React, { useEffect, useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { Layout } from '../components/Layout'
import { Card, StatusBadge, RiskBadge, Button, Loading, ErrorMessage, DocumentTypeBadge } from '../components/UI'
import { apiPost, apiGet, ApiError } from '../lib/api'
import { scopeAuditEventsToReport } from '../lib/auditScope'
import { useAuth } from '../lib/auth'
import {
  ComplianceDecisionReport,
  RequirementExplanation,
  ComplianceFinding,
  DocumentRecord,
} from '../lib/types'
import { formatStatusLabel, COLORS } from '../lib/utils'

interface PairedResponse {
  report: ComplianceDecisionReport
  analysis_id: string
  tender_document_id: string
  bidder_document_ids: string[]
}

export default function Compliance() {
  const router = useRouter()
  const tenderDocumentId =
    typeof router.query.tender_document_id === 'string' ? router.query.tender_document_id : undefined
  const legacyDocumentId =
    typeof router.query.document_id === 'string' ? router.query.document_id : undefined
  const bidderIds = Array.isArray(router.query.bidder_document_ids)
    ? router.query.bidder_document_ids
    : router.query.bidder_document_ids
      ? [String(router.query.bidder_document_ids)]
      : []

  const isPaired = bidderIds.length > 0
  const documentId = tenderDocumentId || legacyDocumentId

  const { session } = useAuth()
  const [report, setReport] = useState<ComplianceDecisionReport | null>(null)
  const [tenderDoc, setTenderDoc] = useState<DocumentRecord | null>(null)
  const [bidderDocs, setBidderDocs] = useState<DocumentRecord[]>([])
  const [selectedRequirement, setSelectedRequirement] = useState<ComplianceFinding | null>(null)
  const [explanation, setExplanation] = useState<RequirementExplanation | null>(null)
  const [explanationError, setExplanationError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Officer final decision state
  const [decisionAction, setDecisionAction] = useState<'APPROVE' | 'REQUEST_CLARIFICATION' | 'DO_NOT_PROCEED' | null>(null)
  const [decisionReason, setDecisionReason] = useState('')
  const [decisionRecorded, setDecisionRecorded] = useState<{
    action: string
    label: string
    reason: string
    actor: string
    audit_event_id: string
    timestamp: string
  } | null>(null)
  const [decisionSubmitting, setDecisionSubmitting] = useState(false)
  const [decisionError, setDecisionError] = useState<string | null>(null)
  const [auditTrail, setAuditTrail] = useState<Array<{
    event_id: string
    actor: string
    action: string
    reason?: string | null
    comment?: string | null
    timestamp: string
  }>>([])

  const DECISION_LABELS: Record<string, string> = {
    APPROVE: 'Approved',
    REQUEST_CLARIFICATION: 'Clarification Requested',
    DO_NOT_PROCEED: 'Not Proceeded',
  }

  useEffect(() => {
    if (!router.isReady) return
    if (documentId) {
      loadComplianceReport()
    } else {
      setLoading(false)
    }
  }, [router.isReady, documentId, bidderIds.join(',')])

  useEffect(() => {
    if (selectedRequirement && report) {
      loadExplanation(selectedRequirement.requirement_id)
    }
  }, [selectedRequirement])

  async function loadComplianceReport() {
    try {
      setLoading(true)
      setError(null)
      setTenderDoc(null)
      setBidderDocs([])

      if (!documentId) {
        setError('No document ID provided')
        return
      }

      let result: ComplianceDecisionReport
      if (isPaired) {
        const paired = await apiPost<PairedResponse>('/compliance/decision/paired', {
          tender_document_id: documentId,
          bidder_document_ids: bidderIds,
        })
        result = paired.report
        // Load doc metadata for the paired header (best-effort).
        try {
          setTenderDoc(await apiGet<DocumentRecord>(`/documents/${encodeURIComponent(paired.tender_document_id)}`))
          setBidderDocs(
            await Promise.all(
              paired.bidder_document_ids.map(
                (id) => apiGet<DocumentRecord>(`/documents/${encodeURIComponent(id)}`)
              )
            )
          )
        } catch {
          /* metadata display is best-effort */
        }
      } else {
        result = await apiPost<ComplianceDecisionReport>('/compliance/decision', {
          document_id: documentId,
        })
      }

      setReport(result)
      if (result.findings && result.findings.length > 0) {
        setSelectedRequirement(result.findings[0])
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to load compliance report: ${err.detail}`)
      } else {
        setError(`Failed to load compliance report: ${err instanceof Error ? err.message : 'Unknown error'}`)
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadExplanation(requirementId: string) {
    try {
      setExplanation(null)
      setExplanationError(null)
      if (!report?.analysis_id) return

      const result = await apiGet<RequirementExplanation>(
        `/compliance/requirements/${encodeURIComponent(requirementId)}/explanation?analysis_id=${encodeURIComponent(report.analysis_id)}`
      )
      setExplanation(result)
    } catch (err) {
      setExplanationError(
        err instanceof ApiError ? err.detail : 'Detailed explanation could not be loaded.'
      )
    }
  }

  // ---- Officer final decision (Phase 8 human decision, audit-chained) ----

  async function loadAuditTrail() {
    if (!report?.report_id) return
    try {
      // Officer decisions are recorded with entity_id = report_id, so the
      // backend-side filter returns only this report's audit events.
      const events = await apiGet<
        Array<{ event_id: string; actor: string; action: string; reason?: string | null; comment?: string | null; timestamp: string; entity_id: string }>
      >(`/review/actions?finding_id=${encodeURIComponent(report.report_id)}&limit=50`)
      // Defense in depth: keep only events scoped to this report entity.
      setAuditTrail(scopeAuditEventsToReport(events, report.report_id))
    } catch {
      setAuditTrail([])
    }
  }

  useEffect(() => {
    if (report) loadAuditTrail()
  }, [report?.report_id])

  async function recordDecision(action: 'APPROVE' | 'REQUEST_CLARIFICATION' | 'DO_NOT_PROCEED') {
    if (!session) {
      setDecisionError('Please log in as an officer before recording a decision.')
      return
    }
    if (!report?.analysis_id || !report?.report_id) {
      setDecisionError('Compliance report is not loaded yet.')
      return
    }
    const needsReason = action !== 'APPROVE'
    if (needsReason && !decisionReason.trim()) {
      setDecisionError('A written reason is required for this decision.')
      return
    }

    setDecisionError(null)
    setDecisionSubmitting(true)
    try {
      const payload = {
        actor: session.officer_id,
        action: action === 'APPROVE' ? 'ACCEPT' : action === 'REQUEST_CLARIFICATION' ? 'COMMENT' : 'OVERRIDE',
        finding_id: report.report_id,
        requirement_id: selectedRequirement?.requirement_id || null,
        analysis_id: report.analysis_id,
        reason:
          action === 'APPROVE'
            ? decisionReason.trim() || `Overall report approved by ${session.name || session.officer_id}`
            : decisionReason.trim(),
        comment:
          action === 'REQUEST_CLARIFICATION'
            ? decisionReason.trim()
            : '',
        metadata: { decision: action, document_id: report.document_id },
      }
      const res = await apiPost<{ audit_event_id: string; status: string }>('/review/actions', payload)

      setDecisionRecorded({
        action,
        label: DECISION_LABELS[action],
        reason: decisionReason.trim(),
        actor: session.name || session.officer_id,
        audit_event_id: res.audit_event_id,
        timestamp: new Date().toISOString(),
      })
      setDecisionAction(null)
      setDecisionReason('')
      await loadAuditTrail()
    } catch (err) {
      setDecisionError(
        err instanceof ApiError ? err.detail : 'Failed to record decision. Please try again.'
      )
    } finally {
      setDecisionSubmitting(false)
    }
  }

  const filteredFindings =
    !report || statusFilter === 'all'
      ? report?.findings || []
      : report.findings.filter((f) => {
          if (statusFilter === 'compliant') return f.status === 'COMPLIANT'
          if (statusFilter === 'review') return f.status === 'REQUIRES_REVIEW' || f.status === 'INSUFFICIENT_EVIDENCE'
          if (statusFilter === 'non-compliant') return f.status === 'POTENTIAL_NON_COMPLIANCE'
          return true
        })

  const statusTone = (status: string) =>
    ({
      COMPLIANT: COLORS.success,
      POTENTIAL_NON_COMPLIANCE: COLORS.error,
      REQUIRES_REVIEW: COLORS.warning,
      INSUFFICIENT_EVIDENCE: COLORS.warning,
      NOT_APPLICABLE: COLORS.textSecondary,
    }[status] || COLORS.textSecondary)

  return (
    <Layout>
      <Head>
        <title>Compliance Review - PolicyGuard AI</title>
      </Head>

      <div>
        <div style={{ marginBottom: '1.75rem' }}>
          <h1 style={{ margin: '0 0 0.5rem 0', fontSize: '1.65rem', fontWeight: 700, color: COLORS.textMain }}>
            Compliance Review
          </h1>
          <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: '0.95rem' }}>
            {isPaired
              ? 'Paired analysis: tender requirements mapped against the bidder submission, with risk and evidence from both PDFs.'
              : documentId
                ? 'Review AI-assisted findings and their evidence.'
                : 'Open this page from the Documents screen to run an analysis.'}
          </p>
        </div>

        {error && <ErrorMessage message={error} onRetry={loadComplianceReport} />}

        {loading ? (
          <Loading text={isPaired ? 'Mapping tender requirements to bidder evidence…' : 'Analyzing compliance requirements…'} />
        ) : !report ? (
          <Card>
            <p style={{ color: COLORS.textSecondary, textAlign: 'center' }}>
              No compliance report available. Please upload and analyze documents first.
            </p>
          </Card>
        ) : (
          <>
            {/* Paired documents header */}
            {isPaired && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  alignItems: 'center',
                  padding: '1rem 1.25rem',
                  marginBottom: '1.5rem',
                  backgroundColor: COLORS.cardBg,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '12px',
                  boxShadow: '0 1px 3px rgba(16,24,40,0.06)',
                }}
              >
                <span style={{ fontSize: '1.3rem' }}>⚖️</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, color: COLORS.textMain, fontSize: '0.9rem' }}>
                    {tenderDoc?.filename || tenderDoc?.document_id || 'Tender'}
                  </span>
                  <DocumentTypeBadge documentType="tender" />
                </div>
                <span style={{ color: COLORS.textSecondary, fontSize: '1rem' }}>×</span>
                {bidderDocs.length > 0 ? (
                  bidderDocs.map((d) => (
                    <div key={d.document_id} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontWeight: 600, color: COLORS.textMain, fontSize: '0.9rem' }}>
                        {d.filename}
                      </span>
                      <DocumentTypeBadge documentType="bidder" />
                    </div>
                  ))
                ) : (
                  <span style={{ fontWeight: 600, color: COLORS.textMain, fontSize: '0.9rem' }}>
                    {bidderIds.length} bidder document(s)
                  </span>
                )}
              </div>
            )}

            {/* KPI strip */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <Card>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Overall Status
                </p>
                <StatusBadge status={report.overall_status} />
              </Card>
              <Card>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Overall Risk
                </p>
                <RiskBadge risk={report.overall_risk} />
              </Card>
              <Card>
                <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Requirements
                </p>
                <p style={{ margin: 0, fontSize: '1.7rem', fontWeight: 700, color: COLORS.navy }}>
                  {report.total_requirements}
                </p>
              </Card>
              <Card>
                <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Compliant
                </p>
                <p style={{ margin: 0, fontSize: '1.7rem', fontWeight: 700, color: COLORS.success }}>
                  {report.compliant_count}
                </p>
              </Card>
              <Card>
                <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Non-Compliant
                </p>
                <p style={{ margin: 0, fontSize: '1.7rem', fontWeight: 700, color: COLORS.error }}>
                  {report.potential_non_compliance_count}
                </p>
              </Card>
              <Card>
                <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  Needs Review
                </p>
                <p style={{ margin: 0, fontSize: '1.7rem', fontWeight: 700, color: COLORS.warning }}>
                  {report.requires_review_count + report.insufficient_evidence_count}
                </p>
              </Card>
            </div>

            {/* Executive summary */}
            {report.executive_summary && (
              <div style={{ marginBottom: '1.5rem' }}>
                <Card title="Executive Summary">
                  <p style={{ margin: 0, color: COLORS.textMain, lineHeight: 1.6 }}>{report.executive_summary}</p>
                </Card>
              </div>
            )}

            <div className="compliance-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 2fr) minmax(340px, 3fr)', gap: '1.5rem', alignItems: 'start' }}>
              {/* Left column: filters + requirements list */}
              <div>
                <Card title={`Requirements (${filteredFindings.length})`}>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                    {[
                      { value: 'all', label: `All (${report.findings.length})` },
                      { value: 'compliant', label: `✓ ${report.compliant_count}` },
                      { value: 'review', label: `⚠ ${report.requires_review_count + report.insufficient_evidence_count}` },
                      { value: 'non-compliant', label: `✕ ${report.potential_non_compliance_count}` },
                    ].map((filter) => (
                      <button
                        key={filter.value}
                        onClick={() => setStatusFilter(filter.value)}
                        style={{
                          padding: '0.45rem 0.85rem',
                          borderRadius: '999px',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          border: `1px solid ${statusFilter === filter.value ? COLORS.navy : COLORS.border}`,
                          backgroundColor: statusFilter === filter.value ? COLORS.navy : 'transparent',
                          color: statusFilter === filter.value ? 'white' : COLORS.textSecondary,
                          transition: 'all 0.2s',
                        }}
                      >
                        {filter.label}
                      </button>
                    ))}
                  </div>

                  {filteredFindings.length === 0 ? (
                    <p style={{ color: COLORS.textSecondary, textAlign: 'center', margin: '1rem 0' }}>
                      No requirements match the selected filter.
                    </p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '560px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                      {filteredFindings.map((finding) => {
                        const selected = selectedRequirement?.requirement_id === finding.requirement_id
                        const tone = statusTone(finding.status)
                        return (
                          <div
                            key={finding.requirement_id}
                            onClick={() => setSelectedRequirement(finding)}
                            style={{
                              padding: '0.8rem 0.9rem',
                              border: selected ? `2px solid ${COLORS.navy}` : `1px solid ${COLORS.border}`,
                              borderRadius: '10px',
                              cursor: 'pointer',
                              backgroundColor: selected ? '#F0F5FA' : COLORS.cardBg,
                              borderLeft: `4px solid ${tone}`,
                              boxShadow: selected ? '0 2px 8px rgba(22,58,95,0.12)' : 'none',
                              transition: 'all 0.15s',
                            }}
                          >
                            <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.87rem', fontWeight: 600, color: COLORS.textMain }}>
                              {finding.requirement_title}
                            </p>
                            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
                              <StatusBadge status={finding.status} size="sm" />
                              <RiskBadge risk={finding.risk_level} size="sm" />
                              {finding.mandatory && (
                                <span style={{ fontSize: '0.68rem', fontWeight: 600, color: COLORS.warning, textTransform: 'uppercase' }}>
                                  Mandatory
                                </span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </Card>
              </div>

              {/* Right column: detail */}
              <div>
                {selectedRequirement ? (
                  <>
                    <Card title="Requirement Details">
                      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                        <StatusBadge status={selectedRequirement.status} />
                        <RiskBadge risk={selectedRequirement.risk_level} />
                      </div>

                      <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                        Title
                      </p>
                      <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontWeight: 600, fontSize: '1.02rem' }}>
                        {selectedRequirement.requirement_title}
                      </p>

                      <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                        Requirement ID
                      </p>
                      <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all' }}>
                        {selectedRequirement.requirement_id}
                      </p>

                      {selectedRequirement.mandatory && (
                        <div
                          style={{
                            padding: '0.7rem 0.9rem',
                            backgroundColor: COLORS.warning + '12',
                            border: `1px solid ${COLORS.warning}55`,
                            borderRadius: '8px',
                            marginBottom: '1rem',
                            fontSize: '0.85rem',
                            color: COLORS.warning,
                          }}
                        >
                          ⚠️ <strong>Mandatory requirement</strong>
                        </div>
                      )}
                      {explanation?.category && (
                        <p style={{ margin: 0, fontSize: '0.87rem', color: COLORS.textSecondary }}>
                          Category: <strong style={{ color: COLORS.textMain }}>{explanation.category}</strong>
                        </p>
                      )}
                    </Card>

                    {explanation && (
                      <div style={{ marginTop: '1rem' }}>
                        <Card title="Evaluation Explanation">
                          <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, lineHeight: 1.6 }}>
                            {explanation.reason}
                          </p>

                          {explanation.evidence_summary && (
                            <>
                              <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                                Evidence
                              </p>
                              <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.87rem', lineHeight: 1.6 }}>
                                {explanation.evidence_summary}
                              </p>
                            </>
                          )}

                          {explanation.regulatory_reference && (
                            <>
                              <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                                Regulatory Reference
                              </p>
                              <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.87rem' }}>
                                {explanation.regulatory_reference}
                                {explanation.regulatory_authority && ` (${explanation.regulatory_authority})`}
                              </p>
                            </>
                          )}

                          {explanation.source_page && (
                            <>
                              <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                                Source Location
                              </p>
                              <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.87rem' }}>
                                Page {explanation.source_page}
                                {explanation.source_section && ` — ${explanation.source_section}`}
                              </p>
                            </>
                          )}

                          {explanation.evidence_trace?.source_text && (
                            <>
                              <p style={{ margin: '0 0 0.35rem 0', fontSize: '0.8rem', color: COLORS.textSecondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                                Source Extract
                              </p>
                              <p
                                style={{
                                  margin: '0 0 1rem 0',
                                  color: COLORS.textMain,
                                  fontSize: '0.82rem',
                                  whiteSpace: 'pre-wrap',
                                  backgroundColor: COLORS.bgLight,
                                  padding: '0.75rem 0.9rem',
                                  borderRadius: '8px',
                                  border: `1px solid ${COLORS.border}`,
                                  maxHeight: '220px',
                                  overflowY: 'auto',
                                }}
                              >
                                {explanation.evidence_trace.source_text}
                              </p>
                            </>
                          )}

                          {explanation.human_review_required && (
                            <div
                              style={{
                                padding: '0.7rem 0.9rem',
                                backgroundColor: COLORS.warning + '12',
                                border: `1px solid ${COLORS.warning}55`,
                                borderRadius: '8px',
                                marginTop: '1rem',
                              }}
                            >
                              <p style={{ margin: 0, fontSize: '0.85rem', color: COLORS.warning }}>
                                👤 <strong>Requires Human Review</strong>
                              </p>
                              {explanation.requires_review_reason && (
                                <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.78rem', color: COLORS.warning }}>
                                  {explanation.requires_review_reason}
                                </p>
                              )}
                            </div>
                          )}
                        </Card>
                      </div>
                    )}

                    {explanationError && (
                      <div style={{ marginTop: '1rem' }}>
                        <ErrorMessage title="Explanation unavailable" message={explanationError} />
                      </div>
                    )}

                    <div style={{ marginTop: '1rem' }}>
                      <Card title="Officer Final Decision">
                        {/* Decision Recorded banner */}
                        {decisionRecorded ? (
                          <div
                            role="status"
                            style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: '0.7rem',
                              padding: '0.85rem 1rem',
                              backgroundColor: COLORS.success + '12',
                              border: `1px solid ${COLORS.success}55`,
                              borderRadius: '10px',
                              marginBottom: '1rem',
                            }}
                          >
                            <span aria-hidden="true" style={{ fontSize: '1.1rem', lineHeight: 1.2 }}>✅</span>
                            <div>
                              <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: COLORS.success }}>
                                Decision Recorded: {decisionRecorded.label}
                              </p>
                              <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.78rem', color: COLORS.textSecondary }}>
                                {decisionRecorded.actor} · {new Date(decisionRecorded.timestamp).toLocaleString()} ·
                                audit event {decisionRecorded.audit_event_id.slice(0, 10)}…
                              </p>
                              {decisionRecorded.reason && (
                                <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.82rem', color: COLORS.textMain }}>
                                  “{decisionRecorded.reason}”
                                </p>
                              )}
                              <button
                                onClick={() => setDecisionRecorded(null)}
                                style={{
                                  marginTop: '0.5rem',
                                  background: 'transparent',
                                  border: 'none',
                                  color: COLORS.blue,
                                  fontSize: '0.78rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              >
                                Record a different decision →
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: COLORS.textSecondary }}>
                            AI analysis is advisory only. Record your final officer decision below — it is
                            written to the tamper-evident audit chain with your officer identity.
                          </p>
                        )}

                        {!session && !decisionRecorded && (
                          <div
                            style={{
                              padding: '0.7rem 0.9rem',
                              backgroundColor: COLORS.warning + '12',
                              border: `1px solid ${COLORS.warning}55`,
                              borderRadius: '8px',
                              marginBottom: '1rem',
                              fontSize: '0.85rem',
                              color: COLORS.warning,
                            }}
                          >
                            🔒 <strong>Officer login required.</strong>{' '}
                            <Link href="/login" style={{ color: COLORS.blue, fontWeight: 600 }}>
                              Sign in
                            </Link>{' '}
                            to record a decision.
                          </div>
                        )}

                        {decisionError && (
                          <p
                            role="alert"
                            style={{
                              margin: '0 0 1rem 0',
                              padding: '0.6rem 0.8rem',
                              backgroundColor: COLORS.error + '12',
                              border: `1px solid ${COLORS.error}55`,
                              borderRadius: '8px',
                              color: COLORS.error,
                              fontSize: '0.82rem',
                            }}
                          >
                            {decisionError}
                          </p>
                        )}

                        {/* Action buttons */}
                        {decisionAction === null && !decisionRecorded && (
                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                              gap: '0.75rem',
                            }}
                          >
                            <button
                              onClick={() => { setDecisionAction('APPROVE'); setDecisionError(null) }}
                              disabled={!session || decisionSubmitting}
                              style={{
                                padding: '0.75rem',
                                backgroundColor: COLORS.success,
                                color: 'white',
                                border: 'none',
                                borderRadius: '8px',
                                fontSize: '0.9rem',
                                fontWeight: 600,
                                cursor: session ? 'pointer' : 'not-allowed',
                                opacity: session ? 1 : 0.5,
                              }}
                            >
                              ✓ Approve
                            </button>
                            <button
                              onClick={() => { setDecisionAction('REQUEST_CLARIFICATION'); setDecisionError(null) }}
                              disabled={!session || decisionSubmitting}
                              style={{
                                padding: '0.75rem',
                                backgroundColor: COLORS.blue,
                                color: 'white',
                                border: 'none',
                                borderRadius: '8px',
                                fontSize: '0.9rem',
                                fontWeight: 600,
                                cursor: session ? 'pointer' : 'not-allowed',
                                opacity: session ? 1 : 0.5,
                              }}
                            >
                              ✉ Request Clarification
                            </button>
                            <button
                              onClick={() => { setDecisionAction('DO_NOT_PROCEED'); setDecisionError(null) }}
                              disabled={!session || decisionSubmitting}
                              style={{
                                padding: '0.75rem',
                                backgroundColor: COLORS.error,
                                color: 'white',
                                border: 'none',
                                borderRadius: '8px',
                                fontSize: '0.9rem',
                                fontWeight: 600,
                                cursor: session ? 'pointer' : 'not-allowed',
                                opacity: session ? 1 : 0.5,
                              }}
                            >
                              ✕ Do Not Proceed
                            </button>
                          </div>
                        )}

                        {/* Reason entry for clarification / do-not-proceed */}
                        {decisionAction !== null && (
                          <div
                            style={{
                              padding: '1rem',
                              backgroundColor: COLORS.bgLight,
                              border: `1px solid ${COLORS.border}`,
                              borderRadius: '10px',
                            }}
                          >
                            <p style={{ margin: '0 0 0.6rem 0', fontSize: '0.88rem', fontWeight: 700, color: COLORS.textMain }}>
                              {decisionAction === 'APPROVE'
                                ? 'Approve this compliance report?'
                                : decisionAction === 'REQUEST_CLARIFICATION'
                                  ? 'Request clarification from the bidder'
                                  : 'Do not proceed with this submission?'}
                            </p>
                            <textarea
                              value={decisionReason}
                              onChange={(e) => setDecisionReason(e.target.value)}
                              placeholder={
                                decisionAction === 'APPROVE'
                                  ? 'Optional note (e.g. evidence verified against official records)'
                                  : 'Written reason (required) — what must the bidder clarify or why is this rejected?'
                              }
                              rows={3}
                              style={{
                                width: '100%',
                                padding: '0.65rem 0.8rem',
                                border: `1px solid ${COLORS.border}`,
                                borderRadius: '8px',
                                fontSize: '0.88rem',
                                color: COLORS.textMain,
                                resize: 'vertical',
                                marginBottom: '0.75rem',
                              }}
                            />
                            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                              <Button
                                onClick={() => decisionAction && recordDecision(decisionAction)}
                                disabled={decisionSubmitting}
                                variant={decisionAction === 'DO_NOT_PROCEED' ? 'danger' : 'primary'}
                              >
                                {decisionSubmitting
                                  ? 'Recording…'
                                  : decisionAction === 'APPROVE'
                                    ? 'Confirm Approve'
                                    : decisionAction === 'REQUEST_CLARIFICATION'
                                      ? 'Confirm Clarification Request'
                                      : 'Confirm Do Not Proceed'}
                              </Button>
                              <Button
                                variant="secondary"
                                onClick={() => { setDecisionAction(null); setDecisionError(null) }}
                                disabled={decisionSubmitting}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* Audit trail */}
                        {auditTrail.length > 0 && (
                          <div style={{ marginTop: '1.25rem' }}>
                            <p style={{ margin: '0 0 0.6rem 0', fontSize: '0.8rem', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                              Audit Trail
                            </p>
                            <div style={{ overflowX: 'auto' }}>
                              <table
                                style={{
                                  width: '100%',
                                  borderCollapse: 'collapse',
                                  fontSize: '0.8rem',
                                  minWidth: '480px',
                                }}
                              >
                                <thead>
                                  <tr>
                                    {['Time', 'Officer', 'Action', 'Reason'].map((h) => (
                                      <th
                                        key={h}
                                        style={{
                                          textAlign: 'left',
                                          padding: '0.45rem 0.6rem',
                                          borderBottom: `2px solid ${COLORS.border}`,
                                          color: COLORS.textSecondary,
                                          fontSize: '0.72rem',
                                          textTransform: 'uppercase',
                                          letterSpacing: '0.4px',
                                          whiteSpace: 'nowrap',
                                        }}
                                      >
                                        {h}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {auditTrail.map((e) => (
                                    <tr key={e.event_id}>
                                      <td style={{ padding: '0.45rem 0.6rem', borderBottom: `1px solid ${COLORS.border}`, whiteSpace: 'nowrap', color: COLORS.textSecondary }}>
                                        {new Date(e.timestamp).toLocaleString()}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textMain, fontWeight: 600 }}>
                                        {e.actor}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textMain }}>
                                        {e.action.replace('REVIEW_', '')}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textSecondary }}>
                                        {e.reason || e.comment || '—'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        <div style={{ marginTop: '1rem' }}>
                          <Link href={`/reports?report_id=${encodeURIComponent(report.report_id)}`}>
                            <Button variant="secondary">View backend decision report →</Button>
                          </Link>
                        </div>
                      </Card>
                    </div>
                  </>
                ) : (
                  <Card>
                    <p style={{ color: COLORS.textSecondary, textAlign: 'center', margin: 0 }}>
                      Select a requirement to view details
                    </p>
                  </Card>
                )}
              </div>
            </div>
          </>
        )}

        <style jsx>{`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
          /* Mobile: stack the requirements list and detail column */
          @media (max-width: 900px) {
            .compliance-grid {
              grid-template-columns: 1fr !important;
            }
          }
        `}</style>
      </div>
    </Layout>
  )
}
