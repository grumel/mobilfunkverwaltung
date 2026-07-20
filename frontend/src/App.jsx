import { useEffect, useState } from 'react'
import { api } from './api'
import Login from './components/Login.jsx'
import Shell from './components/Shell.jsx'
import { ToastHost } from './toast.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(null)
  const [forcePw, setForcePw] = useState(false)

  useEffect(() => {
    api.me()
      .then((d) => { setUser(d.user); setForcePw(!!d.force_pw_change) })
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
    api.version().then(setVersion).catch(() => {})
  }, [])

  function handleLogin(u, force) { setUser(u); setForcePw(!!force) }

  async function logout() {
    try { await api.logout() } catch { /* egal */ }
    setUser(null); setForcePw(false)
  }

  if (loading) return <div className="center">Lädt…</div>
  return (
    <>
      {!user
        ? <Login onLogin={handleLogin} version={version} />
        : <Shell user={user} onLogout={logout} version={version}
                 forcePw={forcePw} onPwDone={() => setForcePw(false)} />}
      <ToastHost />
    </>
  )
}
