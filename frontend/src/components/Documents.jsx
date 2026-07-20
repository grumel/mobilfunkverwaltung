import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtDate } from '../format.js'

// „Dokumente-Ordner" als Web-Ansicht: alle lokal gespeicherten Schreiben
// (Kündigung/Rücknahme-PDFs, Neuvertrag-Texte) mit Download.
function kindOf(name) {
  const n = name.toLowerCase()
  if (n.startsWith('kuendigung')) return 'Kündigung'
  if (n.startsWith('ruecknahme')) return 'Rücknahme'
  if (n.startsWith('neuvertrag')) return 'Neuvertrag'
  return '—'
}
function sizeKB(b) { return (b / 1024).toFixed(1) + ' KB' }

export default function Documents() {
  const [rows, setRows] = useState([])
  const [folder, setFolder] = useState('')
  const [error, setError] = useState('')

  function load() {
    api.documents().then((d) => { setRows(d.documents); setFolder(d.folder); setError('') })
      .catch((e) => setError(e.message))
  }
  useEffect(load, [])

  return (
    <div className="wrap">
      <div className="bar">
        <span className="count">{rows.length} Dokumente</span>
        <button className="btn" onClick={load}>Aktualisieren</button>
        {error && <span className="err">{error}</span>}
      </div>
      <p className="hint-dim" style={{ margin: '0 0 10px' }}>
        Gespeichert auf dem Server unter <code>{folder}</code>. Erzeugte Kündigungen,
        Rücknahmen (PDF) und Neuverträge (Text) liegen hier und können heruntergeladen werden.
      </p>

      <div className="tablecard">
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Art</th><th>Dateiname</th><th>Erstellt</th><th>Größe</th><th>Aktion</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td>{kindOf(r.name)}</td>
                  <td>{r.name}</td>
                  <td>{fmtDate(r.modified)}</td>
                  <td className="num">{sizeKB(r.size)}</td>
                  <td className="rowactions">
                    <a className="linkbtn" href={api.documentUrl(r.name)} download>Herunterladen</a>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan="5" className="hint-dim">Noch keine Dokumente erzeugt.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
