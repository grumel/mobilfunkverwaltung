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

const PARTICIPANT_VIEWS = new Set([...PROVIDERS, ...DERIVED].map(([k]) => k).concat('archiv'))

function SignalMark() {
  return (
    <svg className="shell-v2-logo-mark" viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 47V29" />
      <circle cx="32" cy="51" r="3" />
      <path d="M22 39a14 14 0 0 1 20 0" />
      <path d="M14 31a25 25 0 0 1 36 0" />
      <path d="M7 23a35 35 0 0 1 50 0" />
    </svg>
  )
}

function IconButton({ title, onClick, children, className = '' }) {
  return (
    <button className={`shell-v2-icon-btn ${className}`} title={title} aria-label={title} onClick={onClick}>
      {children}
    </button>
  )
}

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
  const [resultCount, setResultCount] = useState(null)
  const isAdmin = user.role === 'admin'
  const isParticipantsView = PARTICIPANT_VIEWS.has(view)

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
      <div className="shell-v2-header">
        <div className="shell-v2-brand">
          <span className="shell-v2-logo"><SignalMark /></span>
          <span className="shell-v2-brand-copy">
            <strong>Mobilfunkverwaltung</strong>
            <small>Verträge · Geräte · Teilnehmer</small>
          </span>
        </div>

        <div className="shell-v2-header-spacer" />

        {version && version.build && (
          <span className="shell-v2-version" title={'Version ' + versionLabel(version)}>
            {versionLabel(version)}
          </span>
        )}

        <div className="shell-v2-user">
          <span className="shell-v2-avatar">{user.username.slice(0, 1).toUpperCase()}</span>
          <span className="shell-v2-user-copy">
            <strong>{user.username}</strong>
            <small>{user.role}</small>
          </span>
        </div>

        <IconButton
          title={theme === 'dark' ? 'Zu hellem Design wechseln' : 'Zu dunklem Design wechseln'}
          onClick={() => setTheme(toggleTheme())}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </IconButton>
        <button className="shell-v2-action" onClick={() => setHelpOpen(true)}>Hilfe</button>
        <button className="shell-v2-action" onClick={() => setPwOpen(true)}>Passwort</button>
        {isAdmin && (
          <>
            <button className={'shell-v2-action' + (view === 'benutzer' ? ' active' : '')} onClick={() => setView('benutzer')}>Benutzer</button>
            <button className={'shell-v2-action' + (view === 'einstellungen' ? ' active' : '')} onClick={() => setView('einstellungen')}>Einstellungen</button>
          </>
        )}
        <button className="shell-v2-logout" onClick={onLogout}>Abmelden</button>
      </div>

      {(forcePw || pwOpen) && (
        <PasswordModal forced={forcePw}
                       onClose={() => setPwOpen(false)}
                       onDone={() => { setPwOpen(false); onPwDone && onPwDone() }} />
      )}
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}

      <header className="topbar">
        <nav className="tabs" aria-label="Hauptnavigation">
          {PROVIDERS.map(([k, l]) => (
            <button key={k} className={'tab' + (view === k ? ' active' : '')}
                    aria-current={view === k ? 'page' : undefined} onClick={() => setView(k)}>{l}</button>
          ))}
          <span className="tabsep" />
          {DERIVED.map(([k, l]) => (
            <button key={k} className={'tab' + (view === k ? ' active' : '')}
                    aria-current={view === k ? 'page' : undefined} onClick={() => setView(k)}>{l}</button>
          ))}
          <span className="tabsep" />
          <button className={'tab' + (view === 'aufgaben' ? ' active' : '')} aria-current={view === 'aufgaben' ? 'page' : undefined} onClick={() => setView('aufgaben')}>
            Aufgaben{summary.open_tasks > 0 && <span className="badgecount">{summary.open_tasks}</span>}
          </button>
          <button className={'tab' + (view === 'statistik' ? ' active' : '')} aria-current={view === 'statistik' ? 'page' : undefined} onClick={() => setView('statistik')}>Statistik</button>
          <button className={'tab' + (view === 'archiv' ? ' active' : '')} aria-current={view === 'archiv' ? 'page' : undefined} onClick={() => setView('archiv')}>Archiv</button>
          <button className={'tab' + (view === 'protokoll' ? ' active' : '')} aria-current={view === 'protokoll' ? 'page' : undefined} onClick={() => setView('protokoll')}>Protokoll</button>
          <button className={'tab' + (view === 'dokumente' ? ' active' : '')} aria-current={view === 'dokumente' ? 'page' : undefined} onClick={() => setView('dokumente')}>Dokumente</button>
          {isAdmin && (
            <>
              <button className={'tab' + (view === 'audit' ? ' active' : '')} aria-current={view === 'audit' ? 'page' : undefined} onClick={() => setView('audit')}>Audit</button>
              <button className={'tab import' + (view === 'import' ? ' active' : '')} aria-current={view === 'import' ? 'page' : undefined} onClick={() => setView('import')}>Import ▾</button>
            </>
          )}
        </nav>
        <span className="spacer" />
      </header>

      {isParticipantsView && (
        <div className="globalbar searchbar">
          <label className="searchbox">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="6.5" />
              <path d="m16 16 4 4" />
            </svg>
            <span className="sr-only">Globale Suche</span>
            <input className="q" type="search" value={qInput} autoFocus
                   placeholder="Name, GSM, Werk, Konto, Tarif oder Bemerkung suchen …"
                   onChange={(e) => setQInput(e.target.value)} />
          </label>
          {resultCount != null && (
            <span className="searchcount"><b>{resultCount}</b> Treffer{q ? ' (alle Reiter)' : ''}</span>
          )}
          <span className="hint-dim">durchsucht alle Reiter, unabhängig vom aktuell gewählten</span>
        </div>
      )}
      {FILTER_LABELS[view] && (
        <div className="globalbar">
          <button className="btn" onClick={() => setView('statistik')}>← Statistik</button>
          <span className="hint-dim">Gefiltert: <b>{FILTER_LABELS[view]}</b></span>
          {resultCount != null && <span className="searchcount"><b>{resultCount}</b> Treffer</span>}
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
                            openTaskPids={summary.open_task_pids} onChanged={refreshSummary}
                            onCount={setResultCount} />}
      </main>
    </div>
  )
}
