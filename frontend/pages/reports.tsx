import React, { useEffect, useState } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'
import { Layout } from '../components/Layout'
import { Card, StatusBadge, RiskBadge, Loading, ErrorMessage } from '../components/UI'
import { ComplianceDecisionReport } from '../lib/types'
import { apiGet, ApiError } from '../lib/api'
import { formatDate, COLORS } from '../lib/utils'

export default function Reports() {
  const router = useRouter()
  const reportId = typeof router.query.report_id === 'string' ? router.query.report_id : undefined
  const [reports, setReports] = useState<ComplianceDecisionReport[]>([])
  const [selectedReport, setSelectedReport] = useState<ComplianceDecisionReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!router.isReady) return
    if (!reportId) {
      setReports([])
      setSelectedReport(null)
      setError(null)
      setLoading(false)
      return
    }
    loadReport(reportId)
  }, [router.isReady, reportId])

  async function loadReport(id: string) {
    try {
      setLoading(true)
      setError(null)
      const report = await apiGet<ComplianceDecisionReport>(`/compliance/decision/${encodeURIComponent(id)}`)
      setReports([report])
      setSelectedReport(report)
    } catch (err) {
      setReports([])
      setSelectedReport(null)
      setError(err instanceof ApiError ? err.detail : 'Compliance report could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <Head>
        <title>Reports - PolicyGuard AI</title>
      </Head>

      <div>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>Compliance Reports</h1>
          <p style={{ margin: 0, color: COLORS.textSecondary }}>
            View and manage compliance assessment reports.
          </p>
        </div>

        {error && <ErrorMessage message={error} onRetry={reportId ? () => loadReport(reportId) : undefined} />}

        {loading ? (
          <Loading text="Loading reports..." />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
            {/* Reports List */}
            <div>
              <Card title="Recent Reports">
                {reports.length === 0 ? (
                  <p style={{ color: COLORS.textSecondary, textAlign: 'center', margin: 0, fontSize: '0.875rem' }}>
                    {reportId ? 'No report was returned for this identifier.' : 'Open this page from a compliance review to load a backend report. The API does not provide a report-list endpoint.'}
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {reports.map((report) => (
                      <div
                        key={report.report_id}
                        onClick={() => setSelectedReport(report)}
                        style={{
                          padding: '0.75rem',
                          border:
                            selectedReport?.report_id === report.report_id
                              ? `2px solid ${COLORS.navy}`
                              : `1px solid ${COLORS.border}`,
                          borderRadius: '4px',
                          cursor: 'pointer',
                          backgroundColor:
                            selectedReport?.report_id === report.report_id
                              ? COLORS.bgLight
                              : 'transparent',
                          transition: 'all 0.2s',
                        }}
                      >
                        <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.875rem', fontWeight: 500 }}>
                          {report.document_id}
                        </p>
                        <StatusBadge status={report.overall_status} size="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            {/* Report Detail */}
            <div>
              {selectedReport ? (
                <>
                  {/* Summary */}
                  <Card title="Report Summary">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                      <div>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Overall Status
                        </p>
                        <StatusBadge status={selectedReport.overall_status} />
                      </div>
                      <div>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                          Risk Level
                        </p>
                        <RiskBadge risk={selectedReport.overall_risk} />
                      </div>
                    </div>

                    <div style={{ paddingTop: '1rem', borderTop: `1px solid ${COLORS.border}` }}>
                      <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
                        Generated
                      </p>
                      <p style={{ margin: 0, color: COLORS.textMain, fontSize: '0.875rem' }}>
                        {formatDate(selectedReport.generated_at)}
                      </p>
                    </div>
                  </Card>

                  {/* Statistics */}
                  <div style={{ marginTop: '1rem' }}>
                  <Card title="Statistics">
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '1rem',
                      }}
                    >
                      <div>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
                          Total Requirements
                        </p>
                        <p style={{ margin: '0.5rem 0 0 0', fontSize: '1.25rem', fontWeight: 'bold' }}>
                          {selectedReport.total_requirements}
                        </p>
                      </div>
                      <div>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
                          Compliant
                        </p>
                        <p
                          style={{
                            margin: '0.5rem 0 0 0',
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: COLORS.success,
                          }}
                        >
                          {selectedReport.compliant_count}
                        </p>
                      </div>
                      <div>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
                          Requires Review
                        </p>
                        <p
                          style={{
                            margin: '0.5rem 0 0 0',
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: COLORS.warning,
                          }}
                        >
                          {selectedReport.requires_review_count}
                        </p>
                      </div>
                      <div>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
                          Non-Compliant
                        </p>
                        <p
                          style={{
                            margin: '0.5rem 0 0 0',
                            fontSize: '1.25rem',
                            fontWeight: 'bold',
                            color: COLORS.error,
                          }}
                        >
                          {selectedReport.potential_non_compliance_count}
                        </p>
                      </div>
                    </div>
                  </Card>
                  </div>

                  {/* Executive Summary */}
                  {selectedReport.executive_summary && (
                    <div style={{ marginTop: '1rem' }}>
                    <Card title="Executive Summary">
                      <p style={{ margin: 0, color: COLORS.textMain, lineHeight: 1.6 }}>
                        {selectedReport.executive_summary}
                      </p>
                    </Card>
                    </div>
                  )}

                  {/* Key Findings */}
                  {selectedReport.key_findings && selectedReport.key_findings.length > 0 && (
                    <div style={{ marginTop: '1rem' }}>
                    <Card title="Key Findings">
                      <ul
                        style={{
                          margin: 0,
                          paddingLeft: '1.5rem',
                          color: COLORS.textMain,
                          fontSize: '0.875rem',
                        }}
                      >
                        {selectedReport.key_findings.map((finding, i) => (
                          <li key={i} style={{ marginBottom: '0.5rem' }}>
                            {finding}
                          </li>
                        ))}
                      </ul>
                    </Card>
                    </div>
                  )}

                </>
              ) : (
                <Card>
                  <p style={{ color: COLORS.textSecondary, textAlign: 'center', margin: 0 }}>
                    Select a report to view details
                  </p>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
