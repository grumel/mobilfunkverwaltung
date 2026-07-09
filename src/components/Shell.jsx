import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import Participants from './Participants.jsx'
import Tasks from './Tasks.jsx'
import Stats from './Stats.jsx'
import Import from './Import.jsx'
import Settings from './Settings.jsx'

const PROVIDERS = [
  ['vodafone', 'Vodafone'], ['telekom', 'Telekom'], ['o2', 'O2'],
  ['ohnesim', 'Ohne SIM'], ['frei', 'Frei'],
]
const DERIVED = [
  ['offen', 'Prüfungen'], ['unvollstaendig', 'Unvollständig'], ['duplikate', 'Duplikate'],
]

export default function Shell({ user, onLogout }) {
  const [view, setView] = useState('vodafone')
  const [summary, setSummary] = useState({ open_tasks: 0, open_task_pids: [] })
  const isAdmin = user.role === 'admin'

  const refreshSummary = useCallback(() => {
    api.summary().then(setSummary).catch(() => {})
  }, [])
  useEffect(() => { refreshSummary() }, [view, refreshSummary])

  return (
    <div>
      <header className="topbar">
        <span className="dot" />
        <span className="appname">Mobilfunkverwaltung</span>
        <span className="webtag">React</span>
        <nav className="tabs">
          {PROVIDERS.map(([k, l]) => (
            <button key={k} className={'tab' + (view === k ? ' active' : '')} onClick={() => setView(k)}>{l}</button>
          ))}
          <span className="tabsep" />
          {DERIVED.map(([k, l]) => (
            <button key={k} className={'tab' + (view === k ? ' active' : '')} onClick={() => setView(k)}>{l}</button>
          ))}
          <span className="tabsep" />
          <button className={'tab' + (view === 'aufgaben' ? ' active' : '')} onClick={() => setView('aufgaben')}>
            Aufgaben{summary.open_tasks > 0 && <span className="badgecount">{summary.open_tasks}</span>}
          </button>
          <button className={'tab' + (view === 'statistik' ? ' active' : '')} onClick={() => setView('statistik')}>Statistik</button>
          {isAdmin && (
            <>
              <button className={'tab import' + (view === 'import' ? ' active' : '')} onClick={() => setView('import')}>Import ▾</button>
              <button className={'tab' + (view === 'einstellungen' ? ' active' : '')} onClick={() => setView('einstellungen')}>⚙ Einstellungen</button>
            </>
          )}
        </nav>
        <span className="spacer" />
        <span className="user">{user.username} · {user.role}</span>
        <button className="logout" onClick={onLogout}>Abmelden</button>
      </header>
      <main>
        {view === 'aufgaben'
          ? <Tasks user={user} onChanged={refreshSummary} />
          : view === 'statistik'
            ? <Stats />
            : view === 'import'
              ? <Import />
              : view === 'einstellungen'
                ? <Settings />
                : <Participants view={view} user={user}
                                openTaskPids={summary.open_task_pids} onChanged={refreshSummary} />}
      </main>
    </div>
  )
}
