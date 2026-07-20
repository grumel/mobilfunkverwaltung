# Build und Deployment

Dieses Verzeichnis trennt ausschließlich die Betriebs- und Installationsdateien
nach Zielplattform. Anwendungscode, API und Datenmodell sind davon unabhängig.
Die plattformneutralen Basispfade stellt `platform_support/` bereit; der
gemeinsame lokale Einstiegspunkt ist `run.py`.

## Struktur

```text
deploy/
├── linux/      produktionsreifes Debian-/Ubuntu-Deployment
└── windows/    erster Windows-Webbetrieb mit Waitress und Caddy
```

## Gemeinsamer Build

Backend und Frontend liegen gemeinsam im Monorepository, behalten aber getrennte
Build-Umgebungen.

Backend-Abhängigkeiten werden in einer plattformeigenen virtuellen Umgebung
installiert:

```text
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

Für den Serverbetrieb kommen die Abhängigkeiten aus
`requirements-server.txt` hinzu. Das React-Frontend wird in seinem eigenen
Repository gebaut:

```text
cd frontend
npm ci
npm run build
```

Virtuelle Umgebungen, `node_modules` und fertige Builds werden nicht zwischen
Linux und Windows kopiert, sondern auf der jeweiligen Zielplattform neu erstellt.

Für einen lokalen Funktionscheck ohne plattformspezifischen Dienst:

```text
cd backend
python run.py
```

Der Linux-Produktivstart bleibt davon unberührt und verwendet weiterhin
`gunicorn --chdir /opt/mobilfunkverwaltung/backend ... "webapp:create_app()"`.

## Plattformen

- [Linux-Installation](linux/INSTALL.md) – vollständig unterstützt und weiterhin
  der produktive Standard.
- [Windows-Deployment](windows/README.md) – Setup und Start des Webbetriebs mit
  Waitress, Caddy und dem bestehenden React-Build.
