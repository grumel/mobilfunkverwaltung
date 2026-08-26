import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Settings() {
  const [s, setS] = useState(null)
  const [dbPath, setDbPath] = useState('')
  const [databaseUrl, setDatabaseUrl] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [msg, setMsg] = useState('')
  const [warn, setWarn] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function load() {
    api.getSettings()
      .then((d) => { setS(d); setDbPath(d.db_path || ''); setDatabaseUrl(d.database_url || '') })
      .catch((e) => setError(e.message))
  }
  useEffect(() => { load() }, [])

  async function save(e) {
    e.preventDefault()
    setBusy(true); setMsg(''); setWarn(''); setError('')
    try {
      const d = await api.saveSettings({ db_path: dbPath, database_url: databaseUrl })
      setMsg(d.message + ' ' + (d.note || ''))
      if (d.warning) setWarn(d.warning)
      load()
    } catch (ex) { setError(ex.message) } finally { setBusy(false) }
  }

  if (error) return <div className="wrap"><span className="err">{error}</span></div>
  if (!s) return <div className="wrap"><p className="hint-dim">Lädt…</p></div>

  return (
    <div className="wrap">
      <div className="editcard">
        <h2 className="modal-head" style={{ border: 'none', margin: 0 }}>Einstellungen – Datenbank</h2>
        <p className="hint-dim">Programm und Datenbank sind getrennt: Das Programm liegt in seinem
           Verzeichnis, die Datenbank kann beliebig woanders liegen (lokal, Netzlaufwerk, OneDrive).
           Hier legst du fest, welche Datenbank die Web-App verwendet.</p>

        <div className="meta">
          <span>Aktive Datenbank (seit Start): <b>{s.current_url}</b></span>
        </div>
        <p className="hint-dim">Konfigurationsdatei: <code>{s.config_file}</code><br />
           Standard-Datenbank: <code>{s.default_path}</code></p>

        {s.env_override && (
          <div className="warnbox">
            <b>Hinweis:</b> Die Umgebungsvariable <code>DATABASE_URL</code> ist gesetzt und hat
            <b> Vorrang</b>. Einstellungen hier werden erst wirksam, wenn die Variable entfernt wird.
          </div>
        )}
        {msg && <div className="flash" style={{ background: '#e6f4ea', borderColor: '#bfe3c8', color: '#1e7d34' }}>{msg}</div>}
        {warn && <div className="warnbox">{warn}</div>}

        <form onSubmit={save}>
          <label className="field wide">
            <span>Datenbank-Datei (SQLite) <em>– vollständiger Pfad zur .db-Datei</em></span>
            <input type="text" value={dbPath} onChange={(e) => setDbPath(e.target.value)}
                   placeholder="z. B. D:\Daten\Mobilfunk\mobilfunk.db oder \\server\share\mobilfunk.db" />
          </label>

          <p className="hint-dim" style={{ cursor: 'pointer', marginTop: 8 }}
             onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? '▾' : '▸'} Erweitert: volle DATABASE_URL (z. B. für PostgreSQL)
          </p>
          {showAdvanced && (
            <>
              <label className="field wide">
                <span>DATABASE_URL</span>
                <input type="text" value={databaseUrl} onChange={(e) => setDatabaseUrl(e.target.value)}
                       placeholder="postgresql+psycopg://user:pw@host:5432/mobilfunk" />
              </label>
              <p className="hint-dim">Wenn gesetzt, hat dies Vorrang vor dem Datei-Pfad oben.</p>
            </>
          )}

          <div className="warnbox" style={{ background: '#eef4ff', borderColor: '#bcd0f0', color: '#33507a' }}>
            <b>Datenbank verschieben?</b> Erst die Datei <code>mobilfunk.db</code> an den neuen Ort
            <b> kopieren</b>, dann hier den neuen Pfad eintragen. Anschließend die Web-App neu starten.
          </div>

          <div className="modal-actions">
            <button type="submit" className="btn accent" disabled={busy}>{busy ? 'Speichern…' : 'Speichern'}</button>
          </div>
        </form>
      </div>

      {s.backup_available && (
        <div className="editcard" style={{ marginTop: 14 }}>
          <h2 className="modal-head" style={{ border: 'none', margin: 0 }}>Sicherung</h2>
          <p className="hint-dim">Lädt die aktuelle Datenbank als <b>konsistente</b> Sicherungskopie
             herunter (Online-Backup inkl. laufender Änderungen). Bewahre die Datei an einem
             sicheren Ort auf; zum Wiederherstellen einfach als <code>mobilfunk.db</code> zurückkopieren.</p>
          <div className="modal-actions">
            <a className="btn accent" href={api.backupUrl()} download>Backup herunterladen</a>
          </div>
        </div>
      )}
    </div>
  )
}
