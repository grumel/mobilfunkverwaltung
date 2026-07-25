# Mobilfunkverwaltung

[![Backend](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/backend.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/backend.yml)
[![Frontend](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/frontend.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/frontend.yml)
[![Monorepo structure](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/monorepo.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/monorepo.yml)
[![Windows runtime](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/windows.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/windows.yml)

Webbasierte Verwaltung von Mobilfunkteilnehmern, Verträgen, Importen,
Dokumenten und Aufgaben. Dieses Repository führt das bestehende Flask-Backend
und das React/Vite-Frontend in einer gemeinsamen, weiterhin klar getrennten
Codebasis zusammen.

## Status

Die Monorepo-Migration ist abgeschlossen. Der produktive Stand ist
`v1.0.0-monorepo` (Commit `3a822f64c9ba0b2d856028939c428ff582cee61f`).
Phase 2 „Technische Konsolidierung“ erfasst technische Schulden und Testlücken;
funktionale Änderungen sind ausdrücklich ausgeschlossen.

- Backend-Historie bis `420fb1d` unter `backend/` übernommen.
- Frontend-Historie bis `ceaeaf4` unter `frontend/` übernommen.
- Beide Historien wurden ohne Squash über getrennte Subtree-Merge-Commits
  erhalten.
- Backendlogik, React-Oberfläche, REST-API und Datenbankschema wurden durch die
  Migration nicht verändert.
- Produktives `main` enthält den geprüften Merge und den Produktionsbericht.
- Der Cleanup-Arbeitsstand liegt auf `chore/project-cleanup`; Änderungen dort
  bleiben API-, UI- und Datenbank-neutral.
- Linux bleibt die produktive Zielplattform mit Gunicorn, Caddy und systemd.
- Die Windows-Runtime ist implementiert und liegt auf
  `feature/windows-runtime`. Sie ist eine lokale Einzelplatz-Webanwendung mit
  Waitress, kein Windows-Dienst und kein EXE-Paket. Linux-Pfade, REST-API,
  Datenbankschema und React-Oberfläche bleiben unverändert.
- `feature/windows-runtime` enthält zusätzlich die isolierten
  Backend-Regressionstests, den Frontend-Integritätscheck und die
  Performance-Baseline. Der Branch ist ein Fast-Forward auf `main` und wird
  ausschließlich über einen geprüften Pull Request übernommen.

## Architektur

Linux-Produktivbetrieb:

```text
Browser
   |
   v
Caddy :80
   |-- /*      -> frontend/dist (React/Vite)
   `-- /api/*  -> Gunicorn :8000 -> Flask -> SQLAlchemy -> SQLite
```

Caddy ist der öffentliche Einstiegspunkt, Gunicorn lauscht nur lokal.
Schreibbare Daten liegen außerhalb des Git-Checkouts.

Windows-Runtime (lokaler Einzelplatz, ohne Caddy):

```text
Browser
   |
   v
Waitress 127.0.0.1:8000  (backend/run_windows.py)
   |-- /api/*  -> Flask -> SQLAlchemy -> SQLite
   `-- /*      -> frontend/dist, SPA-Fallback auf index.html
```

Ein schlanker WSGI-Wrapper trennt `/api/*` von den statischen Dateien, liefert
für unbekannte Pfade `index.html` aus und weist Pfade außerhalb des
Frontend-Roots ab. Beide Plattformen benutzen denselben WSGI-Einstiegspunkt
`backend/wsgi.py`.

## Repository-Struktur

```text
mobilfunkverwaltung/
├── backend/                    Flask, SQLAlchemy und Fachlogik
│   ├── modules/                gemeinsame Import-/Dokument-/Datenlogik
│   ├── platform_support/       plattformneutrale Basispfade
│   ├── webapp/                 App-Factory, API, Modelle und Jinja-Fallback
│   ├── requirements.txt
│   ├── requirements-server.txt
│   ├── run.py                  plattformneutraler lokaler Start
│   ├── run_windows.py          Waitress mit integrierter SPA-Auslieferung
│   └── wsgi.py                 gemeinsamer WSGI-Einstiegspunkt
├── frontend/                   React/Vite-Oberfläche
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── deploy/
│   ├── linux/                  Caddy, systemd, Installer und Betriebsdoku
│   └── windows/                PowerShell-Runtime: install, start, stop,
│                               update, backup und Konfigurationsvorlage
├── scripts/
│   ├── backend-ci-smoke.py           isolierter CI-Smoke-Test
│   ├── backend-regression-tests.py   isolierte Regressionstests
│   ├── frontend-regression-check.mjs Integritätscheck des Frontend-Builds
│   ├── performance-baseline.py       reproduzierbare Performance-Baseline
│   ├── smoke-test-linux.sh           Produktions-Smoke-Test Linux
│   ├── smoke-test-windows.ps1        Smoke-Test der Windows-Runtime
│   └── rollback-linux.sh             nur Konfigurations-/Release-Rollback
├── docs/
├── .github/workflows/
├── .gitignore
└── README.md
```

## Voraussetzungen

Für die lokale Entwicklung:

- Python 3.12 oder neuer
- Node.js 20 LTS einschließlich npm
- Git

Für Linux-Produktion zusätzlich:

- Debian oder Ubuntu mit systemd
- Gunicorn aus `backend/requirements-server.txt`
- Caddy
- LibreOffice für den bestehenden PDF-Export
- optional `sqlite3` für konsistente Online-Backups

Für die Windows-Runtime zusätzlich:

- Windows 10/11 oder Windows Server 2019+ mit PowerShell 5.1+
- Waitress aus `backend/requirements-server.txt` (dort plattformabhängig
  markiert; Linux installiert weiterhin nur Gunicorn)
- Microsoft Word für den PDF-Export und Outlook für Mail-Entwürfe, angesprochen
  über COM per `pywin32`. LibreOffice wird unter Windows dadurch nicht
  benötigt; ohne Word springt es als Ersatz ein, auch als portable Kopie über
  `MOBILFUNK_SOFFICE`.
- weder Caddy noch Administratorrechte

## Lokale Entwicklung

Die folgenden Schritte gelten für Linux und macOS. Unter Windows übernimmt
`deploy\windows\start-dev.ps1` Installation, Build und Start in einem Schritt,
siehe [Windows-Runtime](#windows-runtime).

Backend einrichten und starten:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
cd backend
.venv/bin/python run.py
```

Das Backend läuft standardmäßig auf <http://127.0.0.1:5001>.

Frontend in einem zweiten Terminal starten:

```bash
cd frontend
npm ci
npm run dev
```

Vite läuft auf <http://127.0.0.1:5173> und leitet `/api` an das lokale Backend
weiter. Lokale Datenbanken, virtuelle Umgebungen, `node_modules`, Builds, Logs
und Secrets sind über die gemeinsame `.gitignore` ausgeschlossen.

## Build und lokale Prüfung

Frontend-Produktionsbuild:

```bash
cd frontend
npm ci
npm run build
```

Backend kompilieren und isolierten Smoke-Test ausführen:

```bash
python3 -m compileall -q backend scripts/backend-ci-smoke.py
backend/.venv/bin/python scripts/backend-ci-smoke.py
```

Der Smoke-Test erzeugt eine temporäre SQLite-Datenbank, legt ausschließlich
einen temporären CI-Benutzer an und prüft App-Factory, `/api/version`, Login und
authentifizierte Session. Produktive Daten werden nicht gelesen.

Regressionstests, Frontend-Integrität und Performance-Baseline:

```bash
backend/.venv/bin/python scripts/backend-regression-tests.py
node scripts/frontend-regression-check.mjs
backend/.venv/bin/python scripts/performance-baseline.py
```

Alle drei laufen gegen temporäre Fixtures beziehungsweise den lokalen Build und
greifen nie auf produktive Daten zu.

Linux-Dateien prüfen:

```bash
find deploy/linux scripts -type f -name '*.sh' -exec bash -n {} \;
caddy validate --config deploy/linux/Caddyfile --adapter caddyfile
```

## Continuous Integration

Alle Workflows laufen bei Pull Requests nach `main`. Zusätzlich laufen
`backend.yml`, `frontend.yml` und `monorepo.yml` bei Pushes auf `main` und
`chore/monorepo-migration`, `windows.yml` bei Pushes auf `main`,
`chore/project-cleanup` und `feature/windows-runtime`:

- `backend.yml` (Ubuntu): Python 3.12, pip-Cache, Abhängigkeiten, `compileall`
  und isolierter Flask/Login/API/SQLite-Smoke-Test.
- `frontend.yml` (Ubuntu): Node.js 20, npm-Cache, `npm ci`, optionales
  `npm test` und Vite-Produktionsbuild.
- `monorepo.yml` (Ubuntu): Pflichtstruktur, Syntax aller Linux-Shellskripte und
  Python-Kompilierung.
- `windows.yml` (`windows-latest`): Abhängigkeiten, `compileall`, Smoke- und
  Regressionstests, Frontend-Build, PowerShell-Syntaxprüfung aller Skripte
  unter `deploy/windows/` sowie ein echter Waitress-Start mit anschließendem
  `scripts/smoke-test-windows.ps1`.

Alle Jobs besitzen nur lesenden Repository-Zugriff und geben keine Secrets aus.
Der Windows-Job verwendet ausschließlich ein CI-Secret und ein temporäres
Datenverzeichnis unterhalb von `RUNNER_TEMP`.

## Linux-Produktion

Standardpfade:

| Zweck | Pfad |
| --- | --- |
| Monorepository | `/opt/mobilfunkverwaltung` |
| Backend | `/opt/mobilfunkverwaltung/backend` |
| Python-Umgebung | `/opt/mobilfunkverwaltung/backend/.venv` |
| Frontend-Build | `/opt/mobilfunkverwaltung/frontend/dist` |
| Daten, Dokumente und Logs | `/var/lib/mobilfunk` |
| SQLite | `/var/lib/mobilfunk/mobilfunk.db` |
| Environment/Secret | `/var/lib/mobilfunk/mobilfunk.env` |
| Caddy-Konfiguration | `/etc/caddy/Caddyfile` |
| systemd-Unit | `/etc/systemd/system/mobilfunk-web.service` |

Für eine bestehende Produktion nicht direkt den Installer ausführen. Zuerst die
rückrollbare Schritt-für-Schritt-Anleitung einschließlich Datenbank-,
Konfigurations- und Anwendungsbackup verwenden:

- [Produktionsmigration](docs/PRODUCTION_MIGRATION.md)
- [Linux-Installation](deploy/linux/INSTALL.md)
- [Deployment-Übersicht](deploy/README.md)

Nach der Umstellung:

```bash
cd /opt/mobilfunkverwaltung
./scripts/smoke-test-linux.sh
```

Optional prüft das Skript Login und Session, wenn `SMOKE_USERNAME` und
`SMOKE_PASSWORD` ausschließlich zur Laufzeit gesetzt werden. Im Skript sind
keine Zugangsdaten hinterlegt.

Das Rollback-Werkzeug stellt nur zuvor gesicherte Caddy-/systemd-Dateien und
optional einen Release-Symlink wieder her. Es löscht oder überschreibt niemals
die Datenbank:

```bash
sudo /opt/mobilfunkverwaltung/scripts/rollback-linux.sh
```

## Windows-Runtime

Die Windows-Runtime ist eine lokale Webanwendung mit Waitress und integrierter
React-SPA-Auslieferung auf einem einzigen Port. Sie benötigt keinen Caddy, keine
Administratorrechte, keinen Windows-Dienst und kein EXE-/WebView2-Paket.
Details, Backup und Einschränkungen stehen in [docs/WINDOWS.md](docs/WINDOWS.md).

Installation und Start in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\bootstrap.ps1 -Install
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1
```

`bootstrap.ps1` prüft Python, Node.js, Git, Word und Outlook, installiert
fehlende Werkzeuge auf Wunsch per winget — nach Möglichkeit ohne
Administratorrechte — und ruft anschließend `install.ps1` auf. Mit `-CheckOnly`
gibt es nur den Bericht. Eine Setup-EXE gibt es bewusst nicht: unsignierte
Installationsprogramme werden in verwalteten Netzen blockiert.

`install.ps1` legt Venv, Abhängigkeiten, Frontend-Build, Datenordner und eine
Environment-Datei mit frisch erzeugtem Secret an. `start.ps1` startet Waitress
auf <http://127.0.0.1:8000/> und wartet, bis `/api/version` antwortet; mit
`-OpenBrowser` wird zusätzlich der Browser geöffnet. Weiter stehen
`stop.ps1`, `update.ps1`, `backup.ps1`, `start-dev.ps1` und `uninstall.ps1`
bereit. `uninstall.ps1` entfernt nur Venv, Frontend-Build und Caches im
Checkout; Datenbank, Dokumente und Secret bleiben unangetastet.

Standardpfade:

| Zweck | Pfad |
| --- | --- |
| Daten, Dokumente und Logs | `%PROGRAMDATA%\Mobilfunkverwaltung` |
| SQLite | `%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.db` |
| Environment/Secret | `%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.env.ps1` |
| Backups | `%PROGRAMDATA%\Mobilfunkverwaltung\backups\<Zeitstempel>` |
| Frontend-Build | `frontend\dist` im Checkout |

`%LOCALAPPDATA%` dient als Fallback, ein gesetztes `MOBILFUNK_DATA_DIR` hat
Vorrang. Die Environment-Datei bleibt außerhalb des Git-Checkouts;
`deploy/windows/mobilfunk.env.example` enthält kein echtes Secret.

Laufende Installation prüfen:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test-windows.ps1
```

Offen bleibt ein echter Windows-Hosttest mit Excel-Importen, LibreOffice-Export,
Datei-Locking, Umlauten und langen Pfaden. HTTPS, Firewallregel und ein
Dienstmodell sind bewusst nicht enthalten.

## Persistente Daten und Secrets

Der Git-Checkout ist ausschließlich Anwendungscode. Folgende Inhalte gehören
nicht hinein:

- `mobilfunk.db` einschließlich WAL-/SHM-Dateien
- `mobilfunk.env` und `MOBILFUNK_SECRET`
- Dokumente, Vorlagen, Upload-/Importdaten
- Logs und Backups

Unter Linux verbleiben sie in `/var/lib/mobilfunk`, unter Windows in
`%PROGRAMDATA%\Mobilfunkverwaltung`. Beide Orte müssen separat gesichert
werden. Die Linux-Environment-Datei soll `root:root` gehören und Modus `0600`
besitzen; systemd übergibt ihre Werte an den Dienstbenutzer `mobilfunk`. Unter
Windows erbt `mobilfunk.env.ps1` die Rechte des Datenordners und wird von
`start.ps1` in die Sitzung geladen.

## Git-Historie und Remotes

Das neue Hauptremote ist:

```text
origin          https://github.com/grumel/mobilfunkverwaltung.git
legacy-backend  https://github.com/grumel/mdwWeb.git
legacy-frontend https://github.com/grumel/mdw-frontend.git
```

Die Legacy-Remotes dienen nur als Referenz. Entwicklung und Releases erfolgen
aus dem Monorepository. Details zu Importcommits, Pfadänderungen und manueller
Produktionsumstellung stehen in [docs/MIGRATION.md](docs/MIGRATION.md).

## Dokumentation

- [Monorepo-Migration](docs/MIGRATION.md)
- [Produktionsmigration](docs/PRODUCTION_MIGRATION.md)
- [Cleanup-Kandidaten](docs/CLEANUP.md)
- [Linux-Deployment](deploy/linux/INSTALL.md)
- [Optionale PostgreSQL-Migration](deploy/linux/POSTGRES.md)
- [Plattformanalyse](deploy/PLATFORM_ANALYSIS.md)
- [Windows-Runtime](docs/WINDOWS.md)
- [Windows-Deployment](deploy/windows/README.md)
- [Technische Schulden und Testprioritäten](docs/TECH_DEBT.md)
- [Architektur](docs/ARCHITECTURE.md)
- [Sicherheit](docs/SECURITY.md)
- [Performance](docs/PERFORMANCE.md)
- [Teststrategie](docs/TESTING.md)
- [Roadmap](docs/ROADMAP.md)
- [Produktionsbericht](docs/PRODUCTION_DEPLOYMENT_REPORT.md)
- [Migrationsprotokoll der Produktion](docs/PRODUCTION_MIGRATION_LOG.md)
- [Bericht zur technischen Konsolidierung](docs/TECHNICAL_CONSOLIDATION_REPORT.md)

## Roadmap

1. **Phase 2 – technische Konsolidierung:** technische Schulden dokumentieren,
   Testlücken priorisieren, Sicherheits- und Pfadprüfungen verbessern, ohne
   Verhalten zu ändern.
2. **Phase 3 – Regressionstests:** temporäre SQLite-Fixtures für Authentifizierung,
   Rollen, CRUD, Importe, Uploads, Dokumente und Exporte ergänzen.
3. **Phase 4 – sichere interne Refactorings:** erst nach grünen Regressionstests
   kleine Extraktionen durchführen und jeden Schritt separat deployen.
4. **Windows-Runtime:** implementiert und in CI geprüft; offen bleibt die
   Abnahme auf einem echten Windows-Host.
5. **Später:** PostgreSQL als optionaler Skalierungspfad.

## Bekannte offene Punkte

- `feature/windows-runtime` per Pull Request nach `main` übernehmen.
- Windows-Abnahme auf einem echten Host: Excel-Import, LibreOffice-Export,
  Datei-Locking, Umlaute und lange Pfade.
- Dediziertes Testkonto für den authentifizierten Smoke-Test bereitstellen.
- Native Deploymenttests auf einem Linux-Testhost ergänzen.
- Die priorisierten Testlücken aus [docs/TECH_DEBT.md](docs/TECH_DEBT.md)
  schließen, bevor produktionsnahe interne Module verschoben werden.
- `backend-regression-tests.py` und `frontend-regression-check.mjs` laufen
  bisher nur im Windows-Workflow; sie gehören auch in `backend.yml` und
  `frontend.yml`.
- Optionale PostgreSQL-Nutzung in einem eigenen Arbeitsschritt bewerten.

