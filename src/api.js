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
const enc = encodeURIComponent

export const api = {
  // Auth
  me: () => req('/api/me'),
  login: (username, password) =>
    req('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => req('/api/logout', { method: 'POST' }),

  // Teilnehmer
  participants: (view, q) => req(`/api/participants?view=${enc(view)}&q=${enc(q || '')}`),
  participant: (id) => req(`/api/participants/${id}`),
  create: (data) => req('/api/participants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => req(`/api/participants/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  verify: (id) => req(`/api/participants/${id}/verify`, { method: 'POST' }),
  move: (id, provider) => req(`/api/participants/${id}/move`, { method: 'POST', body: JSON.stringify({ provider }) }),
  remove: (id) => req(`/api/participants/${id}`, { method: 'DELETE' }),
}
