import { toastOk, toastError } from '../toast.jsx'

// Zeigt einen erzeugten Mailtext (Betreff/Body) zum Kopieren, optional mit
// PDF-Download-Knopf (Kündigung/Rücknahme).
export default function MailResultModal({ title, to, subject, body, downloadUrl, onClose }) {
  async function copyMail() {
    const text = `An: ${to}\nBetreff: ${subject}\n\n${body}`
    try { await navigator.clipboard.writeText(text); toastOk('Mailtext kopiert.') }
    catch { toastError('Kopieren nicht möglich – bitte manuell markieren.') }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()} onSubmit={(e) => e.preventDefault()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="x" aria-label="Dialog schließen" onClick={onClose}>×</button>
        </div>
        <div className="flash ok-flash">
          {downloadUrl ? 'PDF erzeugt. ' : ''}Mailtext an <b>{to}</b> kopieren und in Outlook versenden{downloadUrl ? ' (PDF anhängen)' : ''}:
        </div>
        <div className="field"><span>Betreff</span>
          <input value={subject} readOnly />
        </div>
        <label className="field" style={{ marginTop: 10 }}><span>Nachricht</span>
          <textarea rows="7" value={body} readOnly />
        </label>
        <div className="modal-actions">
          {downloadUrl && (
            <a className="btn accent" href={downloadUrl} download>PDF herunterladen</a>
          )}
          <button type="button" className="btn" onClick={copyMail}>Mailtext kopieren</button>
          <button type="button" className="btn" onClick={onClose}>Schließen</button>
        </div>
      </form>
    </div>
  )
}
