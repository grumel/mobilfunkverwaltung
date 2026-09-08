import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

// Feld-Diff aus dem JSON der Spalte `changes` lesbar darstellen.
function renderChanges(raw) {
  if (!raw) return null
  let changes
  try { changes = JSON.parse(raw) } catch { return null }
  const fmt = (v) => (v === null || v === '' || v === undefined ? '—' : String(v))
  return (
    <ul className="difflist">
      {Object.entries(changes).map(([field, [alt, neu]]) => (
        <li key={field}>
          <span className="difffield">{field}</span> {fmt(alt)} → <b>{fmt(neu)}</b>
        </li>
      ))}
    </ul>
  )
}

export default function Logs({ kind, user }) {
  const isAudit = kind === 'audit'
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(0)

  const load = () => {
    const fn = isAudit ? api.auditLog : api.importLog
    fn().then((d) => setRows(d.logs)).catch((e) => setError(e.message))
  }
  useEffect(load, [isAudit])

  if (isAudit && user.role !== 'admin') {
    return <div className="wrap"><span className="err">Nur für Administratoren.</span></div>
  }

  const isAdmin = user.role === 'admin'

  const undo = async (id) => {
    if (!window.confirm('Diese Änderung wirklich rückgängig machen?')) return
    setError('')
    setBusy(id)
    try {
      await api.auditUndo(id)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(0)
    }
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
                <th>Aktion</th>
                <th>Details</th>
                {isAudit && <th>Änderung</th>}
                {isAudit && isAdmin && <th className="logaction"></th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={r.reverted_at ? 'reverted' : ''}>
                  <td>{r.zeitpunkt ? fmtDate(r.zeitpunkt) : '—'}</td>
                  <td>{(isAudit ? r.username : r.quelle) || '—'}</td>
                  <td>{r.aktion || '—'}</td>
                  <td className="logdetails">{r.details || '—'}</td>
                  {isAudit && <td className="logchanges">{renderChanges(r.changes) || '—'}</td>}
                  {isAudit && isAdmin && (
                    <td className="logaction">
                      {r.reverted_at ? (
                        <span className="muted" title={`Zurückgenommen am ${r.reverted_at}`}>zurückgenommen</span>
                      ) : r.undo_op ? (
                        <button className="btn small" disabled={busy === r.id} onClick={() => undo(r.id)}>
                          {busy === r.id ? '…' : 'Rückgängig'}
                        </button>
                      ) : null}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
