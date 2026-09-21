import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { COLORS } from '../lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const navItems = [
    { label: 'Dashboard', href: '/', icon: '📊' },
    { label: 'Documents', href: '/documents', icon: '📄' },
    { label: 'Compliance Review', href: '/compliance', icon: '✓' },
    { label: 'Reports', href: '/reports', icon: '📋' },
  ]

  const isActive = (href: string) => router.pathname === href

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: COLORS.bgLight }}>
      {/* Header */}
      <header
        style={{
          backgroundColor: COLORS.navy,
          color: 'white',
          padding: '1rem 2rem',
          borderBottom: `1px solid ${COLORS.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>PolicyGuard AI</h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem', opacity: 0.9 }}>
            AI-Assisted Procurement Compliance Verification
          </p>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="md:hidden"
          style={{
            background: 'none',
            border: 'none',
            color: 'white',
            fontSize: '1.5rem',
            cursor: 'pointer',
          }}
        >
          ☰
        </button>
      </header>

      <div style={{ display: 'flex', flex: 1 }}>
        {/* Sidebar Navigation */}
        <nav
          className={sidebarOpen
            ? 'max-md:absolute max-md:top-[120px] max-md:left-0 max-md:right-0 max-md:z-[1000] max-md:border-b'
            : 'max-md:hidden max-md:absolute max-md:top-[120px] max-md:left-0 max-md:right-0 max-md:z-[1000] max-md:border-b'}
          style={{
            width: '250px',
            backgroundColor: COLORS.cardBg,
            borderRight: `1px solid ${COLORS.border}`,
            padding: '2rem 0',
          }}
        >
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {navItems.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  style={{
                    display: 'block',
                    padding: '1rem 1.5rem',
                    color: isActive(item.href) ? COLORS.navy : COLORS.textMain,
                    backgroundColor: isActive(item.href) ? '#E8F0F7' : 'transparent',
                    borderLeft: isActive(item.href) ? `4px solid ${COLORS.navy}` : '4px solid transparent',
                    textDecoration: 'none',
                    fontSize: '0.95rem',
                    transition: 'all 0.2s',
                  }}
                >
                  <span style={{ marginRight: '0.5rem' }}>{item.icon}</span>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Main Content */}
        <main style={{ flex: 1, padding: '2rem', overflowY: 'auto' }}>{children}</main>
      </div>

      {/* Footer */}
      <footer
        style={{
          backgroundColor: COLORS.cardBg,
          borderTop: `1px solid ${COLORS.border}`,
          padding: '1rem 2rem',
          textAlign: 'center',
          fontSize: '0.875rem',
          color: COLORS.textSecondary,
        }}
      >
        <p style={{ margin: 0 }}>
          ⚠️ AI analysis is advisory. Final decision remains with the authorized officer.
        </p>
      </footer>
    </div>
  )
}
