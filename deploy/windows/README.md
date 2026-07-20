# Windows-Deployment (Vorbereitung)

Dieses Verzeichnis reserviert die Windows-spezifische Deployment-Struktur.
Ein produktionsreifer Windows-Dienst-Installer ist noch nicht implementiert.
Für lokale Entwicklung bleibt der vorhandene Start über `run_webapp.bat`
unverändert.

## Vorgesehene Artefakte

- `install.ps1` – idempotente Einrichtung von Python, Backend, Frontend-Build,
  Datenverzeichnis und Dienst
- `start.ps1` – kontrollierter Start des produktiven WSGI-Servers
- `waitress.conf` – Parameter für den vorgesehenen Windows-WSGI-Server
- `mobilfunk-web.xml` oder eine entsprechende Dienstdefinition für WinSW/NSSM
- `Caddyfile` – Reverse-Proxy und Auslieferung des React-Bundles unter Windows
- `INSTALL.md` – Installation, Update, Backup, Diagnose und Deinstallation

`install.ps1` und `start.ps1` brechen derzeit absichtlich mit einer eindeutigen
Fehlermeldung ab; `waitress.conf` enthält nur Kommentare. Vor einer Umsetzung
müssen insbesondere Dienstkonto,
Verzeichnisrechte, Secret-Verwaltung, Firewall, Backup und Update-Rollback
festgelegt und getestet werden.

## Aktueller lokaler Start

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
run_webapp.bat
```

Alternativ steht mit `python run.py` der gemeinsame lokale Einstiegspunkt für
Linux und Windows bereit.

Dies startet den Flask-Entwicklungsserver und ist kein Produktionsdeployment.
Das React-Frontend wird für die Entwicklung weiterhin separat im Frontend-Repo
mit `npm run dev` gestartet.
