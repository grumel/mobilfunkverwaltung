// Kurzanleitung / Hilfe. Wird über den „Hilfe"-Knopf in der oberen Leiste geöffnet.
export default function HelpModal({ onClose }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal help" style={{ maxWidth: 760 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head" style={{ cursor: 'default' }}>
          <h3>Hilfe &amp; Anleitung</h3>
          <button type="button" className="x" onClick={onClose}>×</button>
        </div>

        <div className="help-body">
          <p className="hint-dim">Mobilfunkverwaltung – Web. Diese Kurzanleitung erklärt die wichtigsten Funktionen.</p>

          <h4>Anmeldung &amp; Rollen</h4>
          <ul>
            <li>Anmeldung mit denselben Zugangsdaten wie in der Desktop-App.</li>
            <li><b>Lesen</b>: nur ansehen. <b>Schreiben</b>: bearbeiten/importieren. <b>Admin</b>: zusätzlich Benutzer &amp; Einstellungen.</li>
            <li>Oben rechts <b>Passwort</b>: eigenes Passwort ändern. <b>Abmelden</b>: Sitzung beenden.</li>
          </ul>

          <h4>Reiter &amp; Suche</h4>
          <ul>
            <li>Die Reiter <b>Vodafone / Telekom / O2 / Ohne SIM / Frei</b> zeigen die Teilnehmer je Anbieter.</li>
            <li><b>Prüfungen</b> = offene (ungeprüfte) Einträge, <b>Unvollständig</b> = fehlende Pflichtfelder, <b>Duplikate</b> = doppelte Namen.</li>
            <li>Die <b>globale Suche</b> oben durchsucht <i>alle</i> Reiter gleichzeitig, egal welcher gerade gewählt ist.</li>
            <li>Klick auf einen <b>Spaltenkopf</b> sortiert; erneuter Klick kehrt die Reihenfolge um.</li>
          </ul>

          <h4>Bearbeiten &amp; Aktionen</h4>
          <ul>
            <li><b>Doppelklick</b> auf eine Zeile öffnet den Bearbeiten-Dialog (verschiebbar an der Titelleiste).</li>
            <li><b>Werk</b> und <b>Konto</b> füllen sich gegenseitig automatisch aus (feste Paare).</li>
            <li><b>+ Neu</b>: neuen Teilnehmer anlegen. <b>CSV-Export</b>: aktuelle Liste für Excel exportieren.</li>
            <li><b>Rechtsklick</b> auf eine Zeile öffnet das Aktionsmenü:
              <ul>
                <li>Als geprüft / offen markieren</li>
                <li>Kündigung erstellen / zurücknehmen → erzeugt ein <b>PDF zum Download</b> und einen <b>Mailtext zum Kopieren</b> (in Outlook einfügen, PDF anhängen, senden)</li>
                <li>Zu einem anderen Anbieter verschieben, zu Aufgabe hinzufügen, löschen (Admin)</li>
              </ul>
            </li>
            <li><b>Zusammenführen</b>: mehrere Einträge markieren und zu einem verschmelzen.</li>
          </ul>

          <h4>Neuvertrag</h4>
          <ul>
            <li>Knopf <b>Neuvertrag</b>: Name, Werk (Konto füllt sich) und Tarif eingeben. Der Eintrag wird ungeprüft angelegt und ein <b>Mailtext</b> erzeugt, den du an Nicole versendest.</li>
          </ul>

          <h4>Weitere Bereiche</h4>
          <ul>
            <li><b>Aufgaben</b>: Wiedervorlagen mit Fälligkeit (überfällig = rot, heute = gelb).</li>
            <li><b>Statistik</b>: Kennzahlen und Verteilungen.</li>
            <li><b>Protokoll / Audit</b>: Import-Verlauf bzw. sicherheitsrelevante Aktionen (Audit nur für Admin).</li>
            <li><b>Import</b> (Admin): Vodafone-Liste mit Vorschau/Bestätigen, Syno-Geräte.</li>
            <li><b>Benutzer</b> (Admin): Konten anlegen/bearbeiten, Rolle setzen, Passwort zurücksetzen.</li>
          </ul>

          <h4>Darstellung</h4>
          <ul>
            <li>Der Knopf <b>🌙 / ☀️</b> oben schaltet zwischen hellem und dunklem Design um. Die Wahl bleibt gespeichert.</li>
          </ul>

          <h4>Als App installieren (Edge)</h4>
          <ul>
            <li>Menü „…" → <b>Apps</b> → „Diese Website als App installieren" – dann läuft die Verwaltung in einem eigenen Fenster mit App-Symbol.</li>
          </ul>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn accent" onClick={onClose}>Schließen</button>
        </div>
      </div>
    </div>
  )
}
