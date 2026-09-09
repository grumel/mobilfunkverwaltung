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
// `fields` = optionale zusätzliche Formularfelder (z. B. gsm, name).
async function upload(url, file, fields = {}) {
  const fd = new FormData()
  fd.append('file', file)
  for (const [k, v] of Object.entries(fields)) fd.append(k, v ?? '')
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
  // Auth / Meta
  me: () => req('/api/me'),
  version: () => req('/api/version'),
  changeMyPassword: (current_password, new_password) =>
    req('/api/me/password', { method: 'POST', body: JSON.stringify({ current_password, new_password }) }),
  getMyNotes: () => req('/api/me/notes'),
  saveMyNotes: (notes) => req('/api/me/notes', { method: 'PUT', body: JSON.stringify({ notes }) }),
  login: (username, password) =>
    req('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => req('/api/logout', { method: 'POST' }),

  // Teilnehmer
  participants: (view, q) => req(`/api/participants?view=${enc(view)}&q=${enc(q || '')}`),
  participant: (id) => req(`/api/participants/${id}`),
  create: (data) => req('/api/participants', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => req(`/api/participants/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  verify: (id) => req(`/api/participants/${id}/verify`, { method: 'POST' }),
  overhead: (id) => req(`/api/participants/${id}/overhead`, { method: 'POST' }),
  archive: (id) => req(`/api/participants/${id}/archive`, { method: 'POST' }),
  move: (id, provider) => req(`/api/participants/${id}/move`, { method: 'POST', body: JSON.stringify({ provider }) }),
  remove: (id) => req(`/api/participants/${id}`, { method: 'DELETE' }),
  merge: (ids) => req('/api/participants/merge', { method: 'POST', body: JSON.stringify({ ids }) }),
  werkKonto: () => req('/api/werk-konto'),
  neuvertrag: (data) => req('/api/neuvertrag', { method: 'POST', body: JSON.stringify(data) }),
  kuendigung: (pid, kind) =>
    req(`/api/participants/${pid}/kuendigung`, { method: 'POST', body: JSON.stringify({ kind }) }),
  kuendigungUrl: (file) => `/api/kuendigung/${encodeURIComponent(file)}`,

  // Summary (Nav-Zähler + rote Markierung), Aufgaben, Statistik
  summary: () => req('/api/summary'),
  tasks: (show) => req(`/api/tasks?show=${enc(show || 'offen')}`),
  createTask: (pid, data) => req(`/api/participants/${pid}/tasks`, { method: 'POST', body: JSON.stringify(data) }),
  taskDone: (tid) => req(`/api/tasks/${tid}/done`, { method: 'POST' }),
  taskDelete: (tid) => req(`/api/tasks/${tid}`, { method: 'DELETE' }),
  stats: () => req('/api/stats'),
  dataQuality: () => req('/api/dataquality'),
  unmatchedDevices: () => req('/api/unmatched-devices'),
  unmatchedUpdate: (id, data) => req(`/api/unmatched-devices/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  unmatchedDelete: (id) => req(`/api/unmatched-devices/${id}`, { method: 'DELETE' }),
  unmatchedAssign: (id, participant_id, slot = 'auto') =>
    req(`/api/unmatched-devices/${id}/assign`, { method: 'POST', body: JSON.stringify({ participant_id, slot }) }),
  unmatchedCreateParticipant: (id, data) =>
    req(`/api/unmatched-devices/${id}/create-participant`, { method: 'POST', body: JSON.stringify(data) }),

  // Import
  vodafonePreview: (file) => upload('/api/import/vodafone/preview', file),
  vodafoneConfirm: () => req('/api/import/vodafone/confirm', { method: 'POST' }),
  synoImport: (file, createMissing) => upload('/api/import/syno', file, { create_missing: createMissing ? '1' : '0' }),
  synoEnrich: (file) => upload('/api/syno/enrich', file),
  synoFileUrl: (name) => `/api/syno/file/${encodeURIComponent(name)}`,

  // Einzel-Abgleich im Bearbeiten-Dialog (füllt Felder, speichert nicht)
  matchVodafone: (file, gsm) => upload('/api/match/vodafone', file, { gsm }),
  matchSyno: (file, gsm, name) => upload('/api/match/syno', file, { gsm, name }),

  // Einstellungen
  getSettings: () => req('/api/settings'),
  saveSettings: (data) => req('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),
  backupUrl: () => '/api/backup',

  // Dokumente (Kündigung/Rücknahme/Neuvertrag – lokal gespeichert)
  documents: () => req('/api/documents'),
  documentUrl: (name) => `/api/documents/${enc(name)}`,

  // Protokoll / Audit
  importLog: () => req('/api/logs/import'),
  auditLog: () => req('/api/logs/audit'),
  auditUndo: (id) => req(`/api/audit/${id}/undo`, { method: 'POST' }),

  // Benutzerverwaltung (nur Admin)
  users: () => req('/api/users'),
  userCreate: (data) => req('/api/users', { method: 'POST', body: JSON.stringify(data) }),
  userUpdate: (uid, data) => req(`/api/users/${uid}`, { method: 'PUT', body: JSON.stringify(data) }),
  userSetPassword: (uid, password) =>
    req(`/api/users/${uid}/password`, { method: 'POST', body: JSON.stringify({ password }) }),
  userDelete: (uid) => req(`/api/users/${uid}`, { method: 'DELETE' }),
}
