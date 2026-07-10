import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

export default function Logs({ kind, user }) {
  const isAudit = kind === 'audit'
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    const fn = isAudit ? api.auditLog : api.importLog
    fn().then((d) => setRows(d.logs)).catch((e) => setError(e.message))
  }, [isAudit])

  if (isAudit && user.role !== 'admin') {
    return <div className="wrap"><span className="err">Nur für Administratoren.</span></div>
  }

  return (
    <div className="wrap">
      <div className="bar">
        <span className="count">Letzte {rows.length} {isAudit ? 'Audit-' : 'Protokoll-'}Einträge</span>
        {error && <span className="err">{error}</span>}
      </div>
      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Zeitpunkt</th>
                {isAudit ? <th>Benutzer</th> : <th>Quelle</th>}
                <th>Aktion</th><th>Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.zeitpunkt ? fmtDate(r.zeitpunkt) : '—'}</td>
                  <td>{(isAudit ? r.username : r.quelle) || '—'}</td>
                  <td>{r.aktion || '—'}</td>
                  <td>{r.details || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
