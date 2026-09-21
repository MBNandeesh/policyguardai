import React from 'react'
import { RiskLevel, FindingStatus, OverallComplianceStatus } from '../lib/types'
import { getStatusColor, getRiskLevelColor, formatStatusLabel, formatRiskLabel, COLORS } from '../lib/utils'

interface StatusBadgeProps {
  status: FindingStatus | OverallComplianceStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const color = getStatusColor(status)
  const fontSize = size === 'sm' ? '0.75rem' : '0.875rem'
  const padding = size === 'sm' ? '0.25rem 0.75rem' : '0.375rem 0.875rem'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding,
        backgroundColor: color + '15',
        border: `1px solid ${color}`,
        borderRadius: '4px',
        fontSize,
        fontWeight: 500,
        color,
      }}
    >
      <span style={{ width: '0.5rem', height: '0.5rem', borderRadius: '50%', backgroundColor: color }} />
      {formatStatusLabel(status)}
    </span>
  )
}

interface RiskBadgeProps {
  risk: RiskLevel
  size?: 'sm' | 'md'
}

export function RiskBadge({ risk, size = 'md' }: RiskBadgeProps) {
  const color = getRiskLevelColor(risk)
  const fontSize = size === 'sm' ? '0.75rem' : '0.875rem'
  const padding = size === 'sm' ? '0.25rem 0.75rem' : '0.375rem 0.875rem'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding,
        backgroundColor: color + '15',
        border: `1px solid ${color}`,
        borderRadius: '4px',
        fontSize,
        fontWeight: 500,
        color,
      }}
    >
      <span style={{ width: '0.5rem', height: '0.5rem', borderRadius: '50%', backgroundColor: color }} />
      {formatRiskLabel(risk)}
    </span>
  )
}

interface CardProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
}

export function Card({ children, title, subtitle }: CardProps) {
  return (
    <div
      style={{
        backgroundColor: COLORS.cardBg,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '6px',
        overflow: 'hidden',
      }}
    >
      {(title || subtitle) && (
        <div style={{ padding: '1.5rem', borderBottom: `1px solid ${COLORS.border}` }}>
          {title && <h3 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>{title}</h3>}
          {subtitle && (
            <p style={{ margin: 0, fontSize: '0.875rem', color: COLORS.textSecondary }}>
              {subtitle}
            </p>
          )}
        </div>
      )}
      <div style={{ padding: '1.5rem' }}>{children}</div>
    </div>
  )
}

interface LoadingProps {
  text?: string
}

export function Loading({ text = 'Loading...' }: LoadingProps) {
  return (
    <div style={{ textAlign: 'center', padding: '2rem' }}>
      <div
        style={{
          display: 'inline-block',
          width: '2rem',
          height: '2rem',
          border: `3px solid ${COLORS.bgLight}`,
          borderTop: `3px solid ${COLORS.blue}`,
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }}
      />
      <p style={{ marginTop: '1rem', color: COLORS.textSecondary }}>{text}</p>
    </div>
  )
}

interface ErrorProps {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorMessage({ title = 'Error', message, onRetry }: ErrorProps) {
  return (
    <div
      style={{
        backgroundColor: COLORS.error + '15',
        border: `1px solid ${COLORS.error}`,
        borderRadius: '6px',
        padding: '1rem',
        color: COLORS.error,
      }}
    >
      <h4 style={{ margin: '0 0 0.5rem 0' }}>{title}</h4>
      <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem' }}>{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: COLORS.error,
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 500,
          }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

interface ButtonProps {
  children: React.ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'danger'
  disabled?: boolean
  type?: 'button' | 'submit'
  style?: React.CSSProperties
}

export function Button({ children, onClick, variant = 'primary', disabled = false, type = 'button', style }: ButtonProps) {
  const baseStyle: React.CSSProperties = {
    padding: '0.625rem 1rem',
    border: 'none',
    borderRadius: '4px',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'all 0.2s',
    ...style,
  }

  const variantStyle: React.CSSProperties =
    variant === 'primary'
      ? {
          backgroundColor: COLORS.navy,
          color: 'white',
        }
      : variant === 'secondary'
        ? {
            backgroundColor: COLORS.bgLight,
            color: COLORS.navy,
            border: `1px solid ${COLORS.border}`,
          }
        : {
            backgroundColor: COLORS.error,
            color: 'white',
          }

  return (
    <button type={type} onClick={onClick} disabled={disabled} style={{ ...baseStyle, ...variantStyle }}>
      {children}
    </button>
  )
}

interface KPICardProps {
  label: string
  value: string | number
  subtext?: string
}

export function KPICard({ label, value, subtext }: KPICardProps) {
  return (
    <Card>
      <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: COLORS.textSecondary }}>
        {label}
      </p>
      <h2 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>
        {value}
      </h2>
      {subtext && (
        <p style={{ margin: 0, fontSize: '0.75rem', color: COLORS.textSecondary }}>
          {subtext}
        </p>
      )}
    </Card>
  )
}
