// Kleiner API-Client. Alle Requests same-origin (Dev: Vite-Proxy -> Flask).
async function req(url, opts = {}) {
  const res = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const err = new Error(data.error || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  me: () => req('/api/me'),
  login: (username, password) =>
    req('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => req('/api/logout', { method: 'POST' }),
  participants: (provider, q) =>
    req(`/api/participants?provider=${encodeURIComponent(provider)}&q=${encodeURIComponent(q || '')}`),
}
