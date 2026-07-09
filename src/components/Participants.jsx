import { useEffect, useState } from 'react'
import { api } from '../api'

const PROVIDERS = [
  ['vodafone', 'Vodafone'], ['telekom', 'Telekom'], ['o2', 'O2'],
  ['ohnesim', 'Ohne SIM'], ['frei', 'Frei'],
]
const COLS = [
  ['master_id', 'Nr.'], ['gsm', 'GSM'], ['name', 'Name'], ['plant', 'Werk'],
  ['konto', 'Konto'], ['tarif', 'Tarif'], ['vertragsende', 'Vtg.-Ende'], ['bemerkung', 'Bemerkung'],
]
const NUMERIC = new Set(['master_id', 'konto'])

export default function Participants() {
  const [provider, setProvider] = useState('vodafone')
  const [q, setQ] = useState('')
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      api.participants(provider, q)
        .then((d) => { setRows(d.participants); setTotal(d.total); setError('') })
        .catch((ex) => setError(ex.message))
    }, 150)
    return () => clearTimeout(t)
  }, [provider, q])

  return (
    <div className="wrap">
      <nav className="tabs">
        {PROVIDERS.map(([slug, label]) => (
          <button key={slug}
                  className={'tab' + (provider === slug ? ' active' : '')}
                  onClick={() => setProvider(slug)}>{label}</button>
        ))}
      </nav>

      <div className="bar">
        <input className="q" type="search" value={q} autoFocus
               placeholder="Suche: Name, GSM, Werk, Konto, Tarif …"
               onChange={(e) => setQ(e.target.value)} />
        <span className="count">{total} Treffer</span>
        {error && <span className="err">{error}</span>}
      </div>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Status</th>{COLS.map(([k, l]) => <th key={k}>{l}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.verified === 1
                    ? <span className="badge ok">geprüft</span>
                    : <span className="badge open">offen</span>}</td>
                  {COLS.map(([k]) => (
                    <td key={k} className={NUMERIC.has(k) ? 'num' : ''}>
                      {r[k] === null || r[k] === '' || r[k] === undefined ? '—' : r[k]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
