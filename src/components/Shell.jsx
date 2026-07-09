import { useState } from 'react'
import Participants from './Participants.jsx'

const PROVIDERS = [
  ['vodafone', 'Vodafone'], ['telekom', 'Telekom'], ['o2', 'O2'],
  ['ohnesim', 'Ohne SIM'], ['frei', 'Frei'],
]
const DERIVED = [
  ['offen', 'Prüfungen'], ['unvollstaendig', 'Unvollständig'], ['duplikate', 'Duplikate'],
]

export default function Shell({ user, onLogout }) {
  const [view, setView] = useState('vodafone')
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
        </nav>
        <span className="spacer" />
        <span className="user">{user.username} · {user.role}</span>
        <button className="logout" onClick={onLogout}>Abmelden</button>
      </header>
      <main>
        <Participants view={view} user={user} />
      </main>
    </div>
  )
}
