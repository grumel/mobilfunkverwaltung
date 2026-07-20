import { useEffect, useState } from 'react'
import { api } from '../api'
import { loadWerkKonto } from '../werkkonto.js'
import { toastOk, toastError } from '../toast.jsx'

// Neuvertrag bestellen: Teilnehmer anlegen + Mailtext zum Kopieren erzeugen.
export default function NeuvertragModal({ onClose, onDone }) {
  const [form, setForm] = useState({ name: '', werk: '', konto: '', tarif: '' })
  const [wk, setWk] = useState({ werk_to_konto: {}, konto_to_werk: {} })
  const [mail, setMail] = useState(null)     // Ergebnis: {to, subject, body}
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { loadWerkKonto().then(setWk) }, [])

  function set(k, v) {
    if (k === 'werk') {
      const konto = wk.werk_to_konto[v.trim()]
      setForm((p) => ({ ...p, werk: v, ...(konto ? { konto } : {}) }))
    } else if (k === 'konto') {
      const werk = wk.konto_to_werk[v.trim()]
      setForm((p) => ({ ...p, konto: v, ...(werk ? { werk } : {}) }))
    } else {
      setForm((p) => ({ ...p, [k]: v }))
    }
  }

  async function submit(e) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const d = await api.neuvertrag(form)
      setMail({ to: d.to, subject: d.subject, body: d.body })
      onDone && onDone()
    } catch (ex) { setError(ex.message); setBusy(false) }
  }

  async function copyMail() {
    const text = `An: ${mail.to}\nBetreff: ${mail.subject}\n\n${mail.body}`
    try { await navigator.clipboard.writeText(text); toastOk('Mailtext kopiert.') }
    catch { toastError('Kopieren nicht möglich – bitte manuell markieren.') }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="modal-head">
          <h3>Neuvertrag bestellen</h3>
          <button type="button" className="x" aria-label="Dialog schließen" onClick={onClose}>×</button>
        </div>
        {error && <div className="flash">{error}</div>}

        {!mail ? (
          <>
            <div className="grid">
              <label className="field"><span>Name</span>
                <input value={form.name} autoFocus onChange={(e) => set('name', e.target.value)} required />
              </label>
              <label className="field"><span>Tarif</span>
                <input value={form.tarif} onChange={(e) => set('tarif', e.target.value)} required />
              </label>
              <label className="field"><span>Werk</span>
                <input value={form.werk} onChange={(e) => set('werk', e.target.value)} required />
              </label>
              <label className="field"><span>Konto (füllt sich automatisch)</span>
                <input value={form.konto} onChange={(e) => set('konto', e.target.value)} />
              </label>
            </div>
            <div className="modal-actions">
              <button type="submit" className="btn accent" disabled={busy}>{busy ? 'Anlegen…' : 'Anlegen & Mailtext erzeugen'}</button>
              <button type="button" className="btn" onClick={onClose}>Abbrechen</button>
            </div>
          </>
        ) : (
          <>
            <div className="flash ok-flash">Teilnehmer angelegt. Mailtext an <b>{mail.to}</b> kopieren und in Outlook versenden:</div>
            <div className="field"><span>Betreff</span>
              <input value={mail.subject} readOnly />
            </div>
            <label className="field" style={{ marginTop: 10 }}><span>Nachricht</span>
              <textarea rows="9" value={mail.body} readOnly />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn accent" onClick={copyMail}>Mailtext kopieren</button>
              <button type="button" className="btn" onClick={onClose}>Schließen</button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
