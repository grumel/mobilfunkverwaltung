# Mobilfunkverwaltung

Dieses Monorepository enthält die bestehende Mobilfunkverwaltung unverändert in
zwei klar getrennten Anwendungsteilen: Flask stellt REST-API und Datenzugriff
bereit, React/Vite bildet die Browseroberfläche. Caddy liefert das gebaute
Frontend aus und leitet `/api/*` an den WSGI-Server weiter.

```text
Browser -> Caddy -> frontend/dist
                 -> /api/* -> Gunicorn/Waitress -> Flask -> SQLite
```

## Repository-Struktur

```text
mobilfunkverwaltung/
├── backend/          Flask, SQLAlchemy, SQLite und Fachlogik
├── frontend/         React/Vite
├── deploy/
│   ├── linux/        Gunicorn, systemd, Caddy und Installation
│   └── windows/      vorhandene Windows-Laufzeitvorbereitung
├── scripts/          Platz für gemeinsame Automatisierung
├── docs/             übergreifende Dokumentation
├── .github/          Platz für gemeinsame GitHub-Workflows
├── README.md
└── .gitignore
```

Die vollständigen Historien der früheren Repositories `mdweb` und
`mdw-frontend` sind in der Git-Historie dieses Repositories enthalten. Details
zur Zusammenführung stehen in [docs/MIGRATION.md](docs/MIGRATION.md). Bewusst
nicht bereinigte Alt- und Parallelstrukturen sind in
[docs/CLEANUP.md](docs/CLEANUP.md) erfasst.

## Entwicklungsumgebung

Backend:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd backend
../backend/.venv/bin/python run.py
```

Frontend in einem zweiten Terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite läuft auf Port 5173 und leitet `/api` wie bisher an Flask auf Port 5001
weiter. Weitere Hinweise enthalten [backend/README.md](backend/README.md) und
[frontend/README.md](frontend/README.md).

## Produktions-Build

```bash
cd frontend
npm ci
npm run build
```

Das Ergebnis liegt in `frontend/dist/`. Backend-Abhängigkeiten für den
Serverbetrieb werden zusätzlich aus `backend/requirements-server.txt`
installiert.

## Linux-Deployment

Der produktive Linux-Betrieb bleibt bei Gunicorn, systemd und Caddy. Der
Standardpfad des Monorepositories ist `/opt/mobilfunkverwaltung`; persistente
Daten verbleiben unter `/var/lib/mobilfunk`.

```bash
sudo git clone <repository-url> /opt/mobilfunkverwaltung
sudo bash /opt/mobilfunkverwaltung/deploy/linux/install.sh
```

Die manuelle Anleitung und Update-Hinweise stehen in
[deploy/linux/INSTALL.md](deploy/linux/INSTALL.md). Windows-Unterlagen befinden
sich unter [deploy/windows](deploy/windows/README.md).

## Roadmap

- Gemeinsame CI für Backend-Tests und Frontend-Build ergänzen.
- Windows-Betrieb als Dienst und automatisierte Windows-Tests ergänzen.
- Deployment- und Release-Artefakte aus einem gemeinsamen Versionsstand bauen.
- Optionalen PostgreSQL-Betrieb weiter dokumentieren und automatisieren.

Die Migration selbst ändert weder Benutzeroberfläche noch Backendlogik,
REST-API oder Datenbankschema.
