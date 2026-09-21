import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { COLORS } from '../lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/', icon: 'M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10' },
  { label: 'Documents', href: '/documents', icon: 'M9 12h6m-6 4h6M7 3h7l5 5v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z' },
  { label: 'Compliance Review', href: '/compliance', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Reports', href: '/reports', icon: 'M9 17v-6h6M8 3h8l4 4v14a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z' },
]

function NavIcon({ path, active }: { path: string; active: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2.2 : 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  )
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = useState(false)

  const isActive = (href: string) =>
    href === '/' ? router.pathname === '/' : router.pathname.startsWith(href)

  return (
    <>
      <style jsx global>{`
        .nav-desktop {
          display: none;
        }
        .nav-mobile-btn {
          display: flex;
        }
        @media (min-width: 768px) {
          .nav-desktop {
            display: flex;
          }
          .nav-mobile-btn {
            display: none;
          }
        }
      `}</style>
      {/* Top navbar */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 1000,
          background: `linear-gradient(90deg, ${COLORS.navy} 0%, ${COLORS.blue} 100%)`,
          color: 'white',
          boxShadow: '0 2px 12px rgba(22, 58, 95, 0.25)',
        }}
      >
        <div
          style={{
            maxWidth: '1280px',
            width: '100%',
            margin: '0 auto',
            padding: '0 1.5rem',
            height: '64px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          {/* Brand */}
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexShrink: 0 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '9px',
                background: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.25)',
                fontSize: '1.1rem',
              }}
            >
              🛡️
            </span>
            <span>
              <span style={{ display: 'block', fontSize: '1.05rem', fontWeight: 700, letterSpacing: '0.2px', lineHeight: 1.2 }}>
                PolicyGuard AI
              </span>
              <span style={{ display: 'block', fontSize: '0.7rem', opacity: 0.85, lineHeight: 1.2 }}>
                Procurement Compliance Verification
              </span>
            </span>
          </Link>

          {/* Desktop nav */}
          <nav
            className="nav-desktop"
            style={{
              alignItems: 'center',
              gap: '0.25rem',
            }}
          >
            {NAV_ITEMS.map((item) => {
              const active = isActive(item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    padding: '0.5rem 0.9rem',
                    borderRadius: '8px',
                    fontSize: '0.875rem',
                    fontWeight: active ? 600 : 500,
                    color: 'white',
                    backgroundColor: active ? 'rgba(255,255,255,0.18)' : 'transparent',
                    border: active ? '1px solid rgba(255,255,255,0.3)' : '1px solid transparent',
                    textDecoration: 'none',
                    transition: 'background 0.2s',
                  }}
                >
                  <NavIcon path={item.icon} active={active} />
                  {item.label}
                </Link>
              )
            })}
          </nav>

          {/* Mobile hamburger */}
          <button
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
            className="nav-mobile-btn"
            style={{
              background: 'rgba(255,255,255,0.12)',
              border: '1px solid rgba(255,255,255,0.25)',
              borderRadius: '8px',
              color: 'white',
              width: '40px',
              height: '40px',
              cursor: 'pointer',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {mobileOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <nav
            className="nav-mobile-menu"
            style={{
              borderTop: '1px solid rgba(255,255,255,0.15)',
              background: COLORS.navy,
              padding: '0.5rem 1rem 0.75rem',
            }}
          >
            {NAV_ITEMS.map((item) => {
              const active = isActive(item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.6rem',
                    padding: '0.75rem 0.9rem',
                    borderRadius: '8px',
                    fontSize: '0.95rem',
                    fontWeight: active ? 600 : 400,
                    color: 'white',
                    backgroundColor: active ? 'rgba(255,255,255,0.15)' : 'transparent',
                    textDecoration: 'none',
                    marginBottom: '0.25rem',
                  }}
                >
                  <NavIcon path={item.icon} active={active} />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        )}
      </header>

      {/* Main content */}
      <main style={{ flex: 1, width: '100%', maxWidth: '1280px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        {children}
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: `1px solid ${COLORS.border}`,
          backgroundColor: COLORS.cardBg,
          padding: '1rem 1.5rem',
          textAlign: 'center',
          fontSize: '0.8rem',
          color: COLORS.textSecondary,
        }}
      >
        <p style={{ margin: 0 }}>
          ⚠️ AI analysis is advisory only. The final decision remains with the authorized officer.
        </p>
      </footer>
    </>
  )
}
