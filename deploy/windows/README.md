# Windows-Deployment

Die aktuelle Windows-Runtime ist eine lokale Webanwendung mit Waitress und
integrierter React-SPA-Auslieferung. Sie benötigt keinen Caddy-Prozess, keine
Administratorrechte, keinen Windows-Dienst und kein EXE-/WebView2-Paket.

Die vollständige Anleitung steht in [`docs/WINDOWS.md`](../../docs/WINDOWS.md).

Wichtige Dateien:

- `common.ps1` – gemeinsame Hilfsfunktionen (u. a. Python-Pfad auflösen:
  bevorzugt mitgeliefertes `backend\python-embed`, sonst `.venv`)
- `bootstrap.ps1` – prüft Python, Node, Git, Word und Outlook, installiert
  Fehlendes per winget und startet danach `install.ps1`; ist ein
  Python-Bundle vorhanden, entfällt die Python-Pflicht
- `install.ps1` – Datenordner und Secret; legt Venv/Abhängigkeiten bzw.
  Frontend-Build nur an, wenn kein fertiges Bundle mitgeliefert wurde
- `start.ps1` – lokaler Waitress-/SPA-Start auf `127.0.0.1:8000`
- `start-dev.ps1` – Installieren, Bauen und Starten für Entwicklung
- `stop.ps1`, `update.ps1`, `backup.ps1`
- `uninstall.ps1` – entfernt nur Venv/Python-Bundle, Build und Caches; Daten
  bleiben erhalten
- `mobilfunk.env.example` – secretfreie Konfigurationsvorlage

Das Release-ZIP (`scripts/publish-windows-zip.sh`, Root des Repos) packt
zusätzlich ein vorinstalliertes Python-Bundle nach `backend\python-embed` –
auf dem Zielrechner ist dann nur noch Windows selbst nötig, kein Python.
