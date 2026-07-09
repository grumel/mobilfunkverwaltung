import { useEffect, useState } from 'react'
import { api } from './api'
import Login from './components/Login.jsx'
import Shell from './components/Shell.jsx'

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
  return <Shell user={user} onLogout={logout} />
}
