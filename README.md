# Mobilfunkverwaltung – Web

Web-Version der Mobilfunkverwaltung (Flask). Eigenständiges Programm, getrennt
von der Desktop-App **und** von der Datenbank.

## Start (Windows)

Doppelklick auf **`run_webapp.bat`** → der Browser öffnet <http://127.0.0.1:5001>.
Anmeldung mit denselben Benutzern/Passwörtern wie in der Desktop-App.
Der gemeinsame lokale Einstiegspunkt ist außerdem `python run.py` und kann auf
Linux und Windows verwendet werden. `run_webapp.py` bleibt als kompatibler
Alias bestehen.

## Einmalige Einrichtung

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Build und Deployment

Plattformspezifische Installationsdateien liegen getrennt unter `deploy/`:

- **Linux:** produktionsreifer Installer, systemd-Dienst und Caddy-Konfiguration
  unter [`deploy/linux`](deploy/linux/INSTALL.md)
- **Windows:** dokumentierter Vorbereitungsstand unter
  [`deploy/windows`](deploy/windows/README.md); noch kein produktionsreifer
  Windows-Dienst-Installer

Die gemeinsamen Build-Schritte und die Abgrenzung der Plattformen beschreibt
[`deploy/README.md`](deploy/README.md). Das bestehende Linux-Deployment bleibt
unverändert nutzbar; lediglich der Installer-Pfad lautet jetzt
`deploy/linux/install.sh`.

### Gemeinsame Architektur

- `webapp/` enthält Flask-App, REST-API und servergerenderte Fallback-Oberfläche.
- `modules/` enthält die gemeinsam genutzte Fach- und Importlogik.
- `platform_support/` kapselt Betriebssystemerkennung und Basispfade.
- `run.py` ist der gemeinsame lokale Einstiegspunkt.
- `deploy/linux/` enthält das unveränderte produktive Linux-Betriebsmodell mit
  gunicorn, systemd und Caddy.
- `deploy/windows/` reserviert die künftigen PowerShell-, Waitress- und
  Dienstkonfigurationen. Diese Dateien sind noch nicht produktionsbereit.

Eine vollständige Liste der gefundenen Plattformbindungen und bewusst nicht
bereinigten Duplikate steht in
[`deploy/PLATFORM_ANALYSIS.md`](deploy/PLATFORM_ANALYSIS.md).

## Datenbank (Programm und DB getrennt)

Der Datenbank-Pfad wird in dieser Reihenfolge bestimmt:

1. Umgebungsvariable `DATABASE_URL`
2. **Einstellungen**-Seite in der App (gespeichert in
   `%LOCALAPPDATA%\MobilfunkWeb\webconfig.json`)
3. Standard: `mobilfunk.db` in `MOBILFUNK_DATA_DIR` (in `run_webapp.bat` gesetzt)

In der App unter **⚙ Einstellungen** (nur Admin) änderbar. Zum Verschieben der
Datenbank: Datei kopieren, dort den neuen Pfad eintragen, neu starten. Für
PostgreSQL eine vollständige `DATABASE_URL` hinterlegen (SQLAlchemy-fähig).

## Struktur

```
webapp/          Flask-App (Blueprints, Templates, static, Konfig)
modules/         gemeinsame Datenbank-/Import-/Hilfslogik
platform_support/ zentrale Betriebssystem- und Basispfadauflösung
run.py           gemeinsamer lokaler Startpunkt
run_webapp.py    kompatibler Alias für den bisherigen Startpunkt
run_webapp.bat   Windows-Doppelklick-Starter (setzt DB-Standardpfad + venv)
requirements.txt Abhängigkeiten
deploy/          Build- und Deployment-Dateien, nach Plattform getrennt
```

## Funktionen

Register (Vodafone/Telekom/O2/Ohne SIM/Frei), Suche, Bearbeiten, Rechtsklick-Aktionen
(verschieben/geprüft/löschen/kopieren/zu Aufgabe), Zusammenführen, Import (Vodafone
mit Vorschau, Syno), Aufgaben, Statistik, Protokoll/Audit, Einstellungen –
rollenbasiert (Lesen/Schreiben/Admin).

## Technologie

Python 3.12 · Flask · SQLAlchemy · SQLite (PostgreSQL-fähig) · openpyxl

> Hinweis: Der eingebaute Flask-Server ist für lokalen Betrieb/Test gedacht. Für
> einen echten Server-Betrieb einen produktiven WSGI-Server + Reverse-Proxy und
> CSRF-Schutz/`MOBILFUNK_SECRET` ergänzen.
