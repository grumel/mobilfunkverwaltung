# Produktionsbericht Monorepo-Migration

## Ergebnis

Die Linux-Produktion wurde am 21. Juli 2026 erfolgreich von den getrennten
Checkouts auf das Monorepository umgestellt. Installiert ist der veröffentlichte
Stand `v1.0.0-monorepo` mit Commit
`3a822f64c9ba0b2d856028939c428ff582cee61f`.

Die bisherigen Checkouts und alle persistenten Daten blieben erhalten. Es gab
keine Datenbankmigration und keine Löschung oder Überschreibung von Altdaten.

## Ausgangszustand

- Backend: `/opt/mobilfunk-web`
- Frontend: `/opt/mobilfunk-frontend`
- SQLite-Datenbank und Laufzeitdaten: `/var/lib/mobilfunk`
- Backend-Dienst: `mobilfunk-web`, Gunicorn auf `127.0.0.1:8000`
- Reverse-Proxy: Caddy auf Port 80

Beide Dienste waren vor der Migration aktiv. Die bestehende Environment-Datei
und das bestehende Session-Secret wurden unverändert übernommen; geheime Werte
wurden weder protokolliert noch in dieses Repository geschrieben.

## Sicherung

Vor der ersten produktiven Änderung wurde ein Migrationsbackup unter
`/var/backups/mobilfunk-migration/20260721-013015` angelegt. Es enthält:

- die vorherige Caddy- und systemd-Konfiguration,
- ein konsistentes SQLite-Online-Backup,
- Archive beider alten Anwendungscheckouts und der persistenten Daten,
- SHA-256-Prüfsummen aller Sicherungsdateien.

Das SQLite-Backup wurde mit `sqlite3.Connection.backup()` erstellt. Der
anschließende `PRAGMA integrity_check` ergab `ok`; die abschließende
Prüfsummenprüfung war ebenfalls erfolgreich. Zusätzlich liegen die vom
Rollback-Skript erwarteten Konfigurationskopien als
`/etc/caddy/Caddyfile.pre-monorepo` und
`/etc/systemd/system/mobilfunk-web.service.pre-monorepo` vor.

## Installation und Datenanbindung

Das Monorepository wurde neu unter `/opt/mobilfunkverwaltung` installiert. Der
installierte Commit und der Release-Tag wurden vor und nach dem Build geprüft.
Die Backend-Abhängigkeiten wurden in einer neuen virtuellen Umgebung unter
`backend/.venv` installiert; das React-Frontend wurde mit `npm ci` und
`npm run build` neu gebaut.

Die Anwendung verwendet weiterhin die vorhandene Datenwurzel
`/var/lib/mobilfunk`. Datenbank, Dokumente, Kündigungen und Syno-Dateien wurden
nicht verschoben. Die Environment-Datei hat den Modus `0600` und gehört
`root:root`; der Dienst liest sie weiterhin über systemd ein.

Die vollständige Vorher-/Nachher-Erfassung steht im lokalen
[Migrationsprotokoll](PRODUCTION_MIGRATION_LOG.md). Zum Zeitpunkt der Sicherung
waren SQLite-WAL- und SHM-Dateien vorhanden; sie wurden im Datenarchiv
mitgesichert.

Vor der Umschaltung wurde der neue Backend-Build erfolgreich auf einem
separaten Loopback-Port gegen die Produktionskonfiguration getestet.

## systemd und Caddy

Die aktiven Konfigurationen zeigen nun auf:

- systemd-Arbeitsverzeichnis: `/opt/mobilfunkverwaltung/backend`
- Gunicorn aus: `/opt/mobilfunkverwaltung/backend/.venv`
- Caddy-Frontend-Root: `/opt/mobilfunkverwaltung/frontend/dist`

Die Caddy-Konfiguration wurde vor dem Neustart erfolgreich validiert. Danach
wurden `mobilfunk-web` und `caddy` neu gestartet und als aktiv bestätigt.

## Tests und kontrollierter Rollback

Der erste Umschaltversuch löste das vorbereitete Rollback aus, weil der
Smoke-Test unmittelbar nach `systemctl restart` vor der Bereitschaft von
Gunicorn ausgeführt wurde. Die Journale zeigten einen normalen, fehlerfreien
Start; der Altbetrieb wurde durch `scripts/rollback-linux.sh` erfolgreich
wiederhergestellt. Beim zweiten Versuch wurde vor dem Smoke-Test begrenzt auf
Backend-Bereitschaft gewartet.

Die endgültige Abnahme ergab:

- `mobilfunk-web`: aktiv
- `caddy`: aktiv
- Backend `/api/version`: HTTP 200
- Frontend über Caddy: HTTP 200 und gültiges HTML
- API über Caddy: HTTP 200
- Linux-Smoke-Test: bestanden
- SQLite `PRAGMA integrity_check`: `ok`
- Referenzbestände vor und nach der Umschaltung: unverändert
- erwartete Sicherheits-Header: vorhanden
- Prozess-Arbeitsverzeichnis und ausgelieferter Frontend-Pfad: Monorepo-Pfade
- `npm audit --omit=dev`: 0 Schwachstellen; kein Audit-Fix ausgeführt

Der optionale authentifizierte Smoke-Test wurde nicht ausgeführt, weil keine
dedizierten Testzugangsdaten bereitgestellt wurden. Es wurden bewusst keine
produktiven Datensätze verändert, um schreibende Tests durchzuführen.
Die manuelle fachliche Abnahme (Login/Logout, reversible Schreibprüfung,
Dokumentzugriff und Browserkonsole) bleibt daher als Beobachtungspunkt mit
dediziertem Testkonto offen.

## Rollback- und Aufbewahrungsstatus

Ein Rollback bleibt mit `scripts/rollback-linux.sh` möglich. Es stellt die
vorherigen systemd- und Caddy-Konfigurationen wieder her und verändert keine
Produktionsdaten. Die alten Checkouts `/opt/mobilfunk-web` und
`/opt/mobilfunk-frontend` sowie das vollständige Migrationsbackup bleiben
unverändert erhalten.

## Datenschutz- und Secret-Prüfung

Dieser Bericht enthält keine Zugangsdaten, Secrets, Environment-Werte,
personenbezogenen Datensätze, Dokumentnamen, internen Hostnamen oder internen
IP-Adressen. Er dokumentiert ausschließlich technische Pfade, aggregierte
Prüfergebnisse und den veröffentlichten Git-Stand.
