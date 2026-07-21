# Lokales Migrationsprotokoll

Erfassung: 21.07.2026, vor der produktiven Umschaltung und nach der Abnahme.
Dieses Protokoll enthält keine Secrets, Zugangsdaten, personenbezogenen Daten,
internen Hostnamen oder internen IP-Adressen.

## Ist-Zustand vor Änderungen

- Dienste: `mobilfunk-web` und `caddy`, beide `active (running)`.
- Bestehende Unit: `/etc/systemd/system/mobilfunk-web.service`.
- Bestehende Unit vor der Umstellung: WorkingDirectory und Gunicorn unter
  `/opt/mobilfunk-web`, zwei Worker, Bind `127.0.0.1:8000`, EnvironmentFile
  `/var/lib/mobilfunk/mobilfunk.env`.
- Bestehende Caddy-Konfiguration: `/etc/caddy/Caddyfile`, Port 80, Proxy für
  `/api/*` nach `127.0.0.1:8000`, statischer Root `/opt/mobilfunk-frontend`.
- Backend: `/opt/mobilfunk-web`.
- Frontend: `/opt/mobilfunk-frontend`.
- SQLite: `/var/lib/mobilfunk/mobilfunk.db`, Größe beim Backup 774144 Bytes;
  WAL und SHM waren vorhanden und wurden im Datenarchiv berücksichtigt.
- Datenverzeichnisse: `/var/lib/mobilfunk/Dokumente`, `Kuendigungen` und
  `SynoDateien`.
- Environment: `/var/lib/mobilfunk/mobilfunk.env`; Schlüssel wurden geprüft,
  Werte nicht protokolliert.
- Eigentümer/Gruppen: alte Checkouts `itberlin:itberlin`, persistente Daten
  `mobilfunk:mobilfunk`; Environment-Datei ursprünglich restriktiv und nach
  der Umstellung `root:root`, Modus `0600`.
- Versionen: Python 3.13.5, Node 20.20.2, Caddy 2.11.4, Gunicorn 26.0.0.
- Prozesse/Ports: Gunicorn auf `127.0.0.1:8000`, Caddy auf `*:80`; keine
  weitere produktive Belegung dieser Ports festgestellt.

## Sicherung vor Änderungen

Backup-Verzeichnis:
`/var/backups/mobilfunk-migration/20260721-013015`.

Enthalten sind SQLite-Online-Backup, Datenarchiv einschließlich WAL/SHM,
Dokumente/Uploads, Environment-Datei, Caddyfile, systemd-Unit, Archive der
alten Checkouts, SHA-256-Prüfsummen und die zugehörigen Rechte/Metadaten.
`PRAGMA integrity_check` ergab `ok`; alle Prüfsummen wurden erfolgreich
verifiziert. Das Rollback-Skript konnte die Konfigurationsbackups testweise
wiederherstellen; die Datenbank wurde dabei nie überschrieben.

## Installation und Umschaltung

`/opt/mobilfunkverwaltung` war vorab nicht vorhanden. Installiert wurde exakt
`origin/main` auf Commit `3a822f64c9ba0b2d856028939c428ff582cee61f`, Tag
`v1.0.0-monorepo`, mit neuer Backend-Virtualenv, `pip install`, `npm ci` und
`npm run build`. Es wurde weder globales Python verändert noch `npm audit fix`
ausgeführt. `frontend/dist/index.html` wurde erzeugt.

Die produktive Datenwurzel blieb außerhalb des Checkouts unverändert. Vor dem
Start wurden Datenbank, Tabellen, Integrität und Verzeichnisrechte geprüft.
Die neue Unit verwendet `/opt/mobilfunkverwaltung/backend`; Caddy verwendet
`/opt/mobilfunkverwaltung/frontend/dist`.

## Tests und Ereignisse

- Caddy-Konfiguration validiert.
- Neuer Backend-Build vorab auf separatem Loopback-Port gestartet und `/api/version`
  erfolgreich getestet.
- Erster Umschaltversuch wegen Readiness-Race kontrolliert zurückgerollt;
  Altbetrieb anschließend erfolgreich geprüft.
- Zweiter Versuch mit Readiness-Wartephase erfolgreich.
- `scripts/smoke-test-linux.sh`: bestanden (Backend, Frontend, API).
- `mobilfunk-web` und `caddy`: aktiv, ohne Restart-Loop.
- SQLite-Integrität nach Umschaltung: `ok`; Bestände unverändert.
- `npm audit --omit=dev`: `found 0 vulnerabilities`; keine Audit-Fix-Aktion.
- Authentifizierter Login/API-Test sowie schreibende fachliche Tests wurden
  mangels dedizierter Testzugangsdaten bzw. sicherer Testdaten nicht ausgeführt.

## Endzustand

Produktiver Commit: `0ae8b14d6f6a722cef2018656f7b0fb550d603d9` (Bericht und
dieses Protokoll), nach `origin/main` gepusht. Alte Checkouts, Backup und
Rollback-Konfigurationen bleiben erhalten. Offener Beobachtungspunkt ist die
manuelle fachliche Abnahme mit einem dedizierten Testkonto (Login, Logout,
Lesen/Schreiben eines reversiblen Testdatensatzes, Dokumentzugriff).
