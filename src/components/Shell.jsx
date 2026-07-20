import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import Participants from './Participants.jsx'
import Tasks from './Tasks.jsx'
import Stats from './Stats.jsx'
import Import from './Import.jsx'
import Settings from './Settings.jsx'
import Logs from './Logs.jsx'
import Users from './Users.jsx'
import Documents from './Documents.jsx'
import PasswordModal from './PasswordModal.jsx'
import HelpModal from './HelpModal.jsx'
import UnmatchedDevices from './UnmatchedDevices.jsx'
import { getTheme, toggleTheme } from '../theme.js'

// Von Statistik-Kacheln aufrufbare Filter-Ansichten (Teilnehmerliste gefiltert)
const FILTER_LABELS = {
  alle: 'Alle Teilnehmer', verified: 'Geprüft', ohne_gsm: 'Ohne GSM', ohne_name: 'Ohne Name',
  ohne_werk: 'Ohne Werk', ohne_konto: 'Ohne Konto', mit_syno: 'Mit Syno-Gerät',
  abgelaufen: 'Abgelaufen', ablauf_30: 'Ablauf < 30 Tage', ablauf_60: 'Ablauf 30–60 Tage',
  ablauf_90: 'Ablauf 60–90 Tage',
}

const PROVIDERS = [
  ['vodafone', 'Vodafone'], ['telekom', 'Telekom'], ['o2', 'O2'],
  ['ohnesim', 'Ohne SIM'], ['frei', 'Frei'],
]
const DERIVED = [
  ['offen', 'Prüfungen'], ['unvollstaendig', 'Unvollständig'], ['duplikate', 'Duplikate'],
  ['overhead', 'Overhead'],
]

const PARTICIPANT_VIEWS = new Set([...PROVIDERS, ...DERIVED].map(([k]) => k))

export function versionLabel(version) {
  if (!version || !version.build) return ''
  return 'v' + version.build + (version.commit ? ' · ' + version.commit : '')
}

export default function Shell({ user, onLogout, version, forcePw, onPwDone }) {
  const [view, setView] = useState('vodafone')
  const [summary, setSummary] = useState({ open_tasks: 0, open_task_pids: [] })
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')
  const [pwOpen, setPwOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [theme, setTheme] = useState(getTheme())
  const isAdmin = user.role === 'admin'
  const isParticipantsView = PARTICIPANT_VIEWS.has(view)

  // Kachel-Klick in der Statistik: Suche zurücksetzen und Filter-Ansicht öffnen.
  function openFromStats(v) { setQInput(''); setQ(''); setView(v) }

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
      <div className="utilbar">
        <span className="dot" />
        <span className="appname">Mobilfunkverwaltung</span>
        <span className="webtag">React</span>
        <span className="spacer" />
        {version && version.build && <span className="version" title={'Version ' + versionLabel(version)}>{versionLabel(version)}</span>}
        <span className="user">{user.username} · {user.role}</span>
        <button className="themebtn" title={theme === 'dark' ? 'Zu hellem Design wechseln' : 'Zu dunklem Design wechseln'}
                onClick={() => setTheme(toggleTheme())}>{theme === 'dark' ? '☀️' : '🌙'}</button>
        <button className="utilbtn" onClick={() => setHelpOpen(true)}>Hilfe</button>
        <button className="utilbtn" onClick={() => setPwOpen(true)}>Passwort</button>
        {isAdmin && (
          <>
            <button className={'utilbtn' + (view === 'benutzer' ? ' active' : '')} onClick={() => setView('benutzer')}>Benutzer</button>
            <button className={'utilbtn' + (view === 'einstellungen' ? ' active' : '')} onClick={() => setView('einstellungen')}>⚙ Einstellungen</button>
          </>
        )}
        <button className="utilbtn logout" onClick={onLogout}>Abmelden</button>
      </div>
      {(forcePw || pwOpen) && (
        <PasswordModal forced={forcePw}
                       onClose={() => setPwOpen(false)}
                       onDone={() => { setPwOpen(false); onPwDone && onPwDone() }} />
      )}
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
      <header className="topbar">
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
          <button className={'tab' + (view === 'dokumente' ? ' active' : '')} onClick={() => setView('dokumente')}>Dokumente</button>
          {isAdmin && (
            <>
              <button className={'tab' + (view === 'audit' ? ' active' : '')} onClick={() => setView('audit')}>Audit</button>
              <button className={'tab import' + (view === 'import' ? ' active' : '')} onClick={() => setView('import')}>Import ▾</button>
            </>
          )}
        </nav>
        <span className="spacer" />
      </header>
      {isParticipantsView && (
        <div className="globalbar">
          <input className="q" type="search" value={qInput} autoFocus
                 placeholder="Globale Suche: Name, GSM, Werk, Konto, Tarif, Bemerkung …"
                 onChange={(e) => setQInput(e.target.value)} />
          <span className="hint-dim">durchsucht alle Reiter, unabhängig vom aktuell gewählten</span>
        </div>
      )}
      {FILTER_LABELS[view] && (
        <div className="globalbar">
          <button className="btn" onClick={() => setView('statistik')}>← Statistik</button>
          <span className="hint-dim">Gefiltert: <b>{FILTER_LABELS[view]}</b></span>
        </div>
      )}
      <main>
        {view === 'aufgaben'
          ? <Tasks user={user} onChanged={refreshSummary} />
          : view === 'statistik'
            ? <Stats onOpen={openFromStats} />
            : view === 'dokumente'
              ? <Documents />
            : view === 'unmatched'
              ? <UnmatchedDevices user={user} onBack={() => setView('statistik')} />
            : view === 'protokoll'
              ? <Logs kind="import" user={user} />
              : view === 'audit'
                ? <Logs kind="audit" user={user} />
                : view === 'import'
                  ? <Import />
                  : view === 'benutzer'
                    ? <Users user={user} />
                    : view === 'einstellungen'
                      ? <Settings />
                      : <Participants view={view} q={q} user={user}
                                      openTaskPids={summary.open_task_pids} onChanged={refreshSummary} />}
      </main>
    </div>
  )
}
