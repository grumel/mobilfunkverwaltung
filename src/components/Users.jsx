import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

const ROLE_LABELS = {
  admin: 'Admin (alles)', write: 'Schreiben (bearbeiten/importieren)', read: 'Lesen (nur ansehen)',
}
const ROLES = ['read', 'write', 'admin']

export default function Users({ user }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [edit, setEdit] = useState(undefined)   // undefined = zu, null = neu, Objekt = bearbeiten

  function load() {
    api.users().then((d) => { setRows(d.users); setError('') }).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  if (user.role !== 'admin') {
    return <div className="wrap"><span className="err">Nur für Administratoren.</span></div>
  }

  async function resetPw(u) {
    const pw = prompt(`Neues Passwort für „${u.username}" (min. 6 Zeichen):`, '')
    if (pw === null) return
    try { await api.userSetPassword(u.id, pw); alert('Passwort gesetzt.') }
    catch (e) { alert(e.message) }
  }

  async function remove(u) {
    if (!confirm(`Benutzer „${u.username}" wirklich löschen?`)) return
    try { await api.userDelete(u.id); load() } catch (e) { alert(e.message) }
  }

  return (
    <div className="wrap">
      <div className="bar">
        <button className="btn accent" onClick={() => setEdit(null)}>+ Neuer Benutzer</button>
        <span className="count">{rows.length} Benutzer</span>
        {error && <span className="err">{error}</span>}
      </div>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Benutzername</th><th>Rolle</th><th>Status</th><th>Windows-Login</th>
                <th>Letzter Login</th><th>Angelegt</th><th>Aktionen</th></tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}{u.id === user.id && <span className="hint-dim"> (ich)</span>}</td>
                  <td>{ROLE_LABELS[u.role] || u.role}</td>
                  <td>{u.active
                    ? <span className="badge ok">aktiv</span>
                    : <span className="badge open">gesperrt</span>}</td>
                  <td>{u.windows_login || '—'}</td>
                  <td>{u.last_login ? fmtDate(u.last_login) : '—'}</td>
                  <td>{u.created_at ? fmtDate(u.created_at) : '—'}</td>
                  <td className="rowactions">
                    <button className="linkbtn" onClick={() => setEdit(u)}>Bearbeiten</button>
                    <button className="linkbtn" onClick={() => resetPw(u)}>Passwort</button>
                    {u.id !== user.id &&
                      <button className="linkbtn danger" onClick={() => remove(u)}>Löschen</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {edit !== undefined && (
        <UserModal u={edit} onClose={() => setEdit(undefined)}
                   onSaved={() => { setEdit(undefined); load() }} />
      )}
    </div>
  )
}

function UserModal({ u, onClose, onSaved }) {
  const isNew = u === null
  const [form, setForm] = useState(isNew
    ? { username: '', role: 'read', active: true, windows_login: '', password: '' }
    : { username: u.username, role: u.role, active: !!u.active, windows_login: u.windows_login || '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0 })

  function set(k, v) { setForm((p) => ({ ...p, [k]: v })) }

  function startDrag(e) {
    if (e.target.closest('.x')) return
    const sx = e.clientX, sy = e.clientY, start = pos
    function move(ev) { setPos({ x: start.x + (ev.clientX - sx), y: start.y + (ev.clientY - sy) }) }
    function up() { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (isNew) {
        await api.userCreate({
          username: form.username, role: form.role, active: form.active,
          windows_login: form.windows_login, password: form.password,
        })
      } else {
        await api.userUpdate(u.id, {
          username: form.username, role: form.role, active: form.active,
          windows_login: form.windows_login,
        })
      }
      onSaved()
    } catch (ex) { setError(ex.message); setBusy(false) }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" style={{ maxWidth: 480, transform: `translate(${pos.x}px, ${pos.y}px)` }}
            onClick={(e) => e.stopPropagation()} onSubmit={save}>
        <div className="modal-head" onMouseDown={startDrag}>
          <h3>{isNew ? 'Neuer Benutzer' : `Bearbeiten: ${u.username}`}</h3>
          <button type="button" className="x" onClick={onClose}>×</button>
        </div>
        {error && <div className="flash">{error}</div>}
        <div className="grid">
          <label className="field"><span>Benutzername</span>
            <input value={form.username} onChange={(e) => set('username', e.target.value)} autoFocus required />
          </label>
          <label className="field"><span>Rolle</span>
            <select value={form.role} onChange={(e) => set('role', e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </label>
          {isNew && (
            <label className="field"><span>Passwort (min. 6, oder Windows-Login)</span>
              <input type="password" value={form.password} onChange={(e) => set('password', e.target.value)}
                     autoComplete="new-password" />
            </label>
          )}
          <label className="field"><span>Windows-Login (optional, SSO)</span>
            <input value={form.windows_login} onChange={(e) => set('windows_login', e.target.value)} />
          </label>
        </div>
        <label className="check">
          <input type="checkbox" checked={form.active} onChange={(e) => set('active', e.target.checked)} /> Konto aktiv
        </label>
        <div className="modal-actions">
          <button type="submit" className="btn accent" disabled={busy}>{busy ? 'Speichern…' : 'Speichern'}</button>
          <button type="button" className="btn" onClick={onClose}>Abbrechen</button>
        </div>
      </form>
    </div>
  )
}
