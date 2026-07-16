const ADMIN_KEY_STORAGE = 'ADMIN_API_KEY'

export function getAdminKey(): string {
  return (
    localStorage.getItem(ADMIN_KEY_STORAGE) ||
    localStorage.getItem('admin_api_key') ||
    ''
  )
}

export function setAdminKey(key: string): void {
  const trimmed = key.trim()
  localStorage.setItem(ADMIN_KEY_STORAGE, trimmed)
  localStorage.setItem('admin_api_key', trimmed)
}

export function clearAdminKey(): void {
  localStorage.removeItem(ADMIN_KEY_STORAGE)
  localStorage.removeItem('admin_api_key')
}

export function hasAdminKey(): boolean {
  return Boolean(getAdminKey())
}

export async function netlifyFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const key = getAdminKey()
  const existingHeaders = (options.headers as Record<string, string>) || {}
  return fetch(`/.netlify/functions/${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...existingHeaders,
      ...(key ? { 'x-admin-api-key': key, 'X-Admin-API-Key': key } : {}),
    },
  })
}
