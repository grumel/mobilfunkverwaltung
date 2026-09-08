import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { toastError } from '../toast.jsx'

const SAVE_DELAY_MS = 800

// Persönliches Notizfeld ("Notizen"-Knopf oben rechts). Fortlaufend
// beschreibbar, speichert automatisch (debounced) statt einen eigenen
// Speichern-Knopf zu verlangen – beim Schließen wird sofort geflusht, damit
// die letzten Tastenanschläge nicht verloren gehen.
export default function NotesModal({ onClose }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('') // '' | 'speichert' | 'gespeichert' | 'fehler'
  const timerRef = useRef(null)
  const pendingRef = useRef(null) // letzter noch nicht gespeicherter Text

  useEffect(() => {
    let cancelled = false
    api.getMyNotes()
      .then((d) => { if (!cancelled) setText(d.notes || '') })
      .catch((ex) => toastError(ex.message))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => {
      cancelled = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  async function doSave(value) {
    setStatus('speichert')
    try {
      await api.saveMyNotes(value)
      pendingRef.current = null
      setStatus('gespeichert')
    } catch (ex) {
      setStatus('fehler')
      toastError(ex.message)
    }
  }

  function handleChange(e) {
    const value = e.target.value
    setText(value)
    pendingRef.current = value
    setStatus('')
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSave(value), SAVE_DELAY_MS)
  }

  function handleClose() {
    if (timerRef.current) clearTimeout(timerRef.current)
    if (pendingRef.current !== null) doSave(pendingRef.current)
    onClose()
  }

  const statusLabel = status === 'speichert' ? 'Speichert …'
    : status === 'gespeichert' ? 'Gespeichert ✓'
    : status === 'fehler' ? 'Fehler beim Speichern' : ' '

  return (
    <div className="overlay" onClick={handleClose}>
      <div className="modal notes" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Notizen</h3>
          <button type="button" className="x" aria-label="Dialog schließen" onClick={handleClose}>×</button>
        </div>
        <p className="hint-dim" style={{ marginTop: -6 }}>
          Persönliches Notizfeld – wird automatisch gespeichert, nur für dich sichtbar.
        </p>
        <label className="field">
          <span className="sr-only">Notizen</span>
          <textarea rows="14" value={text} autoFocus disabled={loading}
                    placeholder="Hier fortlaufend Notizen eintragen …"
                    onChange={handleChange} />
        </label>
        <div className="modal-actions" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="hint-dim">{statusLabel}</span>
          <button type="button" className="btn accent" onClick={handleClose}>Schließen</button>
        </div>
      </div>
    </div>
  )
}
