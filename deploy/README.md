# Build und Deployment

Dieses Verzeichnis trennt ausschließlich die Betriebs- und Installationsdateien
nach Zielplattform. Anwendungscode, API und Datenmodell sind davon unabhängig.
Die plattformneutralen Basispfade stellt `platform_support/` bereit; der
gemeinsame lokale Einstiegspunkt ist `run.py`.

## Struktur

```text
deploy/
├── linux/      produktionsreifes Debian-/Ubuntu-Deployment
└── windows/    dokumentierter Platzhalter für ein künftiges Windows-Deployment
```

## Gemeinsamer Build

Backend und Frontend bleiben zwei getrennte Repositories.

Backend-Abhängigkeiten werden in einer plattformeigenen virtuellen Umgebung
installiert:

```text
python -m venv .venv
python -m pip install -r requirements.txt
```

Für den Serverbetrieb kommen die Abhängigkeiten aus
`requirements-server.txt` hinzu. Das React-Frontend wird in seinem eigenen
Repository gebaut:

```text
npm ci
npm run build
```

Virtuelle Umgebungen, `node_modules` und fertige Builds werden nicht zwischen
Linux und Windows kopiert, sondern auf der jeweiligen Zielplattform neu erstellt.

Für einen lokalen Funktionscheck ohne plattformspezifischen Dienst:

```text
python run.py
```

Der Linux-Produktivstart bleibt davon unberührt und verwendet weiterhin
`gunicorn --chdir /opt/mobilfunk-web ... "webapp:create_app()"`.

## Plattformen

- [Linux-Installation](linux/INSTALL.md) – vollständig unterstützt und weiterhin
  der produktive Standard.
- [Windows-Deployment](windows/README.md) – `install.ps1`, `start.ps1` und
  `waitress.conf` sind als klar markierte, nicht produktive Platzhalter vorhanden.
