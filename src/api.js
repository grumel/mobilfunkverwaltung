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

// Datei-Upload (multipart) – eigener Aufruf ohne JSON-Content-Type-Header.
async function upload(url, file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(url, { method: 'POST', credentials: 'same-origin', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

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

  // Summary (Nav-Zähler + rote Markierung), Aufgaben, Statistik
  summary: () => req('/api/summary'),
  tasks: (show) => req(`/api/tasks?show=${enc(show || 'offen')}`),
  createTask: (pid, data) => req(`/api/participants/${pid}/tasks`, { method: 'POST', body: JSON.stringify(data) }),
  taskDone: (tid) => req(`/api/tasks/${tid}/done`, { method: 'POST' }),
  taskDelete: (tid) => req(`/api/tasks/${tid}`, { method: 'DELETE' }),
  stats: () => req('/api/stats'),

  // Import
  vodafonePreview: (file) => upload('/api/import/vodafone/preview', file),
  vodafoneConfirm: () => req('/api/import/vodafone/confirm', { method: 'POST' }),
  synoImport: (file) => upload('/api/import/syno', file),

  // Einstellungen
  getSettings: () => req('/api/settings'),
  saveSettings: (data) => req('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),
}
