import { useEffect, useState } from 'react'
import { api } from '../api'

const TILES = [
  ['total', 'Teilnehmer'], ['verified', 'Geprüft'], ['zur_pruefung', 'Zur Prüfung'],
  ['ohne_gsm', 'Ohne GSM'], ['mit_syno', 'Mit Syno-Gerät'], ['abgelaufen', 'Abgelaufen'],
  ['ablauf_30', 'Ablauf < 30 T'], ['ablauf_60', 'Ablauf 30–60 T'], ['ablauf_90', 'Ablauf 60–90 T'],
]

const DQ_TILES = [
  ['ohne_gsm', 'Ohne GSM', 'orange'], ['ohne_name', 'Ohne Name', 'orange'],
  ['ohne_werk', 'Ohne Werk', 'orange'], ['ohne_konto', 'Ohne Konto', 'orange'],
  ['ungeprueft', 'Ungeprüft', 'blue'], ['duplikate', 'Duplikate', 'red'],
  ['verwaiste_geraete', 'Verwaiste Geräte', 'grey'],
]

export default function Stats() {
  const [s, setS] = useState(null)
  const [dq, setDq] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.stats().then(setS).catch((e) => setError(e.message))
    api.dataQuality().then((d) => setDq(d.metrics)).catch(() => {})
  }, [])

  if (error) return <div className="wrap"><span className="err">{error}</span></div>
  if (!s) return <div className="wrap"><p className="hint-dim">Lädt…</p></div>

  const maxN = Math.max(1, ...s.werke.map((w) => w.n))
  const sauber = dq ? dq.sauberkeit : null
  const sauberCls = sauber == null ? '' : sauber >= 90 ? 'green' : sauber >= 70 ? 'orange' : 'red'

  return (
    <div className="wrap">
      {dq && (
        <div className="tablecard" style={{ marginBottom: 14, padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div className={'tile ' + sauberCls} style={{ minWidth: 130 }}>
              <div className="tval">{sauber}%</div>
              <div className="tlbl">Sauberkeit (vollständig)</div>
            </div>
            <div className="tiles" style={{ margin: 0 }}>
              {DQ_TILES.map(([k, l, cls]) => (
                <div key={k} className={'tile ' + cls}>
                  <div className="tval">{dq[k]}</div>
                  <div className="tlbl">{l}</div>
                </div>
              ))}
            </div>
          </div>
          <p className="hint-dim" style={{ margin: '8px 0 0' }}>
            „Sauberkeit" = Anteil vollständiger Einträge (GSM, Name, Werk und Konto vorhanden)
            von {dq.total}. Details siehe Reiter „Unvollständig", „Duplikate" und „Prüfungen".
          </p>
        </div>
      )}

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
