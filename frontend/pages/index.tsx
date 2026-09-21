import React from 'react'
import Link from 'next/link'
import Head from 'next/head'
import { Layout } from '../components/Layout'
import { Card, Button } from '../components/UI'
import { COLORS } from '../lib/utils'

export default function Dashboard() {
  return (
    <Layout>
      <Head>
        <title>Dashboard - PolicyGuard AI</title>
      </Head>

      <div>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: '0 0 0.5rem 0', color: COLORS.textMain }}>
            Procurement Compliance Dashboard
          </h1>
          <p style={{ margin: 0, color: COLORS.textSecondary }}>
            Manage and review tender compliance assessments at a glance.
          </p>
        </div>

        <>
            <Card title="Quick Actions" subtitle="Start a new compliance assessment">
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <Link href="/documents">
                  <Button style={{ cursor: 'pointer' }}>📄 Upload Document</Button>
                </Link>
                <Link href="/compliance">
                  <Button variant="secondary" style={{ cursor: 'pointer' }}>✓ Review Compliance</Button>
                </Link>
                <Link href="/reports">
                  <Button variant="secondary" style={{ cursor: 'pointer' }}>📋 View Reports</Button>
                </Link>
              </div>
            </Card>

            <div style={{ marginTop: '2rem' }}>
            <Card
              title="Getting Started"
              subtitle="Follow these steps to complete your first compliance assessment"
            >
              <ol
                style={{
                  margin: 0,
                  paddingLeft: '1.5rem',
                  color: COLORS.textMain,
                  lineHeight: 1.8,
                }}
              >
                <li style={{ marginBottom: '0.75rem' }}>
                  <strong>Upload a tender PDF</strong> using the Documents section
                </li>
                <li style={{ marginBottom: '0.75rem' }}>
                  <strong>Wait for analysis</strong> – PolicyGuard AI will extract requirements
                </li>
                <li style={{ marginBottom: '0.75rem' }}>
                  <strong>Review findings</strong> in the Compliance Review section
                </li>
                <li style={{ marginBottom: '0.75rem' }}>
                  <strong>Review AI-assisted findings</strong> and record any final officer decision in the authorized system
                </li>
                <li style={{ marginBottom: 0 }}>
                  <strong>Generate report</strong> for your records
                </li>
              </ol>
            </Card>
            </div>

            <div style={{ marginTop: '2rem' }}>
            <Card title="System Status" subtitle="Integration scope">
              <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: '0.875rem' }}>
                No aggregate dashboard endpoint is available. Document, compliance, and report screens display backend data when it is requested.
              </p>
            </Card>
            </div>
        </>
      </div>

      <style jsx>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Layout>
  )
}
