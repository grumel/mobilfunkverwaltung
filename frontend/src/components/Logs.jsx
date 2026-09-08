import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

const fmtVal = (v) => (v === null || v === '' || v === undefined ? '—' : String(v))

// Feld-Diff aus dem JSON der Spalte `changes` als lesbare Liste.
function ChangeList({ raw }) {
  if (!raw) return null
  let changes
  try { changes = JSON.parse(raw) } catch { return null }
  const entries = Object.entries(changes)
  if (!entries.length) return null
  return (
    <ul className="difflist">
      {entries.map(([field, [alt, neu]]) => (
        <li key={field}>
          <span className="difffield">{field}</span>
          <span className="diffold">{fmtVal(alt)}</span>
          <span className="diffarrow">→</span>
          <b className="diffnew">{fmtVal(neu)}</b>
        </li>
      ))}
    </ul>
  )
}

// Kurzer Kopf je Eintrag: Aktion als farbige Marke + Betreff.
function actionLabel(aktion) {
  const map = {
    INSERT: 'Angelegt', UPDATE: 'Geändert', DELETE: 'Gelöscht',
    VERIFIED: 'Geprüft', OVERHEAD: 'Overhead', ARCHIV: 'Archiv',
    PROVIDER: 'Provider', REVERT: 'Rücknahme', MERGE: 'Zusammengeführt',
    IMPORT: 'Importiert',
  }
  return map[aktion] || aktion
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

  // Protokoll (Import-Log): schlichte Tabelle, keine Rücknahme.
  if (!isAudit) {
    return (
      <div className="wrap">
        <div className="bar">
          <span className="count">Letzte {rows.length} Protokoll-Einträge</span>
          {error && <span className="err">{error}</span>}
        </div>
        <div className="tablecard">
          <div className="scroll">
            <table>
              <thead>
                <tr><th>Zeitpunkt</th><th>Quelle</th><th>Aktion</th><th>Details</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.zeitpunkt ? fmtDate(r.zeitpunkt) : '—'}</td>
                    <td>{r.quelle || '—'}</td>
                    <td>{r.aktion || '—'}</td>
                    <td className="logdetails">{r.details || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  // Audit-Log: lesbare Karten mit gut sichtbarer Einzel-Rücknahme.
  const isAdmin = user.role === 'admin'
  return (
    <div className="wrap">
      <div className="bar">
        <span className="count">Letzte {rows.length} Änderungen</span>
        {error && <span className="err">{error}</span>}
      </div>
      <div className="auditlist">
        {rows.map((r) => (
          <div key={r.id} className={`auditcard${r.reverted_at ? ' reverted' : ''}`}>
            <div className="auditmain">
              <div className="audithead">
                <span className={`tag tag-${(r.aktion || '').toLowerCase()}`}>{actionLabel(r.aktion)}</span>
                <span className="auditwhen">{r.zeitpunkt ? fmtDate(r.zeitpunkt) : '—'}</span>
                <span className="auditwho">{r.username || '—'}</span>
              </div>
              {r.details && <div className="auditdetails">{r.details}</div>}
              <ChangeList raw={r.changes} />
            </div>
            <div className="auditside">
              {r.reverted_at ? (
                <span className="badge muted" title={`Zurückgenommen am ${r.reverted_at}`}>zurückgenommen</span>
              ) : isAdmin && r.undo_op ? (
                <button className="btn danger" disabled={busy === r.id} onClick={() => undo(r.id)}>
                  {busy === r.id ? '…' : '↶ Rückgängig'}
                </button>
              ) : null}
            </div>
          </div>
        ))}
        {!rows.length && !error && <div className="muted">Noch keine Änderungen protokolliert.</div>}
      </div>
    </div>
  )
}
