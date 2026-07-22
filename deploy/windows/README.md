# Windows-Deployment

Die aktuelle Windows-Runtime ist eine lokale Webanwendung mit Waitress und
integrierter React-SPA-Auslieferung. Sie benötigt keinen Caddy-Prozess, keine
Administratorrechte, keinen Windows-Dienst und kein EXE-/WebView2-Paket.

Die vollständige Anleitung steht in [`docs/WINDOWS.md`](../../docs/WINDOWS.md).

Wichtige Dateien:

- `install.ps1` – Venv, Abhängigkeiten, Frontend-Build und Datenordner
- `start.ps1` – lokaler Waitress-/SPA-Start auf `127.0.0.1:8000`
- `start-dev.ps1` – Installieren, Bauen und Starten für Entwicklung
- `stop.ps1`, `update.ps1`, `backup.ps1`
- `uninstall.ps1` – entfernt nur Venv, Build und Caches; Daten bleiben
- `mobilfunk.env.example` – secretfreie Konfigurationsvorlage
