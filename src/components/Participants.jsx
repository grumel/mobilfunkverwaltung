import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'
import { toastError } from '../toast.jsx'
import EditModal from './EditModal.jsx'
import NeuvertragModal from './NeuvertragModal.jsx'
import MailResultModal from './MailResultModal.jsx'

const COLS = [
  ['master_id', 'Nr.'], ['gsm', 'GSM'], ['name', 'Name'], ['plant', 'Werk'],
  ['konto', 'Konto'], ['tarif', 'Tarif'], ['sim_nummer', 'SIM-Seriennummer'],
  ['vertragsbeginn', 'Vertragsbeginn'], ['vertragsende', 'Vtg.-Ende'], ['kuendigung', 'Kündigung zu'],
  ['rahmenvertrag', 'Rahmenvertrag'], ['syno', 'Syno'], ['start_syno', 'Syno seit'],
  ['bemerkung', 'Bemerkung'],
]
const NUM = new Set(['master_id', 'konto'])
const DATE_COLS = new Set(['vertragsbeginn', 'vertragsende', 'kuendigung', 'start_syno'])
const PROVIDERS = ['Vodafone', 'Telekom', 'O2', 'Ohne SIM', 'Frei']

export default function Participants({ view, q, user, openTaskPids = [], onChanged }) {
  const canWrite = user.role === 'write' || user.role === 'admin'
  const canDelete = user.role === 'admin'
  const taskSet = new Set(openTaskPids)

  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [menu, setMenu] = useState(null)
  const [editId, setEditId] = useState(undefined)
  const [mergeMode, setMergeMode] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [sort, setSort] = useState({ key: 'name', dir: 1 })
  const [neuvertrag, setNeuvertrag] = useState(false)
  const [mailResult, setMailResult] = useState(null)   // Kündigungs-Ergebnis

  const load = useCallback((query) => {
    api.participants(view, query)
      .then((d) => { setRows(d.participants); setTotal(d.total); setError('') })
      .catch((e) => setError(e.message))
  }, [view])

  useEffect(() => { setMergeMode(false); setSelected(new Set()) }, [view])
  useEffect(() => { load(q) }, [view, q, load])
  useEffect(() => {
    const close = () => setMenu(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  async function act(fn) {
    setMenu(null)
    try { await fn(); load(q); onChanged && onChanged() } catch (e) { toastError(e.message) }
  }

  function addTask(row) {
    setMenu(null)
    const k = prompt('Kommentar zur Aufgabe:', '')
    if (k !== null) act(() => api.createTask(row.id, { kommentar: k }))
  }

  async function createKuendigung(row, kind) {
    setMenu(null)
    try {
      const d = await api.kuendigung(row.id, kind)
      setMailResult({
        title: kind === 'kuendigung' ? 'Kündigung erstellt' : 'Rücknahme erstellt',
        to: d.to, subject: d.subject, body: d.body,
        downloadUrl: api.kuendigungUrl(d.file),
      })
      onChanged && onChanged()
    } catch (e) { toastError(e.message) }
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
    if (selected.size < 2) { toastError('Bitte mindestens 2 Einträge auswählen.'); return }
    if (!confirm(selected.size + ' Einträge zusammenführen?\n\nLeere Felder des ältesten '
                 + 'Eintrags werden aus den anderen gefüllt, die übrigen gelöscht.')) return
    try {
      await api.merge(Array.from(selected))
      setMergeMode(false); setSelected(new Set())
      load(q); onChanged && onChanged()
    } catch (e) { toastError(e.message) }
  }

  function handleRowClick(row) {
    if (mergeMode) toggleSelect(row.id)
  }

  function toggleSort(key) {
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: 1 }))
  }

  function csvCell(s) {
    return /[";\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  function exportCsv() {
    const header = ['Status', ...COLS.map(([, l]) => l)]
    const lines = [header]
    sortedRows.forEach((r) => {
      const status = r.verified === 1 ? 'geprüft' : 'offen'
      const vals = COLS.map(([k]) => {
        let v = r[k]
        if (v === null || v === undefined) v = ''
        else if (DATE_COLS.has(k)) v = fmtDate(v)
        return String(v)
      })
      lines.push([status, ...vals])
    })
    const csv = lines.map((row) => row.map(csvCell).join(';')).join('\r\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mobilfunk_${view}_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  function sortArrow(key) {
    if (sort.key !== key) return null
    return <span className="sortarrow">{sort.dir === 1 ? ' ▲' : ' ▼'}</span>
  }

  const sortedRows = [...rows].sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key]
    if (av === bv) return 0
    if (av === null || av === undefined || av === '') return 1
    if (bv === null || bv === undefined || bv === '') return -1
    if (NUM.has(sort.key) || sort.key === 'verified') return (Number(av) - Number(bv)) * sort.dir
    return String(av).localeCompare(String(bv), 'de') * sort.dir
  })

  return (
    <div className="wrap">
      <div className="bar">
        {canWrite && !mergeMode && (
          <>
            <button className="btn accent" onClick={() => setEditId(null)}>+ Neu</button>
            <button className="btn" onClick={() => setNeuvertrag(true)}>Neuvertrag</button>
            <button className="btn" onClick={toggleMergeMode}>Zusammenführen</button>
          </>
        )}
        {!mergeMode && (
          <button className="btn" onClick={exportCsv} disabled={rows.length === 0}>CSV-Export</button>
        )}
        {mergeMode ? (
          <span className="hint-dim">
            <b>{selected.size} ausgewählt</b> — <a href="#" onClick={(e) => { e.preventDefault(); doMerge() }}>zusammenführen</a>
            {' · '}<a href="#" onClick={(e) => { e.preventDefault(); toggleMergeMode() }}>abbrechen</a>
          </span>
        ) : (
          <>
            <span className="count">{total} Treffer{q ? ' (alle Reiter)' : ''}</span>
            {error && <span className="err">{error}</span>}
            <span className="hint-dim">Rechtsklick = Aktionen · Doppelklick = Bearbeiten · Spaltenkopf = Sortieren</span>
          </>
        )}
      </div>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort('verified')}>Status{sortArrow('verified')}</th>
                {COLS.map(([k, l]) => (
                  <th key={k} className="sortable" onClick={() => toggleSort(k)}>{l}{sortArrow(k)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((r) => (
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
                      {r[k] === null || r[k] === '' || r[k] === undefined
                        ? '—'
                        : (DATE_COLS.has(k) ? fmtDate(r[k]) : r[k])}
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
              <div className="ctx-sep" />
              <div className="ctx-item" onClick={() => createKuendigung(menu.row, 'kuendigung')}>Kündigung erstellen …</div>
              <div className="ctx-item" onClick={() => createKuendigung(menu.row, 'ruecknahme')}>Kündigung zurücknehmen …</div>
              <div className="ctx-sep" />
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

      {neuvertrag && (
        <NeuvertragModal onClose={() => setNeuvertrag(false)}
                         onDone={() => { load(q); onChanged && onChanged() }} />
      )}

      {mailResult && (
        <MailResultModal {...mailResult} onClose={() => setMailResult(null)} />
      )}
    </div>
  )
}
