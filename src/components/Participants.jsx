import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import EditModal from './EditModal.jsx'

const COLS = [
  ['master_id', 'Nr.'], ['gsm', 'GSM'], ['name', 'Name'], ['plant', 'Werk'],
  ['konto', 'Konto'], ['tarif', 'Tarif'], ['vertragsende', 'Vtg.-Ende'], ['bemerkung', 'Bemerkung'],
]
const NUM = new Set(['master_id', 'konto'])
const PROVIDERS = ['Vodafone', 'Telekom', 'O2', 'Ohne SIM', 'Frei']

export default function Participants({ view, user, openTaskPids = [], onChanged }) {
  const canWrite = user.role === 'write' || user.role === 'admin'
  const canDelete = user.role === 'admin'
  const taskSet = new Set(openTaskPids)

  const [q, setQ] = useState('')
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [menu, setMenu] = useState(null)
  const [editId, setEditId] = useState(undefined)
  const [mergeMode, setMergeMode] = useState(false)
  const [selected, setSelected] = useState(new Set())

  const load = useCallback((query) => {
    api.participants(view, query)
      .then((d) => { setRows(d.participants); setTotal(d.total); setError('') })
      .catch((e) => setError(e.message))
  }, [view])

  useEffect(() => { setQ(''); setMergeMode(false); setSelected(new Set()) }, [view])
  useEffect(() => {
    const t = setTimeout(() => load(q), 150)
    return () => clearTimeout(t)
  }, [view, q, load])
  useEffect(() => {
    const close = () => setMenu(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  async function act(fn) {
    setMenu(null)
    try { await fn(); load(q); onChanged && onChanged() } catch (e) { alert(e.message) }
  }

  function addTask(row) {
    setMenu(null)
    const k = prompt('Kommentar zur Aufgabe:', '')
    if (k !== null) act(() => api.createTask(row.id, { kommentar: k }))
  }

  function toggleMergeMode() {
    setMergeMode((m) => !m)
    setSelected(new Set())
  }

  function toggleSelect(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function doMerge() {
    if (selected.size < 2) { alert('Bitte mindestens 2 Einträge auswählen.'); return }
    if (!confirm(selected.size + ' Einträge zusammenführen?\n\nLeere Felder des ältesten '
                 + 'Eintrags werden aus den anderen gefüllt, die übrigen gelöscht.')) return
    try {
      await api.merge(Array.from(selected))
      setMergeMode(false); setSelected(new Set())
      load(q); onChanged && onChanged()
    } catch (e) { alert(e.message) }
  }

  function handleRowClick(row) {
    if (mergeMode) toggleSelect(row.id)
  }

  return (
    <div className="wrap">
      <div className="bar">
        <input className="q" type="search" value={q} autoFocus
               placeholder="Suche: Name, GSM, Werk, Konto, Tarif …"
               onChange={(e) => setQ(e.target.value)} />
        {canWrite && !mergeMode && (
          <>
            <button className="btn accent" onClick={() => setEditId(null)}>+ Neu</button>
            <button className="btn" onClick={toggleMergeMode}>Zusammenführen</button>
          </>
        )}
        {mergeMode ? (
          <span className="hint-dim">
            <b>{selected.size} ausgewählt</b> — <a href="#" onClick={(e) => { e.preventDefault(); doMerge() }}>zusammenführen</a>
            {' · '}<a href="#" onClick={(e) => { e.preventDefault(); toggleMergeMode() }}>abbrechen</a>
          </span>
        ) : (
          <>
            <span className="count">{total} Treffer</span>
            {error && <span className="err">{error}</span>}
            <span className="hint-dim">Rechtsklick = Aktionen · Doppelklick = Bearbeiten</span>
          </>
        )}
      </div>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Status</th>{COLS.map(([k, l]) => <th key={k}>{l}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}
                    className={(taskSet.has(r.id) ? 'hastask ' : '') + (selected.has(r.id) ? 'selected' : '')}
                    style={mergeMode ? { cursor: 'pointer' } : undefined}
                    onClick={() => handleRowClick(r)}
                    onDoubleClick={() => !mergeMode && setEditId(r.id)}
                    onContextMenu={(e) => { if (mergeMode) return; e.preventDefault(); setMenu({ x: e.pageX, y: e.pageY, row: r }) }}>
                  <td>{r.verified === 1
                    ? <span className="badge ok">geprüft</span>
                    : <span className="badge open">offen</span>}</td>
                  {COLS.map(([k]) => (
                    <td key={k} className={NUM.has(k) ? 'num' : ''}>
                      {r[k] === null || r[k] === '' || r[k] === undefined ? '—' : r[k]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {menu && (
        <div className="ctxmenu"
             style={{ left: Math.min(menu.x, window.innerWidth - 210), top: menu.y }}
             onClick={(e) => e.stopPropagation()}>
          <div className="ctx-item" onClick={() => { setEditId(menu.row.id); setMenu(null) }}>Bearbeiten</div>
          {canWrite && (
            <>
              <div className="ctx-sep" />
              <div className="ctx-item" onClick={() => addTask(menu.row)}>Zu Aufgabe …</div>
              <div className="ctx-item" onClick={() => act(() => api.verify(menu.row.id))}>
                {menu.row.verified ? 'Als offen markieren' : 'Als geprüft markieren'}
              </div>
              {PROVIDERS.filter((p) => p !== menu.row.provider).map((p) => (
                <div key={p} className="ctx-item" onClick={() => act(() => api.move(menu.row.id, p))}>→ nach {p}</div>
              ))}
            </>
          )}
          {canDelete && (
            <>
              <div className="ctx-sep" />
              <div className="ctx-item danger" onClick={() => {
                if (confirm('Wirklich löschen?\n\n' + (menu.row.name || ('ID ' + menu.row.id))))
                  act(() => api.remove(menu.row.id))
                else setMenu(null)
              }}>Löschen</div>
            </>
          )}
        </div>
      )}

      {editId !== undefined && (
        <EditModal id={editId} canWrite={canWrite}
                   onClose={() => setEditId(undefined)}
                   onSaved={() => { setEditId(undefined); load(q) }} />
      )}
    </div>
  )
}
