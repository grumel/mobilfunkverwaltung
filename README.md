# Mobilfunkverwaltung

[![Backend](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/backend.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/backend.yml)
[![Frontend](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/frontend.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/frontend.yml)
[![Monorepo structure](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/monorepo.yml/badge.svg?branch=main)](https://github.com/grumel/mobilfunkverwaltung/actions/workflows/monorepo.yml)

Webbasierte Verwaltung von Mobilfunkteilnehmern, Verträgen, Importen,
Dokumenten und Aufgaben. Dieses Repository führt das bestehende Flask-Backend
und das React/Vite-Frontend in einer gemeinsamen, weiterhin klar getrennten
Codebasis zusammen.

## Status

Die Monorepo-Migration ist abgeschlossen:

- Backend-Historie bis `420fb1d` unter `backend/` übernommen.
- Frontend-Historie bis `ceaeaf4` unter `frontend/` übernommen.
- Beide Historien wurden ohne Squash über getrennte Subtree-Merge-Commits
  erhalten.
- Backendlogik, React-Oberfläche, REST-API und Datenbankschema wurden durch die
  Migration nicht verändert.
- Der Migrationsbranch ist `chore/monorepo-migration`; produktives `main` wird
  ausschließlich über einen geprüften Merge aktualisiert.
- Linux bleibt die produktive Zielplattform. Windows-Unterstützung ist später
  geplant; vorhandene frühe Dateien unter `deploy/windows/` werden in diesem
  Schritt weder erweitert noch als produktionsreif erklärt.

## Architektur

```text
Browser
   |
   v
Caddy :80
   |-- /*      -> frontend/dist (React/Vite)
   `-- /api/*  -> Gunicorn :8000 -> Flask -> SQLAlchemy -> SQLite
```

Im Linux-Produktivbetrieb ist Caddy der öffentliche Einstiegspunkt. Gunicorn
lauscht nur lokal. Schreibbare Daten liegen außerhalb des Git-Checkouts.

## Repository-Struktur

```text
mobilfunkverwaltung/
├── backend/                    Flask, SQLAlchemy und Fachlogik
│   ├── modules/                gemeinsame Import-/Dokument-/Datenlogik
│   ├── platform_support/       plattformneutrale Basispfade
│   ├── webapp/                 App-Factory, API, Modelle und Jinja-Fallback
│   ├── requirements.txt
│   ├── requirements-server.txt
│   └── run.py
├── frontend/                   React/Vite-Oberfläche
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── deploy/
│   ├── linux/                  Caddy, systemd, Installer und Betriebsdoku
│   └── windows/                übernommene frühe Vorbereitung, nicht erweitert
├── scripts/
│   ├── backend-ci-smoke.py     isolierter CI-Smoke-Test
│   ├── smoke-test-linux.sh     Produktions-Smoke-Test
│   └── rollback-linux.sh       nur Konfigurations-/Release-Rollback
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

## Lokale Entwicklung

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

Linux-Dateien prüfen:

```bash
find deploy/linux scripts -type f -name '*.sh' -exec bash -n {} \;
caddy validate --config deploy/linux/Caddyfile --adapter caddyfile
```

## Continuous Integration

Die Workflows laufen bei Pull Requests nach `main` sowie Pushes auf `main` und
`chore/monorepo-migration`:

- `backend.yml`: Python 3.12, pip-Cache, Abhängigkeiten, `compileall` und
  isolierter Flask/Login/API/SQLite-Smoke-Test.
- `frontend.yml`: Node.js 20, npm-Cache, `npm ci`, optionales `npm test` und
  Vite-Produktionsbuild.
- `monorepo.yml`: Pflichtstruktur, Syntax aller Linux-Shellskripte und
  Python-Kompilierung.

Alle Jobs besitzen nur lesenden Repository-Zugriff und geben keine Secrets aus.

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

## Persistente Daten und Secrets

Der Git-Checkout ist ausschließlich Anwendungscode. Folgende Inhalte gehören
nicht hinein:

- `mobilfunk.db` einschließlich WAL-/SHM-Dateien
- `mobilfunk.env` und `MOBILFUNK_SECRET`
- Dokumente, Vorlagen, Upload-/Importdaten
- Logs und Backups

Sie verbleiben unter `/var/lib/mobilfunk` und müssen separat gesichert werden.
Die Environment-Datei soll `root:root` gehören und Modus `0600` besitzen;
systemd übergibt ihre Werte an den Dienstbenutzer `mobilfunk`.

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

## Bekannte offene Punkte

- Migrationsbranch per Pull Request nach `main` übernehmen.
- Produktionsserver kontrolliert und mit geprüftem Rollback umstellen.
- Native Deploymenttests auf einem Linux-Testhost ergänzen.
- Windows-Betrieb erst in einem eigenen, späteren Arbeitsschritt bewerten und
  implementieren.
- Kandidaten aus [docs/CLEANUP.md](docs/CLEANUP.md) erst nach belastbaren
  Regressionstests bereinigen.
