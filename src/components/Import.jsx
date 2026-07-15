import { useState } from 'react'
import { api } from '../api'

const VF_TILES = [
  ['updated', 'Aktualisiert', 'blue'], ['created', 'Neu angelegt', 'green'],
  ['review', 'Zur Prüfung', 'orange'], ['skipped', 'Übersprungen', 'grey'],
]
const SY_TILES = [
  ['matched_gsm', 'GSM-Matches', 'blue'], ['matched_name', 'Name-Matches', 'blue'],
  ['neu_angelegt', 'Neu angelegt', 'green'],
  ['duplicate', 'Bereits vorhanden', 'grey'], ['slots_full', 'Kein freier Slot', 'orange'],
  ['unmatched', 'Nicht zugeordnet', 'orange'], ['skipped', 'Übersprungen', 'grey'],
]

function Tiles({ data, spec }) {
  return (
    <div className="tiles">
      {spec.map(([k, l, cls]) => (
        <div key={k} className={'tile ' + cls}><div className="tval">{data[k] ?? 0}</div><div className="tlbl">{l}</div></div>
      ))}
      <div className="tile red"><div className="tval">{(data.errors || []).length}</div><div className="tlbl">Fehler</div></div>
    </div>
  )
}

export default function Import() {
  const [vfFile, setVfFile] = useState(null)
  const [vfPreview, setVfPreview] = useState(null)
  const [vfResult, setVfResult] = useState(null)
  const [syFile, setSyFile] = useState(null)
  const [syCreate, setSyCreate] = useState(true)
  const [syResult, setSyResult] = useState(null)
  const [enFile, setEnFile] = useState(null)
  const [enResult, setEnResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function doEnrich(e) {
    e.preventDefault()
    if (!enFile) return
    setBusy(true); setError(''); setEnResult(null)
    try {
      const d = await api.synoEnrich(enFile)
      setEnResult(d)
      setEnFile(null)
    } catch (ex) { setError(ex.message) } finally { setBusy(false) }
  }

  async function doVfPreview(e) {
    e.preventDefault()
    if (!vfFile) return
    setBusy(true); setError(''); setVfResult(null)
    try {
      const d = await api.vodafonePreview(vfFile)
      setVfPreview(d.preview)
    } catch (ex) { setError(ex.message) } finally { setBusy(false) }
  }

  async function doVfConfirm() {
    setBusy(true); setError('')
    try {
      const d = await api.vodafoneConfirm()
      setVfResult(d.result)
      setVfPreview(null)
      setVfFile(null)
    } catch (ex) { setError(ex.message) } finally { setBusy(false) }
  }

  async function doSyno(e) {
    e.preventDefault()
    if (!syFile) return
    if (!confirm('Syno-Import jetzt ausführen? (Backup wird vorher erstellt)')) return
    setBusy(true); setError(''); setSyResult(null)
    try {
      const d = await api.synoImport(syFile, syCreate)
      setSyResult(d.result)
      setSyFile(null)
    } catch (ex) { setError(ex.message) } finally { setBusy(false) }
  }

  return (
    <div className="wrap">
      {error && <div className="flash">{error}</div>}

      <div className="importgrid">
        <div className="importcard">
          <h3>Vodafone-Import</h3>
          <p className="hint-dim">Aktualisiert Tarif, SIM, Vertragsdaten per GSM. Setzt das Werk
             aus dem Konto-Mapping. Zuerst <b>Vorschau</b>, dann bestätigen. Vor dem echten
             Import wird automatisch ein Backup erstellt.</p>
          {!vfPreview && !vfResult && (
            <form onSubmit={doVfPreview}>
              <input type="file" accept=".xlsx,.xls" required
                     onChange={(e) => setVfFile(e.target.files[0])} />
              <button type="submit" className="btn accent" disabled={busy}>
                {busy ? 'Prüfe…' : 'Datei prüfen (Vorschau)'}
              </button>
            </form>
          )}

          {vfPreview && (
            <div>
              <p className="hint-dim">Datei: <b>{vfFile?.name}</b> · noch nichts gespeichert.</p>
              <Tiles data={vfPreview} spec={VF_TILES} />
              {vfPreview.header_warnings?.length > 0 && (
                <div className="warnbox">
                  <b>⚠ Spaltenköpfe weichen ab:</b>
                  <ul>{vfPreview.header_warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                </div>
              )}
              {vfPreview.changes?.length > 0 && (
                <>
                  <h4 className="sub">Änderungen ({vfPreview.changes.length})</h4>
                  <pre className="logbox">{vfPreview.changes.join('\n')}</pre>
                </>
              )}
              <div className="modal-actions">
                <button className="btn accent" disabled={busy} onClick={doVfConfirm}>
                  {busy ? 'Importiere…' : 'Import jetzt durchführen'}
                </button>
                <button className="btn" onClick={() => { setVfPreview(null); setVfFile(null) }}>Abbrechen</button>
              </div>
            </div>
          )}

          {vfResult && (
            <div>
              <Tiles data={vfResult} spec={VF_TILES} />
              <h4 className="sub">Protokoll</h4>
              <pre className="logbox tall">{(vfResult.log_lines || []).join('\n')}</pre>
              <button className="btn" onClick={() => setVfResult(null)}>Neuer Import</button>
            </div>
          )}
        </div>

        <div className="importcard">
          <h3>Syno-Import</h3>
          <p className="hint-dim">Trägt Syno-Geräte per GSM/Name in bis zu zwei Slots ein.
             Läuft <b>direkt</b> (mit vorherigem Backup). Zeilen ohne Treffer landen unter
             „Nicht zugeordnet".</p>
          {!syResult && (
            <form onSubmit={doSyno}>
              <input type="file" accept=".xlsx,.xls" required
                     onChange={(e) => setSyFile(e.target.files[0])} />
              <label className="check" style={{ marginTop: 0 }}>
                <input type="checkbox" checked={syCreate}
                       onChange={(e) => setSyCreate(e.target.checked)} />
                Nicht gefundene Personen als neue Teilnehmer anlegen (zur Prüfung)
              </label>
              <button type="submit" className="btn accent" disabled={busy}>
                {busy ? 'Importiere…' : 'Syno importieren'}
              </button>
            </form>
          )}
          {syResult && (
            <div>
              <Tiles data={syResult} spec={SY_TILES} />
              <h4 className="sub">Protokoll</h4>
              <pre className="logbox tall">{(syResult.log_lines || []).join('\n')}</pre>
              <button className="btn" onClick={() => setSyResult(null)}>Neuer Import</button>
            </div>
          )}
        </div>

        <div className="importcard">
          <h3>Syno anreichern (vor dem Import)</h3>
          <p className="hint-dim">Korrigiert <b>GSM</b> und <b>Namen</b> in der Syno-Datei
             anhand deiner Datenbank und erzeugt eine farblich markierte Kopie
             (grün = ergänzt, blau = GSM korrigiert, gelb = kein Treffer, bitte prüfen).
             Das <b>Original wird gespeichert</b> und alles protokolliert. Die
             angereicherte Datei danach oben unter „Syno-Import" importieren.</p>
          {!enResult && (
            <form onSubmit={doEnrich}>
              <input type="file" accept=".xlsx,.xls" required
                     onChange={(e) => setEnFile(e.target.files[0])} />
              <button type="submit" className="btn accent" disabled={busy}>
                {busy ? 'Reichere an…' : 'Datei anreichern'}
              </button>
            </form>
          )}
          {enResult && (
            <div>
              <div className="tiles">
                <div className="tile green"><div className="tval">{enResult.summary.fixed_gsm}</div><div className="tlbl">GSM ergänzt</div></div>
                <div className="tile blue"><div className="tval">{enResult.summary.changed_gsm}</div><div className="tlbl">GSM korrigiert</div></div>
                <div className="tile green"><div className="tval">{enResult.summary.fixed_name}</div><div className="tlbl">Namen ergänzt</div></div>
                <div className="tile orange"><div className="tval">{enResult.summary.no_match}</div><div className="tlbl">Ohne Treffer</div></div>
              </div>
              <p className="hint-dim">Original gespeichert: <b>{enResult.original}</b></p>
              <div className="modal-actions">
                <a className="btn accent" href={api.synoFileUrl(enResult.enriched)} download>Angereicherte Datei herunterladen</a>
                <button className="btn" onClick={() => setEnResult(null)}>Neue Datei</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
