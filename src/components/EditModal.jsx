import { useEffect, useState } from 'react'
import { api } from '../api'

const FIELDS = [
  ['gsm', 'GSM-Nummer', 'text'], ['name', 'Name', 'text'], ['plant', 'Werk (Plant)', 'text'],
  ['konto', 'Konto', 'text'], ['telefon', 'Telefon (alt)', 'text'], ['tarif', 'Tarif', 'text'],
  ['sim_nummer', 'SIM-Seriennummer', 'text'], ['rahmenvertrag', 'Rahmenvertrag', 'text'],
  ['startdatum', 'Erstaktivierung', 'date'], ['vertragsbeginn', 'Vertragsbeginn', 'date'],
  ['vertragsende', 'Vertragsende', 'date'], ['kuendigung', 'Kündigung zu', 'date'],
  ['syno', 'Syno-Gerät 1', 'text'], ['start_syno', 'Syno 1 seit', 'date'],
  ['syno2', 'Syno-Gerät 2', 'text'], ['start_syno2', 'Syno 2 seit', 'date'],
]
const PROVIDERS = ['Vodafone', 'Telekom', 'O2', 'Ohne SIM', 'Frei']

export default function EditModal({ id, canWrite, onClose, onSaved }) {
  const isNew = id === null
  const [p, setP] = useState(isNew ? { provider: 'Vodafone', verified: 1 } : null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0 })

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
          <button type="button" className="x" onClick={onClose}>×</button>
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
                         readOnly={!canWrite} onChange={(e) => set(k, e.target.value)} />
                </label>
              ))}
            </div>
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
