import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import EditModal from './EditModal.jsx'

export default function Tasks({ user, onChanged }) {
  const canWrite = user.role === 'write' || user.role === 'admin'
  const today = new Date().toISOString().slice(0, 10)

  const [show, setShow] = useState('offen')
  const [rows, setRows] = useState([])
  const [editId, setEditId] = useState(undefined)

  const load = useCallback(() => {
    api.tasks(show).then((d) => setRows(d.tasks)).catch(() => {})
  }, [show])
  useEffect(() => { load() }, [load])

  async function act(fn) {
    try { await fn(); load(); onChanged && onChanged() } catch (e) { alert(e.message) }
  }

  return (
    <div className="wrap">
      <div className="bar">
        <button className={'btn' + (show === 'offen' ? ' accent' : '')} onClick={() => setShow('offen')}>Offene</button>
        <button className={'btn' + (show === 'alle' ? ' accent' : '')} onClick={() => setShow('alle')}>Alle</button>
        <span className="count">{rows.length} Aufgaben</span>
      </div>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Prio</th><th>Name</th><th>GSM</th><th>Werk</th><th>Kommentar</th>
                  <th>Fällig</th><th>Von</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((t) => {
                const overdue = t.faellig_am && t.faellig_am < today && !t.erledigt
                const due = t.faellig_am === today && !t.erledigt
                const cls = (overdue ? 'overdue' : due ? 'duetoday' : '') + (t.erledigt ? ' done' : '')
                return (
                  <tr key={t.id} className={cls}>
                    <td>{t.prioritaet ? <span className="badge open">hoch</span> : '—'}</td>
                    <td>{t.participant_id
                      ? <a className="rowlink" onClick={() => setEditId(t.participant_id)}>{t.name || ('ID ' + t.participant_id)}</a>
                      : (t.name || '—')}</td>
                    <td>{t.gsm || '—'}</td>
                    <td>{t.plant || '—'}</td>
                    <td>{t.kommentar || '—'}</td>
                    <td>{t.faellig_am || '—'}</td>
                    <td>{t.created_by || '—'}</td>
                    <td>{t.erledigt
                      ? <span className="badge ok">erledigt</span>
                      : <span className="badge open">offen</span>}</td>
                    <td className="rowactions">
                      {canWrite && (
                        <>
                          <button className="linkbtn" onClick={() => act(() => api.taskDone(t.id))}>
                            {t.erledigt ? 'wieder öffnen' : 'erledigt'}
                          </button>
                          <button className="linkbtn danger" onClick={() => {
                            if (confirm('Aufgabe löschen?')) act(() => api.taskDelete(t.id))
                          }}>löschen</button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {editId !== undefined && (
        <EditModal id={editId} canWrite={canWrite}
                   onClose={() => setEditId(undefined)}
                   onSaved={() => { setEditId(undefined); load() }} />
      )}
    </div>
  )
}
