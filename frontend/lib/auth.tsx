'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { apiGet, apiPost } from './api'

export interface OfficerSession {
  token: string
  officer_id: string
  name: string
  role: string
  expires_at: string
}

interface AuthContextValue {
  session: OfficerSession | null
  loading: boolean
  login: (officerId: string, password: string) => Promise<void>
  logout: () => void
}

const STORAGE_KEY = 'policyguard.officer.session'

const AuthContext = createContext<AuthContextValue>({
  session: null,
  loading: true,
  login: async () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<OfficerSession | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const stored = JSON.parse(raw) as OfficerSession
        // Drop expired sessions immediately.
        if (stored.expires_at && new Date(stored.expires_at) > new Date()) {
          setSession(stored)
        } else {
          window.localStorage.removeItem(STORAGE_KEY)
        }
      }
    } catch {
      /* ignore malformed stored state */
    }
    setLoading(false)
  }, [])

  async function login(officerId: string, password: string) {
    const res = await apiPost<OfficerSession, { officer_id: string; password: string }>(
      '/auth/login',
      { officer_id: officerId, password },
    )
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(res))
    setSession(res)
  }

  function logout() {
    if (session) {
      apiPost('/auth/logout', {}).catch(() => {})
    }
    window.localStorage.removeItem(STORAGE_KEY)
    setSession(null)
  }

  return (
    <AuthContext.Provider value={{ session, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

/** Attach the officer's bearer token to an API call, if logged in. */
export function authHeaders(): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const stored = JSON.parse(raw) as OfficerSession
    return stored.token ? { Authorization: `Bearer ${stored.token}` } : {}
  } catch {
    return {}
  }
}
