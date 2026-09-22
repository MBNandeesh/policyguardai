import React, { useEffect, useState } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'
import { useAuth } from '../lib/auth'
import { apiGet } from '../lib/api'
import { COLORS } from '../lib/utils'

export default function Login() {
  const router = useRouter()
  const { session, loading, login } = useAuth()
  const [officerId, setOfficerId] = useState('officer-001')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [officers, setOfficers] = useState<Array<{ officer_id: string; name: string }>>([])
  const expired = router.query.expired === '1'

  useEffect(() => {
    if (!loading && session) {
      router.replace('/')
    }
  }, [loading, session])

  useEffect(() => {
    apiGet<Array<{ officer_id: string; name: string }>>('/auth/officers')
      .then(setOfficers)
      .catch(() => setOfficers([]))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(officerId.trim(), password)
      router.replace('/')
    } catch (err: any) {
      setError(err?.detail || 'Login failed. Check your officer ID and password.')
    } finally {
      setSubmitting(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.7rem 0.9rem',
    border: `1px solid ${COLORS.border}`,
    borderRadius: '8px',
    fontSize: '0.95rem',
    color: COLORS.textMain,
    backgroundColor: 'white',
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
        background: `linear-gradient(135deg, ${COLORS.navy} 0%, ${COLORS.blue} 100%)`,
      }}
    >
      <Head>
        <title>Officer Login - PolicyGuard AI</title>
      </Head>

      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          backgroundColor: 'white',
          borderRadius: '16px',
          boxShadow: '0 12px 40px rgba(10, 25, 41, 0.35)',
          padding: '2rem',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '52px',
              height: '52px',
              borderRadius: '12px',
              background: `linear-gradient(135deg, ${COLORS.navy} 0%, ${COLORS.blue} 100%)`,
              color: 'white',
              fontSize: '1.5rem',
              marginBottom: '0.75rem',
            }}
          >
            🛡️
          </span>
          <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: COLORS.textMain }}>
            PolicyGuard AI
          </h1>
          <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: COLORS.textSecondary }}>
            Officer sign-in for compliance decisions
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {expired && (
            <p
              role="alert"
              style={{
                margin: '0 0 1rem 0',
                padding: '0.6rem 0.8rem',
                backgroundColor: COLORS.warning + '12',
                border: `1px solid ${COLORS.warning}55`,
                borderRadius: '8px',
                color: COLORS.textMain,
                fontSize: '0.85rem',
              }}
            >
              Your session expired. Please sign in again.
            </p>
          )
          }
          <label
            htmlFor="officer-id"
            style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: COLORS.textSecondary, marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.4px' }}
          >
            Officer ID
          </label>
          <input
            id="officer-id"
            type="text"
            value={officerId}
            onChange={(e) => setOfficerId(e.target.value)}
            placeholder="e.g. officer-001"
            autoComplete="username"
            style={{ ...inputStyle, marginBottom: '1rem' }}
          />

          <label
            htmlFor="password"
            style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: COLORS.textSecondary, marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.4px' }}
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            autoComplete="current-password"
            style={{ ...inputStyle, marginBottom: '1.25rem' }}
          />

          {error && (
            <p
              role="alert"
              style={{
                margin: '0 0 1rem 0',
                padding: '0.6rem 0.8rem',
                backgroundColor: COLORS.error + '12',
                border: `1px solid ${COLORS.error}55`,
                borderRadius: '8px',
                color: COLORS.error,
                fontSize: '0.85rem',
              }}
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting || !officerId.trim() || !password}
            style={{
              width: '100%',
              padding: '0.8rem',
              border: 'none',
              borderRadius: '8px',
              background: `linear-gradient(90deg, ${COLORS.navy} 0%, ${COLORS.blue} 100%)`,
              color: 'white',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: submitting ? 'wait' : 'pointer',
              opacity: submitting || !officerId.trim() || !password ? 0.7 : 1,
            }}
          >
            {submitting ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {officers.length > 0 && (
          <p style={{ margin: '1.25rem 0 0 0', fontSize: '0.78rem', color: COLORS.textSecondary, textAlign: 'center' }}>
            Registered officers: {officers.map((o) => o.officer_id).join(', ')}
          </p>
        )}

        <p
          style={{
            margin: '0.75rem 0 0 0',
            padding: '0.6rem 0.8rem',
            backgroundColor: COLORS.bgLight,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '8px',
            fontSize: '0.78rem',
            color: COLORS.textSecondary,
            textAlign: 'center',
          }}
        >
          Sign in with your officer ID. Demo deployments use the officer ID
          shown above and the configured demo password (default
          {' '}<strong>officer123</strong> in development).
        </p>
      </div>
    </div>
  )
}
