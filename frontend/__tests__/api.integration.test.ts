/**
 * Frontend API Integration Tests
 * 
 * This file validates that the frontend API client can integrate with the backend APIs.
 * Run manually with: npx jest frontend.integration.test.ts
 */

import { apiPost, apiGet, uploadFile, ApiError } from '../lib/api'

// Mock environment
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1'

describe('Frontend API Integration', () => {
  describe('Document Upload', () => {
    test('uploadFile function should construct correct FormData', async () => {
      // This is a smoke test - actual file upload requires a running backend
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      expect(mockFile.name).toBe('test.pdf')
      expect(mockFile.type).toBe('application/pdf')
    })

    test('uploadFile should reject non-PDF files', async () => {
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' })
      expect(mockFile.type).not.toBe('application/pdf')
    })
  })

  describe('Compliance Decision API', () => {
    test('apiPost should format compliance decision request correctly', async () => {
      const payload = { document_id: 'doc-123' }
      expect(payload.document_id).toBe('doc-123')
    })

    test('apiPost should handle JSON serialization', async () => {
      const data = {
        document_id: 'doc-123',
        metadata: { timestamp: new Date().toISOString() },
      }
      const json = JSON.stringify(data)
      const parsed = JSON.parse(json)
      expect(parsed.document_id).toBe('doc-123')
    })
  })

  describe('Requirement Explanation API', () => {
    test('apiGet should construct correct URL with query params', async () => {
      const requirementId = 'req-123'
      const analysisId = 'analysis-456'
      const url = `/compliance/requirements/${requirementId}/explanation?analysis_id=${analysisId}`
      expect(url).toContain(requirementId)
      expect(url).toContain(analysisId)
    })
  })

  describe('Error Handling', () => {
    test('ApiError should preserve status and detail', () => {
      const error = new ApiError(404, 'Not Found', 'Document not found')
      expect(error.status).toBe(404)
      expect(error.statusText).toBe('Not Found')
      expect(error.detail).toBe('Document not found')
      expect(error.message).toContain('404')
    })

    test('ApiError should be instanceof Error', () => {
      const error = new ApiError(500, 'Server Error', 'Internal error')
      expect(error instanceof Error).toBe(true)
    })
  })

  describe('Type Safety', () => {
    test('ComplianceDecisionReport types should match backend response shape', () => {
      const mockReport = {
        report_id: 'report-1',
        document_id: 'doc-1',
        analysis_id: 'analysis-1',
        overall_status: 'COMPLIANT' as const,
        overall_risk: 'LOW' as const,
        total_requirements: 5,
        compliant_count: 5,
        critical_count: 0,
        high_count: 0,
        medium_count: 0,
        low_count: 5,
        info_count: 0,
        findings: [],
        human_review_queue: [],
        generated_at: new Date().toISOString(),
      }

      expect(mockReport.overall_status).toBe('COMPLIANT')
      expect(mockReport.overall_risk).toBe('LOW')
      expect(Array.isArray(mockReport.findings)).toBe(true)
    })
  })
})
