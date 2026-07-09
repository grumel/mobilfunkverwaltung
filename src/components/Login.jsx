import { useState } from 'react'
import { api } from '../api'

export default function Login({ onLogin }) {
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
      onLogin(d.user)
    } catch (ex) {
      setError(ex.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-body">
      <form className="login-card" onSubmit={submit}>
        <div className="login-head"><span className="dot" /> Mobilfunkverwaltung</div>
        <p className="login-sub">Bitte anmelden</p>
        {error && <div className="flash">{error}</div>}
        <label>Benutzername
          <input value={username} onChange={(e) => setUsername(e.target.value)}
                 autoComplete="username" autoFocus required />
        </label>
        <label>Passwort
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="current-password" required />
        </label>
        <button type="submit" disabled={busy}>{busy ? 'Anmelden…' : 'Anmelden'}</button>
        <p className="hint">Gleiche Zugangsdaten wie in der Desktop-/Web-App.</p>
      </form>
    </div>
  )
}
