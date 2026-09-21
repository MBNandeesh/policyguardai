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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: withAuthHeaders() })
  if (!res.ok) {
    const detail = await getErrorDetail(res)
    throw new ApiError(res.status, res.statusText, detail)
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
    const detail = await getErrorDetail(res)
    throw new ApiError(res.status, res.statusText, detail)
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
    body: formData,
  })
  if (!res.ok) {
    const detail = await getErrorDetail(res)
    throw new ApiError(res.status, res.statusText, detail)
  }
  return res.json()
}

async function getErrorDetail(res: Response): Promise<string> {
  try {
    const json = await res.json()
    return json.detail || json.message || res.statusText
  } catch {
    return res.statusText
  }
}
