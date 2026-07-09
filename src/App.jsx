import { useEffect, useState } from 'react'
import { api } from './api'
import Login from './components/Login.jsx'
import Participants from './components/Participants.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.me()
      .then((d) => setUser(d.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  async function logout() {
    try { await api.logout() } catch { /* egal */ }
    setUser(null)
  }

  if (loading) return <div className="center">Lädt…</div>
  if (!user) return <Login onLogin={setUser} />

  return (
    <div>
      <header className="topbar">
        <span className="dot" />
        <span className="appname">Mobilfunkverwaltung</span>
        <span className="webtag">React</span>
        <span className="spacer" />
        <span className="user">{user.username} · {user.role}</span>
        <button className="logout" onClick={logout}>Abmelden</button>
      </header>
      <main>
        <Participants />
      </main>
    </div>
  )
}
