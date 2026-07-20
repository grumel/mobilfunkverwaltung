# Windows-Webbetrieb mit Waitress und Caddy

Die Anwendung läuft unter Windows als Webanwendung im Browser. Waitress hostet
Flask ausschließlich auf `127.0.0.1:8000`; Caddy liefert das gebaute
React-Frontend auf Port 80 aus und leitet `/api/*` an Waitress weiter.

```text
Browser -> Caddy :80 -> /api/* -> Waitress :8000 -> Flask -> SQLite
                    -> /*      -> React dist/
```

Dies ist keine Desktop-Version, kein Windows-Dienst und kein EXE-Installer.
`install.ps1` ist ein wiederholbares Setup-Skript für bereits installierte
Werkzeuge.

## Voraussetzungen

- Windows 10 oder 11 beziehungsweise Windows Server
- Python 3.12 oder neuer im `PATH`
- Node.js LTS einschließlich npm im `PATH`
- Caddy für Windows (`caddy.exe`) im `PATH`
- LibreOffice für die bestehende PDF-Erzeugung; der Standardpfad unter
  `%ProgramFiles%\LibreOffice\program` wird automatisch übernommen
- Backend- und Frontend-Repository in getrennten Verzeichnissen

Waitress wird vom Setup-Skript als Python-Abhängigkeit installiert.

## Verzeichnisbeispiel

```text
C:\Mobilfunkverwaltung\
├── mdwWeb\
└── mdw-frontend\
```

Bei einer anderen Struktur werden `-BackendDir` und `-FrontendDir` angegeben.

## Einrichten

PowerShell **als Administrator** öffnen und aus dem Backend-Repository ausführen:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1 `
  -FrontendDir C:\Mobilfunkverwaltung\mdw-frontend
```

Das Skript:

1. prüft Python, Node, npm, Caddy und LibreOffice,
2. erstellt beziehungsweise aktiviert `.venv`,
3. installiert Backend-Abhängigkeiten einschließlich Waitress,
4. führt im Frontend `npm ci` und `npm run build` aus,
5. erstellt unter `%ProgramData%\Mobilfunkverwaltung` Daten- und Logverzeichnis,
6. erzeugt einmalig ein persistentes Session-Secret.

Eine vorhandene `mobilfunk.db` kann vor dem ersten Start nach
`%ProgramData%\Mobilfunkverwaltung\mobilfunk.db` kopiert werden. Das Setup selbst
verändert keine Datenbank und legt kein Schema um.

## Starten

Auch zum Starten ist wegen Caddys Port 80 eine PowerShell als Administrator
erforderlich.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1 `
  -FrontendDir C:\Mobilfunkverwaltung\mdw-frontend
```

Oder per Doppelklick beziehungsweise Eingabeaufforderung:

```bat
deploy\windows\start.bat -FrontendDir C:\Mobilfunkverwaltung\mdw-frontend
```

Danach ist die Anwendung unter <http://localhost/> erreichbar. Beim Beenden von
Caddy wird auch der von `start.ps1` gestartete Waitress-Prozess beendet.

## Konfiguration und Logs

- Waitress: `deploy/windows/waitress.conf`
- Caddy: `deploy/windows/Caddyfile`
- Laufzeitumgebung: `%ProgramData%\Mobilfunkverwaltung\mobilfunk.env.ps1`
- SQLite und Dokumente: `%ProgramData%\Mobilfunkverwaltung`
- Backend-Log: `%ProgramData%\Mobilfunkverwaltung\logs\mobilfunk-web.log`

Die Pfade werden mit `Join-Path` beziehungsweise Python-`pathlib` gebildet.
Caddy erhält den absoluten Frontendpfad über `MOBILFUNK_FRONTEND_DIST`.

## Updates

Nach dem Aktualisieren beider Repositories `install.ps1` erneut ausführen. Es
installiert die aktuellen Abhängigkeiten und baut das Frontend reproduzierbar
neu. Danach `start.ps1` erneut starten.

## Noch nicht enthalten

- Installation von Python, Node oder Caddy
- Registrierung als Windows-Dienst
- automatische Firewall-Regel
- EXE- oder Desktop-Paket
- automatische Backups oder Update-Rollbacks
