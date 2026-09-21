import { RiskLevel, OverallComplianceStatus, FindingStatus, Severity } from './types'

export const COLORS = {
  navy: '#163A5F',
  blue: '#2F5D8C',
  bgLight: '#F7F8FA',
  cardBg: '#FFFFFF',
  textMain: '#263238',
  textSecondary: '#667085',
  border: '#D9DEE5',
  success: '#2E7D5B',
  warning: '#B7791F',
  error: '#B54747',
}

export function getRiskLevelColor(risk: RiskLevel): string {
  switch (risk) {
    case 'CRITICAL':
      return COLORS.error
    case 'HIGH':
      return COLORS.warning
    case 'MEDIUM':
      return '#D4A520'
    case 'LOW':
      return COLORS.success
    case 'INFO':
      return COLORS.blue
  }
}

export function getStatusColor(status: FindingStatus | OverallComplianceStatus): string {
  if (status === 'COMPLIANT') {
    return COLORS.success
  }
  if (
    status === 'REVIEW_REQUIRED' ||
    status === 'REQUIRES_REVIEW' ||
    status === 'INSUFFICIENT_EVIDENCE'
  ) {
    return COLORS.warning
  }
  if (
    status === 'HIGH_RISK' ||
    status === 'POTENTIAL_NON_COMPLIANCE'
  ) {
    return COLORS.error
  }
  return COLORS.textSecondary
}

export function formatStatusLabel(status: FindingStatus | OverallComplianceStatus): string {
  return status.replace(/_/g, ' ').toUpperCase()
}

export function formatRiskLabel(risk: RiskLevel): string {
  return risk.toUpperCase()
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}
