export async function apiGet(path: string) {
  const res = await fetch(`/api/v1${path}`)
  if (!res.ok) throw new Error('API error')
  return res.json()
}
