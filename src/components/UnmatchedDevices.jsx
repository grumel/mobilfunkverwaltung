import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

// Verwaiste Syno-Geräte ('Nicht zugeordnet') – Zeilen ohne passenden Teilnehmer.
export default function UnmatchedDevices({ onBack }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api.unmatchedDevices().then((d) => setRows(d.devices)).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="wrap">
      <div className="bar">
        {onBack && <button className="btn" onClick={onBack}>← Statistik</button>}
        <span className="count">{rows.length} verwaiste Geräte</span>
        {error && <span className="err">{error}</span>}
      </div>
      <p className="hint-dim" style={{ margin: '0 0 10px' }}>
        Syno-Geräte aus dem Import, die keinem Teilnehmer zugeordnet werden konnten.
        Über „Syno anreichern" lassen sich viele davon vor dem Import korrigieren.
      </p>
      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Quelle</th><th>Benutzer</th><th>GSM</th><th>Gerät</th><th>Startdatum</th><th>Importiert</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.quelle || '—'}</td>
                  <td>{r.benutzer || '—'}</td>
                  <td>{r.gsm || '—'}</td>
                  <td>{r.geraet || '—'}</td>
                  <td>{r.startdatum ? fmtDate(r.startdatum) : '—'}</td>
                  <td>{r.importdatum ? fmtDate(r.importdatum) : '—'}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan="6" className="hint-dim">Keine verwaisten Geräte.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
