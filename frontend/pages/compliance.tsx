import React, { useEffect, useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { Layout } from '../components/Layout'
import { Card, StatusBadge, RiskBadge, Button, Loading, ErrorMessage } from '../components/UI'
import { apiPost, apiGet, ApiError } from '../lib/api'
import {
  ComplianceDecisionReport,
  RequirementExplanation,
  ComplianceFinding,
} from '../lib/types'
import { formatStatusLabel, COLORS } from '../lib/utils'

export default function Compliance() {
  const router = useRouter()
  const documentId = typeof router.query.document_id === 'string' ? router.query.document_id : undefined

  const [report, setReport] = useState<ComplianceDecisionReport | null>(null)
  const [selectedRequirement, setSelectedRequirement] = useState<ComplianceFinding | null>(null)
  const [explanation, setExplanation] = useState<RequirementExplanation | null>(null)
  const [explanationError, setExplanationError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    if (documentId) {
      loadComplianceReport()
    }
  }, [documentId])

  useEffect(() => {
    if (selectedRequirement && report) {
      loadExplanation(selectedRequirement.requirement_id)
    }
  }, [selectedRequirement])

  async function loadComplianceReport() {
    try {
      setLoading(true)
      setError(null)

      if (!documentId) {
        setError('No document ID provided')
        return
      }

      const result = await apiPost<ComplianceDecisionReport>('/compliance/decision', {
        document_id: documentId,
      })

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

  const filteredFindings =
    !report || statusFilter === 'all'
      ? report?.findings || []
      : report.findings.filter((f) => {
          if (statusFilter === 'compliant') return f.status === 'COMPLIANT'
          if (statusFilter === 'review') return f.status === 'REQUIRES_REVIEW' || f.status === 'INSUFFICIENT_EVIDENCE'
          if (statusFilter === 'non-compliant') return f.status === 'POTENTIAL_NON_COMPLIANCE'
          return true
        })

  return (
    <Layout>
      <Head>
        <title>Compliance Review - PolicyGuard AI</title>
      </Head>

      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>Compliance Review</h1>
        <p style={{ margin: 0, color: COLORS.textSecondary }}>
          {documentId ? 'Review AI-assisted findings and their evidence' : 'Select a document to review'}
        </p>
      </div>

      {error && <ErrorMessage message={error} onRetry={loadComplianceReport} />}

      {loading ? (
        <Loading text="Analyzing compliance requirements..." />
      ) : !report ? (
        <Card>
          <p style={{ color: COLORS.textSecondary, textAlign: 'center' }}>
            No compliance report available. Please upload and analyze a document first.
          </p>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
          {/* Left Column: Report Summary & Requirements List */}
          <div>
            {/* Summary */}
            <Card
              title="Summary"
              subtitle={`Overall Status: ${formatStatusLabel(report.overall_status)}`}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Status
                  </p>
                  <StatusBadge status={report.overall_status} />
                </div>
                <div>
                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Risk Level
                  </p>
                  <RiskBadge risk={report.overall_risk} />
                </div>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '1rem',
                  marginTop: '1rem',
                  paddingTop: '1rem',
                  borderTop: `1px solid ${COLORS.border}`,
                }}
              >
                <div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Requirements
                  </p>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '1.5rem', fontWeight: 'bold', color: COLORS.navy }}>
                    {report.total_requirements}
                  </p>
                </div>
                <div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Compliant
                  </p>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '1.5rem', fontWeight: 'bold', color: COLORS.success }}>
                    {report.compliant_count}
                  </p>
                </div>
              </div>
            </Card>

            {/* Status Filter */}
            <div style={{ marginTop: '1rem' }}>
              <Card>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {[
                  { value: 'all', label: `All (${report.findings.length})` },
                  { value: 'compliant', label: `Compliant (${report.compliant_count})` },
                  { value: 'review', label: `Review (${report.requires_review_count + report.insufficient_evidence_count})` },
                  {
                    value: 'non-compliant',
                    label: `Non-Compliant (${report.potential_non_compliance_count})`,
                  },
                ].map((filter) => (
                  <Button
                    key={filter.value}
                    onClick={() => setStatusFilter(filter.value)}
                    variant={statusFilter === filter.value ? 'primary' : 'secondary'}
                    style={{ fontSize: '0.75rem', padding: '0.5rem 0.75rem' }}
                  >
                    {filter.label}
                  </Button>
                ))}
                </div>
              </Card>
            </div>

            {/* Requirements List */}
            <div style={{ marginTop: '1rem' }}>
            <Card title="Requirements">
              {filteredFindings.length === 0 ? (
                <p style={{ color: COLORS.textSecondary, textAlign: 'center', margin: 0 }}>
                  No requirements match the selected filter.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '600px', overflowY: 'auto' }}>
                  {filteredFindings.map((finding) => (
                    <div
                      key={finding.requirement_id}
                      onClick={() => setSelectedRequirement(finding)}
                      style={{
                        padding: '0.75rem',
                        border:
                          selectedRequirement?.requirement_id === finding.requirement_id
                            ? `2px solid ${COLORS.navy}`
                            : `1px solid ${COLORS.border}`,
                        borderRadius: '4px',
                        cursor: 'pointer',
                        backgroundColor:
                          selectedRequirement?.requirement_id === finding.requirement_id
                            ? COLORS.bgLight
                            : 'transparent',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '0.5rem' }}>
                        <div style={{ flex: 1 }}>
                          <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.875rem', fontWeight: 500, color: COLORS.textMain }}>
                            {finding.requirement_title}
                          </p>
                          <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
                            ID: {finding.requirement_id}
                          </p>
                        </div>
                      </div>
                      <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <StatusBadge status={finding.status} size="sm" />
                        <RiskBadge risk={finding.risk_level} size="sm" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
            </div>
          </div>

          {/* Right Column: Requirement Detail */}
          <div>
            {selectedRequirement ? (
              <>
                <Card title="Requirement Details">
                  <p style={{ margin: '0 0 1rem 0', fontSize: '0.75rem', color: COLORS.textSecondary }}>
                    AI-assisted assessment from the backend. It is advisory and preserves the available evidence and provenance below.
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                    <StatusBadge status={selectedRequirement.status} />
                    <RiskBadge risk={selectedRequirement.risk_level} />
                  </div>

                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Title
                  </p>
                  <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontWeight: 500 }}>
                    {selectedRequirement.requirement_title}
                  </p>

                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    Requirement ID
                  </p>
                  <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontFamily: 'monospace', fontSize: '0.875rem' }}>
                    {selectedRequirement.requirement_id}
                  </p>

                  {selectedRequirement.mandatory && (
                    <div
                      style={{
                        padding: '0.75rem',
                        backgroundColor: COLORS.warning + '15',
                        border: `1px solid ${COLORS.warning}`,
                        borderRadius: '4px',
                        marginBottom: '1rem',
                      }}
                    >
                      <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.warning }}>
                        ⚠️ <strong>Mandatory Requirement</strong>
                      </p>
                    </div>
                  )}
                  {explanation?.category && (
                    <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
                      Category: <strong style={{ color: COLORS.textMain }}>{explanation.category}</strong>
                    </p>
                  )}
                </Card>

                {/* Explanation */}
                {explanation && (
                  <div style={{ marginTop: '1rem' }}>
                  <Card title="Evaluation Explanation">
                    <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain }}>
                      {explanation.reason}
                    </p>

                    {explanation.evidence_summary && (
                      <>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Evidence
                        </p>
                        <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.875rem' }}>
                          {explanation.evidence_summary}
                        </p>
                      </>
                    )}

                    {explanation.regulatory_reference && (
                      <>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Regulatory Reference
                        </p>
                        <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.875rem' }}>
                          {explanation.regulatory_reference}
                          {explanation.regulatory_authority && ` (${explanation.regulatory_authority})`}
                        </p>
                      </>
                    )}

                    {explanation.source_page && (
                      <>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Source Location
                        </p>
                        <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.875rem' }}>
                          Page {explanation.source_page}
                          {explanation.source_section && ` - ${explanation.source_section}`}
                        </p>
                      </>
                    )}

                    {explanation.evidence_trace?.source_text && (
                      <>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Source Extract
                        </p>
                        <p style={{ margin: '0 0 1rem 0', color: COLORS.textMain, fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>
                          {explanation.evidence_trace.source_text}
                        </p>
                      </>
                    )}

                    {explanation.human_review_required && (
                      <div
                        style={{
                          padding: '0.75rem',
                          backgroundColor: COLORS.warning + '15',
                          border: `1px solid ${COLORS.warning}`,
                          borderRadius: '4px',
                          marginTop: '1rem',
                        }}
                      >
                        <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.warning }}>
                          👤 <strong>Requires Human Review</strong>
                        </p>
                        {explanation.requires_review_reason && (
                          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem', color: COLORS.warning }}>
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
                  <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                    The backend provides AI-assisted analysis only. No Phase 8 endpoint records an officer decision, so this screen does not simulate or persist one.
                  </p>
                  <Link href={`/reports?report_id=${encodeURIComponent(report.report_id)}`}>
                    <Button variant="secondary">View backend decision report</Button>
                  </Link>
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
      )}

      <style jsx>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </Layout>
  )
}
