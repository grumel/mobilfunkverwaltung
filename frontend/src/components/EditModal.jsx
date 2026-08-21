import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { loadWerkKonto } from '../werkkonto.js'
import { toastOk, toastError } from '../toast.jsx'

const FIELDS = [
  ['gsm', 'GSM-Nummer', 'text'], ['name', 'Name', 'text'], ['plant', 'Werk (Plant)', 'text'],
  ['konto', 'Konto', 'text'], ['telefon', 'Telefon (alt)', 'text'], ['tarif', 'Tarif', 'text'],
  ['sim_nummer', 'SIM-Seriennummer', 'text'], ['rahmenvertrag', 'Rahmenvertrag', 'text'],
  ['startdatum', 'Erstaktivierung', 'date'], ['vertragsbeginn', 'Vertragsbeginn', 'date'],
  ['vertragsende', 'Vertragsende', 'date'], ['kuendigung', 'Kündigung zu', 'date'],
]
// Syno-Geräte: je Gerät eine Zeile mit Gerät · Syno seit · IMEI nebeneinander.
const SYNO_ROWS = [
  { geraet: ['syno', 'Syno-Gerät 1'], datum: ['start_syno', 'Syno 1 seit'], imei: ['imei', 'IMEI-Nr. 1'] },
  { geraet: ['syno2', 'Syno-Gerät 2'], datum: ['start_syno2', 'Syno 2 seit'], imei: ['imei2', 'IMEI-Nr. 2'] },
]
const PROVIDERS = ['Vodafone', 'Telekom', 'O2', 'Ohne SIM', 'Frei']

export default function EditModal({ id, canWrite, onClose, onSaved }) {
  const isNew = id === null
  const [p, setP] = useState(isNew ? { provider: 'Vodafone', verified: 1 } : null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [wk, setWk] = useState({ werk_to_konto: {}, konto_to_werk: {} })
  const vodafoneFileRef = useRef(null)
  const synoFileRef = useRef(null)

  useEffect(() => { loadWerkKonto().then(setWk) }, [])

  function pickVodafone() {
    if (!(p.gsm || '').trim()) { toastError('Bitte zuerst eine GSM-Nummer eingeben.'); return }
    vodafoneFileRef.current.value = ''
    vodafoneFileRef.current.click()
  }
  function pickSyno() {
    if (!(p.gsm || '').trim() && !(p.name || '').trim()) {
      toastError('Bitte zuerst eine GSM-Nummer oder einen Namen eingeben.'); return
    }
    synoFileRef.current.value = ''
    synoFileRef.current.click()
  }
  async function runMatch(source, file) {
    if (!file) return
    setError('')
    const gsm = (p.gsm || '').trim()
    const name = (p.name || '').trim()
    try {
      const d = source === 'vodafone'
        ? await api.matchVodafone(file, gsm)
        : await api.matchSyno(file, gsm, name)
      if (!d.match) {
        toastError(source === 'vodafone'
          ? `Keine Zeile mit GSM „${gsm}" in der Datei gefunden.`
          : 'Keine passende Zeile (GSM/Name) in der Datei gefunden.')
        return
      }
      setP((prev) => ({ ...prev, ...d.match }))
      toastOk('Felder aus der Datei übernommen – bitte prüfen und speichern.')
    } catch (ex) { toastError(ex.message) }
  }

  function startDrag(e) {
    if (e.target.closest('.x')) return
    const startX = e.clientX, startY = e.clientY
    const startPos = pos
    function onMove(ev) {
      setPos({ x: startPos.x + (ev.clientX - startX), y: startPos.y + (ev.clientY - startY) })
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  useEffect(() => {
    if (!isNew) {
      api.participant(id).then((d) => setP(d.participant)).catch((e) => setError(e.message))
    }
  }, [id, isNew])

  function set(k, v) { setP((prev) => ({ ...prev, [k]: v })) }

  // Werk/Konto sind feste Paare: bei Änderung des einen das andere automatisch füllen.
  function setField(k, v) {
    if (k === 'plant') {
      const konto = wk.werk_to_konto[v.trim()]
      setP((prev) => ({ ...prev, plant: v, ...(konto ? { konto } : {}) }))
    } else if (k === 'konto') {
      const werk = wk.konto_to_werk[v.trim()]
      setP((prev) => ({ ...prev, konto: v, ...(werk ? { plant: werk } : {}) }))
    } else {
      set(k, v)
    }
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (isNew) await api.create(p)
      else await api.update(id, p)
      onSaved()
    } catch (ex) { setError(ex.message); setBusy(false) }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}
            style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}>
        <div className="modal-head" onMouseDown={startDrag}>
          <h3>{isNew ? 'Neuer Teilnehmer' : ('Bearbeiten: ' + ((p && p.name) || ('ID ' + id)))}</h3>
          <button type="button" className="x" aria-label="Dialog schließen" onClick={onClose}>×</button>
        </div>
        {error && <div className="flash">{error}</div>}
        {!p ? <p className="hint-dim">Lädt…</p> : (
          <>
            <div className="grid">
              <label className="field"><span>Register (Provider)</span>
                <select value={p.provider || 'Vodafone'} disabled={!canWrite}
                        onChange={(e) => set('provider', e.target.value)}>
                  {PROVIDERS.map((x) => <option key={x}>{x}</option>)}
                </select>
              </label>
              {FIELDS.map(([k, l, t]) => (
                <label className="field" key={k}><span>{l}</span>
                  <input type={t === 'date' ? 'date' : 'text'} value={p[k] || ''}
                         readOnly={!canWrite} onChange={(e) => setField(k, e.target.value)} />
                </label>
              ))}
            </div>

            <div className="synogrid">
              {SYNO_ROWS.map((r) => (
                <div className="synorow" key={r.geraet[0]}>
                  <label className="field"><span>{r.geraet[1]}</span>
                    <input type="text" value={p[r.geraet[0]] || ''} readOnly={!canWrite}
                           onChange={(e) => set(r.geraet[0], e.target.value)} /></label>
                  <label className="field"><span>{r.datum[1]}</span>
                    <input type="date" value={p[r.datum[0]] || ''} readOnly={!canWrite}
                           onChange={(e) => set(r.datum[0], e.target.value)} /></label>
                  <label className="field"><span>{r.imei[1]}</span>
                    <input type="text" value={p[r.imei[0]] || ''} readOnly={!canWrite}
                           onChange={(e) => set(r.imei[0], e.target.value)} /></label>
                </div>
              ))}
            </div>

            {canWrite && (
              <div className="matchrow">
                <span className="hint-dim">Einzel-Abgleich aus Exportdatei:</span>
                <button type="button" className="btn" onClick={pickVodafone}>Vodafone …</button>
                <button type="button" className="btn" onClick={pickSyno}>Syno …</button>
                <input ref={vodafoneFileRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }}
                       onChange={(e) => runMatch('vodafone', e.target.files[0])} />
                <input ref={synoFileRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }}
                       onChange={(e) => runMatch('syno', e.target.files[0])} />
              </div>
            )}
            <label className="field wide"><span>Bemerkung</span>
              <textarea rows="2" value={p.bemerkung || ''} readOnly={!canWrite}
                        onChange={(e) => set('bemerkung', e.target.value)} />
            </label>
            <label className="field wide"><span>Prüfungsnotiz</span>
              <input type="text" value={p.pruefung_grund || ''} readOnly={!canWrite}
                     onChange={(e) => set('pruefung_grund', e.target.value)} />
            </label>
            <label className="check">
              <input type="checkbox" checked={p.verified === 1} disabled={!canWrite}
                     onChange={(e) => set('verified', e.target.checked ? 1 : 0)} /> Verifiziert (geprüft)
            </label>
            <div className="modal-actions">
              {canWrite
                ? <button type="submit" className="btn accent" disabled={busy}>{busy ? 'Speichern…' : 'Speichern'}</button>
                : <span className="hint-dim">Nur-Lese-Zugriff</span>}
              <button type="button" className="btn" onClick={onClose}>{canWrite ? 'Abbrechen' : 'Schließen'}</button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
