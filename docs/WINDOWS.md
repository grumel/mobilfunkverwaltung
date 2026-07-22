# Windows-Runtime

## Status

Die Windows-Unterstützung ist eine lokale Webanwendung, kein EXE-Paket, kein
WebView2 und kein Windows-Dienst. Waitress liefert Flask und das gebaute React-
Frontend auf demselben lokalen Port aus. Linux verwendet weiterhin Gunicorn,
Caddy und die unveränderten Linux-Pfade.

## Voraussetzungen und Start

- Windows 10/11 oder Windows Server 2019+
- Python 3.12+, Node.js 20 LTS, npm, Git und PowerShell 5.1+
- LibreOffice nur für den bestehenden PDF-Export

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1
```

Standard ist <http://127.0.0.1:8000/>. Mit `-OpenBrowser` wird der Browser
geöffnet. Für Entwicklung: `deploy\windows\start-dev.ps1 -OpenBrowser`.

## Daten und Konfiguration

Standarddatenpfad: `%PROGRAMDATA%\Mobilfunkverwaltung`, Fallback
`%LOCALAPPDATA%\Mobilfunkverwaltung`. Enthalten sind `mobilfunk.db`,
`Dokumente`, `Kuendigungen`, `SynoDateien`, `logs` und `backups`. Ein explizites
`MOBILFUNK_DATA_DIR` hat Vorrang. Secrets liegen in `mobilfunk.env.ps1`,
außerhalb des Git-Checkouts. `mobilfunk.env.example` enthält kein echtes
Secret.

## Backup, Update und Stop

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\backup.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\windows\update.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\windows\stop.ps1
```

Backups werden datiert unter `backups\YYYY-MM-DD_HH-mm-ss` angelegt und
enthalten SQLite, Datenverzeichnisse, Logs und Environment-Datei. Vor einem
produktiven Backup sollte zusätzlich `sqlite3.Connection.backup()` eingeplant
werden.

## Smoke-Test und Sicherheit

`scripts\smoke-test-windows.ps1` prüft Python, `/api/version`, HTML-SPA-
Fallback und ein JavaScript-Asset. Waitress bindet standardmäßig nur an
`127.0.0.1`; Debug und Browser-Autostart sind deaktiviert. Der WSGI-Wrapper
trennt `/api/*` von statischen Dateien und verhindert Pfade außerhalb des
Frontend-Roots. Logs liegen unter `%PROGRAMDATA%\Mobilfunkverwaltung\logs`.

## Einschränkungen und Deinstallation

Es gibt keinen Windows-Dienst, keine Firewallregel, kein HTTPS, keine EXE und
kein WebView2. Ein echter Windows-Hosttest einschließlich Excel, LibreOffice,
Datei-Locking, Umlauten und langen Pfaden bleibt erforderlich.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\uninstall.ps1
```

`uninstall.ps1` beendet eine laufende Instanz und entfernt danach ausschließlich
erzeugte Laufzeitartefakte innerhalb des Checkouts: `backend\.venv`,
`frontend\dist`, `frontend\node_modules` und die `__pycache__`-Verzeichnisse.
Vor dem Löschen wird die Liste angezeigt und rückgefragt; `-Force` überspringt
nur die Rückfrage, `-WhatIf` zeigt den Ablauf ohne Änderung. Das
Datenverzeichnis mit Datenbank, Dokumenten, Logs und Secret wird nie angefasst,
sondern nur zur Kontrolle ausgegeben — vorher `backup.ps1` ausführen und die
Sicherung prüfen. Den Checkout selbst löschst du anschließend von Hand; da
weder Dienst noch Registry-Einträge oder Verknüpfungen angelegt wurden, bleibt
sonst nichts im System zurück.
