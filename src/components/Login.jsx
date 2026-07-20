import { useState } from 'react'
import { api } from '../api'
import { versionLabel } from './Shell.jsx'
import '../login.css'

function SignalMark() {
  return (
    <svg className="login-logo-mark" viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 47V29" />
      <circle cx="32" cy="51" r="3" />
      <path d="M22 39a14 14 0 0 1 20 0" />
      <path d="M14 31a25 25 0 0 1 36 0" />
      <path d="M7 23a35 35 0 0 1 50 0" />
    </svg>
  )
}

export default function Login({ onLogin, version }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const d = await api.login(username, password)
      onLogin(d.user, d.force_pw_change)
    } catch (ex) {
      setError(ex.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-v2">
      <div className="login-v2-grid" aria-hidden="true" />
      <div className="login-v2-glow login-v2-glow-one" aria-hidden="true" />
      <div className="login-v2-glow login-v2-glow-two" aria-hidden="true" />

      <section className="login-v2-shell">
        <div className="login-v2-intro">
          <div className="login-v2-brand">
            <span className="login-v2-logo"><SignalMark /></span>
            <span>Mobilfunkverwaltung</span>
          </div>
          <h1>Mobilfunkdaten.<br />Klar verwaltet.</h1>
          <p>
            Verträge, Geräte und Teilnehmer in einer zentralen,
            sicheren Arbeitsoberfläche.
          </p>
          <div className="login-v2-status">
            <span className="login-v2-status-dot" />
            Interne Anwendung · Geschützter Zugriff
          </div>
        </div>

        <form className="login-v2-card" onSubmit={submit}>
          <div className="login-v2-card-head">
            <span className="login-v2-eyebrow">Willkommen zurück</span>
            <h2>Anmelden</h2>
            <p>Bitte mit Ihrem Benutzerkonto fortfahren.</p>
          </div>

          {error && <div className="login-v2-error" role="alert">{error}</div>}

          <label className="login-v2-field">
            <span>Benutzername</span>
            <div className="login-v2-input-wrap">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 21a8 8 0 0 0-16 0" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
          </label>

          <label className="login-v2-field">
            <span>Passwort</span>
            <div className="login-v2-input-wrap">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="4" y="10" width="16" height="11" rx="2" />
                <path d="M8 10V7a4 4 0 0 1 8 0v3" />
              </svg>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
          </label>

          <button className="login-v2-submit" type="submit" disabled={busy}>
            <span>{busy ? 'Anmeldung läuft …' : 'Sicher anmelden'}</span>
            {!busy && <span aria-hidden="true">→</span>}
          </button>

          <div className="login-v2-foot">
            <span>Werke Lehner GmbH &amp; Co. KG</span>
            {version && version.build && <span>{versionLabel(version)}</span>}
          </div>
        </form>
      </section>
    </main>
  )
}
