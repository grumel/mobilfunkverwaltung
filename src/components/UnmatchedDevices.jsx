import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'
import { toastError } from '../toast.jsx'

// Verwaiste Syno-Geräte ('Nicht zugeordnet') – Zeilen ohne passenden Teilnehmer.
export default function UnmatchedDevices({ onBack, user }) {
  const canWrite = user?.role === 'write' || user?.role === 'admin'
  const canDelete = user?.role === 'admin'
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [menu, setMenu] = useState(null)

  function load() {
    api.unmatchedDevices().then((d) => { setRows(d.devices); setError('') }).catch((e) => setError(e.message))
  }
  useEffect(load, [])
  useEffect(() => {
    const close = () => setMenu(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  const shown = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase('de')
    if (!needle) return rows
    return rows.filter((r) => [r.quelle, r.benutzer, r.gsm, r.geraet, r.startdatum]
      .some((v) => String(v || '').toLocaleLowerCase('de').includes(needle)))
  }, [rows, q])

  async function run(fn) {
    setMenu(null)
    try { await fn(); load() } catch (e) { toastError(e.message) }
  }

  function edit(row) {
    setMenu(null)
    const benutzer = prompt('Benutzer / Name:', row.benutzer || '')
    if (benutzer === null) return
    const gsm = prompt('GSM:', row.gsm || '')
    if (gsm === null) return
    const geraet = prompt('Gerät:', row.geraet || '')
    if (geraet === null) return
    const startdatum = prompt('Startdatum (JJJJ-MM-TT):', row.startdatum || '')
    if (startdatum === null) return
    run(() => api.unmatchedUpdate(row.id, { benutzer, gsm, geraet, startdatum }))
  }

  async function assign(row) {
    setMenu(null)
    const search = prompt('Teilnehmer suchen (Name oder GSM):', row.benutzer || row.gsm || '')
    if (search === null) return
    try {
      const data = await api.participants('alle', search)
      if (!data.participants.length) { toastError('Kein passender Teilnehmer gefunden.'); return }
      const choices = data.participants.slice(0, 20)
      const text = choices.map((p) => `${p.id}: ${p.name || '—'} · ${p.gsm || 'ohne GSM'} · ${p.provider || 'Vodafone'}`).join('\n')
      const id = prompt(`Teilnehmer-ID eingeben:\n\n${text}`, String(choices[0].id))
      if (id === null) return
      await api.unmatchedAssign(row.id, id)
      load()
    } catch (e) { toastError(e.message) }
  }

  function createParticipant(row) {
    setMenu(null)
    const name = prompt('Name des neuen Teilnehmers:', row.benutzer || '')
    if (name === null) return
    const gsm = prompt('GSM (kann leer bleiben):', row.gsm || '')
    if (gsm === null) return
    const plant = prompt('Werk (kann leer bleiben):', '')
    if (plant === null) return
    const konto = prompt('Konto (kann leer bleiben):', '')
    if (konto === null) return
    run(() => api.unmatchedCreateParticipant(row.id, { name, gsm, plant, konto }))
  }

  function remove(row) {
    setMenu(null)
    if (!confirm(`Verwaistes Gerät wirklich löschen?\n\n${row.geraet || row.benutzer || 'ID ' + row.id}`)) return
    run(() => api.unmatchedDelete(row.id))
  }

  return (
    <div className="wrap">
      <div className="bar">
        {onBack && <button className="btn" onClick={onBack}>← Statistik</button>}
        <input className="q" type="search" value={q} placeholder="Verwaiste Geräte durchsuchen …"
               onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 360 }} />
        <span className="count">{shown.length} von {rows.length} verwaiste Geräte</span>
        {error && <span className="err">{error}</span>}
        {canWrite && <span className="hint-dim">Rechtsklick = Aktionen · Doppelklick = Bearbeiten</span>}
      </div>
      <p className="hint-dim" style={{ margin: '0 0 10px' }}>
        Syno-Geräte aus dem Import, die keinem Teilnehmer zugeordnet werden konnten.
        Sie können korrigiert, einem vorhandenen Teilnehmer zugeordnet oder als neuer Teilnehmer unter „Ohne SIM“ angelegt werden.
      </p>
      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Quelle</th><th>Benutzer</th><th>GSM</th><th>Gerät</th><th>Startdatum</th><th>Importiert</th><th>Aktionen</th></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}
                    onDoubleClick={() => canWrite && edit(r)}
                    onContextMenu={(e) => { if (!canWrite && !canDelete) return; e.preventDefault(); setMenu({ x: e.pageX, y: e.pageY, row: r }) }}>
                  <td>{r.quelle || '—'}</td>
                  <td>{r.benutzer || '—'}</td>
                  <td>{r.gsm || '—'}</td>
                  <td>{r.geraet || '—'}</td>
                  <td>{r.startdatum ? fmtDate(r.startdatum) : '—'}</td>
                  <td>{r.importdatum ? fmtDate(r.importdatum) : '—'}</td>
                  <td>
                    {canWrite && <button className="btn" onClick={() => assign(r)}>Zuordnen</button>}
                    {canWrite && <button className="btn" onClick={() => createParticipant(r)} style={{ marginLeft: 6 }}>Neu anlegen</button>}
                  </td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr><td colSpan="7" className="hint-dim">Keine passenden verwaisten Geräte.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {menu && (
        <div className="ctxmenu"
             style={{ left: Math.min(menu.x, window.innerWidth - 230), top: menu.y }}
             onClick={(e) => e.stopPropagation()}>
          {canWrite && <div className="ctx-item" onClick={() => edit(menu.row)}>Bearbeiten</div>}
          {canWrite && <div className="ctx-item" onClick={() => assign(menu.row)}>Teilnehmer zuordnen …</div>}
          {canWrite && <div className="ctx-item" onClick={() => createParticipant(menu.row)}>Als neuen Teilnehmer anlegen …</div>}
          {canDelete && <><div className="ctx-sep" /><div className="ctx-item danger" onClick={() => remove(menu.row)}>Löschen</div></>}
        </div>
      )}
    </div>
  )
}
