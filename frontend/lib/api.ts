// Default to the Next.js proxy so browser requests do not require CORS access
// to the FastAPI service. A deployed public API may override this value.
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '/api/v1').replace(/\/$/, '')

/** Read the officer bearer token from localStorage (set by lib/auth.tsx). */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem('policyguard.officer.session')
    if (!raw) return null
    const stored = JSON.parse(raw)
    return stored?.token || null
  } catch {
    return null
  }
}

function withAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail: string,
  ) {
    super(`API Error ${status}: ${detail}`)
  }
}

/**
 * Centralized 401 handling: an expired/invalid officer session clears the
 * stored session and returns the user to the login screen instead of showing
 * a confusing per-page error. demo-day safe: no stale-token failures.
 */
function handleUnauthorized(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem('policyguard.officer.session')
  } catch {
    /* ignore */
  }
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login?expired=1'
  }
}

/** Turn a failed Response into an ApiError, handling 401 centrally. */
async function throwApiError(res: Response): Promise<never> {
  if (res.status === 401) handleUnauthorized()
  const detail = await getErrorDetail(res)
  throw new ApiError(res.status, res.statusText, detail)
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: withAuthHeaders() })
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

export async function apiPost<T, TBody = unknown>(path: string, body: TBody): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

export async function uploadFile<T>(
  path: string,
  file: File,
  fields: Record<string, string> = {},
): Promise<T> {
  const formData = new FormData()
  formData.append('file', file)
  for (const [key, value] of Object.entries(fields)) {
    formData.append(key, value)
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    // NOTE: Authorization header is attached; the browser sets the multipart
    // Content-Type boundary automatically - do not override it manually.
    headers: withAuthHeaders(),
    body: formData,
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

/**
 * Download a binary file (e.g. the compliance report PDF) with the officer
 * bearer token attached, and trigger a browser download. Never navigates to
 * a blank page: the blob is fetched, then saved via a temporary object URL.
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: withAuthHeaders(),
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    window.URL.revokeObjectURL(url)
  }
}

async function getErrorDetail(res: Response): Promise<string> {
  try {
    const json = await res.json()
    return json.detail || json.message || res.statusText
  } catch {
    return res.statusText
  }
}
