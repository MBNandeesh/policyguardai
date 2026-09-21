import React from 'react'
import Link from 'next/link'
import Head from 'next/head'
import { Layout } from '../components/Layout'
import { Card, Button } from '../components/UI'
import { COLORS } from '../lib/utils'

const ACTIONS = [
  {
    href: '/documents',
    icon: '📤',
    title: 'Upload Documents',
    text: 'Add the tender PDF and the bidder PDF for paired analysis.',
    accent: COLORS.blue,
  },
  {
    href: '/compliance',
    icon: '⚖️',
    title: 'Review Compliance',
    text: 'See requirements, risk levels, evidence and review queue.',
    accent: COLORS.success,
  },
  {
    href: '/reports',
    icon: '📋',
    title: 'View Reports',
    text: 'Open the backend decision report with full provenance.',
    accent: COLORS.warning,
  },
]

const STEPS = [
  { icon: '📑', title: 'Upload the tender', text: 'The NIT / RFP states the requirements.' },
  { icon: '📨', title: 'Upload the bidder PDF', text: 'The bid submission contains the evidence.' },
  { icon: '🔗', title: 'Paired mapping', text: 'Each tender requirement is mapped to evidence from both PDFs.' },
  { icon: '⚖️', title: 'Decision & risk', text: 'Grounded evaluation produces status, risk and a human review queue.' },
]

export default function Dashboard() {
  return (
    <Layout>
      <Head>
        <title>Dashboard - PolicyGuard AI</title>
      </Head>

      <div>
        {/* Hero */}
        <div
          style={{
            background: `linear-gradient(135deg, ${COLORS.navy} 0%, ${COLORS.blue} 100%)`,
            borderRadius: '16px',
            padding: '2.25rem 2rem',
            color: 'white',
            marginBottom: '2rem',
            boxShadow: '0 8px 24px rgba(22,58,95,0.25)',
          }}
        >
          <h1 style={{ margin: '0 0 0.6rem 0', fontSize: '1.8rem', fontWeight: 700, lineHeight: 1.25 }}>
            Procurement Compliance Dashboard
          </h1>
          <p style={{ margin: '0 0 1.5rem 0', opacity: 0.9, maxWidth: '640px', fontSize: '0.95rem', lineHeight: 1.6 }}>
            Upload the tender and bidder PDFs together — PolicyGuard maps every tender requirement
            onto the bidder&apos;s submitted evidence and produces a grounded compliance decision with
            risk classification and a human review queue.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link href="/documents">
              <Button
                style={{
                  backgroundColor: 'white',
                  color: COLORS.navy,
                  fontWeight: 600,
                  padding: '0.7rem 1.4rem',
                  cursor: 'pointer',
                }}
              >
                📤 Upload Documents
              </Button>
            </Link>
            <Link href="/compliance">
              <Button
                variant="secondary"
                style={{
                  backgroundColor: 'rgba(255,255,255,0.12)',
                  color: 'white',
                  border: '1px solid rgba(255,255,255,0.35)',
                  fontWeight: 600,
                  padding: '0.7rem 1.4rem',
                  cursor: 'pointer',
                }}
              >
                ⚖️ Compliance Review
              </Button>
            </Link>
          </div>
        </div>

        {/* Quick actions */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          {ACTIONS.map((action) => (
            <Link key={action.href} href={action.href} style={{ textDecoration: 'none' }}>
              <div
                style={{
                  height: '100%',
                  backgroundColor: COLORS.cardBg,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '12px',
                  padding: '1.4rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 3px rgba(16,24,40,0.06)',
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '44px',
                    height: '44px',
                    borderRadius: '11px',
                    backgroundColor: action.accent + '15',
                    fontSize: '1.3rem',
                    marginBottom: '0.85rem',
                  }}
                >
                  {action.icon}
                </span>
                <p style={{ margin: '0 0 0.35rem 0', fontWeight: 700, color: COLORS.textMain, fontSize: '1rem' }}>
                  {action.title}
                </p>
                <p style={{ margin: 0, fontSize: '0.85rem', color: COLORS.textSecondary, lineHeight: 1.55 }}>
                  {action.text}
                </p>
              </div>
            </Link>
          ))}
        </div>

        {/* Workflow */}
        <Card title="How it works" subtitle="From two PDFs to a grounded compliance decision">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem' }}>
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                style={{
                  position: 'relative',
                  padding: '1.1rem',
                  backgroundColor: COLORS.bgLight,
                  borderRadius: '10px',
                  border: `1px solid ${COLORS.border}`,
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: '-10px',
                    left: '1rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minWidth: '22px',
                    height: '22px',
                    padding: '0 6px',
                    borderRadius: '999px',
                    backgroundColor: COLORS.navy,
                    color: 'white',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                  }}
                >
                  {i + 1}
                </span>
                <div style={{ fontSize: '1.4rem', marginTop: '0.35rem', marginBottom: '0.45rem' }}>{step.icon}</div>
                <p style={{ margin: '0 0 0.3rem 0', fontWeight: 600, color: COLORS.textMain, fontSize: '0.92rem' }}>
                  {step.title}
                </p>
                <p style={{ margin: 0, fontSize: '0.82rem', color: COLORS.textSecondary, lineHeight: 1.55 }}>
                  {step.text}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <div style={{ marginTop: '1.5rem' }}>
          <Card title="System Status" subtitle="Integration scope">
            <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: '0.87rem' }}>
              Analysis is AI-assisted and advisory only. Document, compliance, and report screens display
              backend data when it is requested. The final decision remains with the authorized officer.
            </p>
          </Card>
        </div>
      </div>
    </Layout>
  )
}
