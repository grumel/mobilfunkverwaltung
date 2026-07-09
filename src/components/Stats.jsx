import { useEffect, useState } from 'react'
import { api } from '../api'

const TILES = [
  ['total', 'Teilnehmer'], ['verified', 'Geprüft'], ['zur_pruefung', 'Zur Prüfung'],
  ['ohne_gsm', 'Ohne GSM'], ['mit_syno', 'Mit Syno-Gerät'], ['abgelaufen', 'Abgelaufen'],
  ['ablauf_30', 'Ablauf < 30 T'], ['ablauf_60', 'Ablauf 30–60 T'], ['ablauf_90', 'Ablauf 60–90 T'],
]

export default function Stats() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.stats().then(setS).catch((e) => setError(e.message)) }, [])

  if (error) return <div className="wrap"><span className="err">{error}</span></div>
  if (!s) return <div className="wrap"><p className="hint-dim">Lädt…</p></div>

  const maxN = Math.max(1, ...s.werke.map((w) => w.n))

  return (
    <div className="wrap">
      <div className="tiles">
        {TILES.map(([k, l]) => (
          <div key={k} className="tile">
            <div className="tval">{s.tiles[k]}</div>
            <div className="tlbl">{l}</div>
          </div>
        ))}
      </div>

      <div className="statcols">
        <div className="tablecard">
          <div className="cardhead">Teilnehmer je Werk</div>
          <div className="scroll" style={{ maxHeight: 340, padding: '8px 12px' }}>
            {s.werke.map((w) => (
              <div key={w.werk} className="barrow">
                <span className="barlbl">{w.werk}</span>
                <span className="bartrack"><span className="barfill" style={{ width: (w.n / maxN * 100) + '%' }} /></span>
                <span className="barval">{w.n}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="tablecard">
          <div className="cardhead">Ablaufende Verträge (90 Tage): {s.ablauf.length}</div>
          <div className="scroll" style={{ maxHeight: 340 }}>
            <table>
              <thead><tr><th>Vtg.-Ende</th><th>Name</th><th>Werk</th><th>GSM</th><th>Register</th></tr></thead>
              <tbody>
                {s.ablauf.map((r, i) => (
                  <tr key={i}>
                    <td>{r.vertragsende}</td><td>{r.name || '—'}</td><td>{r.plant || '—'}</td>
                    <td>{r.gsm || '—'}</td><td>{r.provider || 'Vodafone'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
