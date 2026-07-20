import { useState } from 'react'
import { api } from '../api'
import { toastOk } from '../toast.jsx'

// Eigenes Passwort ändern. `forced` = Pflicht bei Erstanmeldung
// (kein Abbrechen, kein Schließen per Klick außerhalb).
export default function PasswordModal({ forced, onClose, onDone }) {
  const [cur, setCur] = useState('')
  const [pw1, setPw1] = useState('')
  const [pw2, setPw2] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function save(e) {
    e.preventDefault()
    setError('')
    if (pw1.length < 6) { setError('Neues Passwort: mindestens 6 Zeichen.'); return }
    if (pw1 !== pw2) { setError('Die neuen Passwörter stimmen nicht überein.'); return }
    setBusy(true)
    try {
      await api.changeMyPassword(cur, pw1)
      toastOk('Passwort geändert.')
      onDone && onDone()
    } catch (ex) { setError(ex.message); setBusy(false) }
  }

  return (
    <div className="overlay" onClick={forced ? undefined : onClose}>
      <form className="modal" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()} onSubmit={save}>
        <div className="modal-head">
          <h3>Passwort ändern</h3>
          {!forced && <button type="button" className="x" aria-label="Dialog schließen" onClick={onClose}>×</button>}
        </div>
        {forced && <div className="flash">Bitte vergib ein neues Passwort, bevor du fortfährst.</div>}
        {error && <div className="flash">{error}</div>}
        <label className="field"><span>Aktuelles Passwort</span>
          <input type="password" value={cur} autoFocus autoComplete="current-password"
                 onChange={(e) => setCur(e.target.value)} required />
        </label>
        <label className="field" style={{ marginTop: 10 }}><span>Neues Passwort (min. 6 Zeichen)</span>
          <input type="password" value={pw1} autoComplete="new-password"
                 onChange={(e) => setPw1(e.target.value)} required />
        </label>
        <label className="field" style={{ marginTop: 10 }}><span>Neues Passwort wiederholen</span>
          <input type="password" value={pw2} autoComplete="new-password"
                 onChange={(e) => setPw2(e.target.value)} required />
        </label>
        <div className="modal-actions">
          <button type="submit" className="btn accent" disabled={busy}>{busy ? 'Speichern…' : 'Passwort ändern'}</button>
          {!forced && <button type="button" className="btn" onClick={onClose}>Abbrechen</button>}
        </div>
      </form>
    </div>
  )
}
