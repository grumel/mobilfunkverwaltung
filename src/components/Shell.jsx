import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import Participants from './Participants.jsx'
import Tasks from './Tasks.jsx'
import Stats from './Stats.jsx'
import Import from './Import.jsx'
import Settings from './Settings.jsx'
import Logs from './Logs.jsx'

const PROVIDERS = [
  ['vodafone', 'Vodafone'], ['telekom', 'Telekom'], ['o2', 'O2'],
  ['ohnesim', 'Ohne SIM'], ['frei', 'Frei'],
]
const DERIVED = [
  ['offen', 'Prüfungen'], ['unvollstaendig', 'Unvollständig'], ['duplikate', 'Duplikate'],
]

const PARTICIPANT_VIEWS = new Set([...PROVIDERS, ...DERIVED].map(([k]) => k))

export default function Shell({ user, onLogout }) {
  const [view, setView] = useState('vodafone')
  const [summary, setSummary] = useState({ open_tasks: 0, open_task_pids: [] })
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')
  const isAdmin = user.role === 'admin'
  const isParticipantsView = PARTICIPANT_VIEWS.has(view)

  const refreshSummary = useCallback(() => {
    api.summary().then(setSummary).catch(() => {})
  }, [])
  useEffect(() => { refreshSummary() }, [view, refreshSummary])
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 150)
    return () => clearTimeout(t)
  }, [qInput])

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
          <button className={'tab' + (view === 'protokoll' ? ' active' : '')} onClick={() => setView('protokoll')}>Protokoll</button>
          {isAdmin && (
            <>
              <button className={'tab' + (view === 'audit' ? ' active' : '')} onClick={() => setView('audit')}>Audit</button>
              <button className={'tab import' + (view === 'import' ? ' active' : '')} onClick={() => setView('import')}>Import ▾</button>
              <button className={'tab' + (view === 'einstellungen' ? ' active' : '')} onClick={() => setView('einstellungen')}>⚙ Einstellungen</button>
            </>
          )}
        </nav>
        <span className="spacer" />
        <span className="user">{user.username} · {user.role}</span>
        <button className="logout" onClick={onLogout}>Abmelden</button>
      </header>
      {isParticipantsView && (
        <div className="globalbar">
          <input className="q" type="search" value={qInput} autoFocus
                 placeholder="Globale Suche: Name, GSM, Werk, Konto, Tarif, Bemerkung …"
                 onChange={(e) => setQInput(e.target.value)} />
          <span className="hint-dim">durchsucht alle Reiter, unabhängig vom aktuell gewählten</span>
        </div>
      )}
      <main>
        {view === 'aufgaben'
          ? <Tasks user={user} onChanged={refreshSummary} />
          : view === 'statistik'
            ? <Stats />
            : view === 'protokoll'
              ? <Logs kind="import" user={user} />
              : view === 'audit'
                ? <Logs kind="audit" user={user} />
                : view === 'import'
                  ? <Import />
                  : view === 'einstellungen'
                    ? <Settings />
                    : <Participants view={view} q={q} user={user}
                                    openTaskPids={summary.open_task_pids} onChanged={refreshSummary} />}
      </main>
    </div>
  )
}
