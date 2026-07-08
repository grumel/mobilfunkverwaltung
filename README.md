# Mobilfunkverwaltung – Web

Web-Version der Mobilfunkverwaltung (Flask). Eigenständiges Programm, getrennt
von der Desktop-App **und** von der Datenbank.

## Start (Windows)

Doppelklick auf **`run_webapp.bat`** → der Browser öffnet <http://127.0.0.1:5001>.
Anmeldung mit denselben Benutzern/Passwörtern wie in der Desktop-App.

## Einmalige Einrichtung

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

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
run_webapp.py    Startpunkt (Flask-Entwicklungsserver)
run_webapp.bat   Doppelklick-Starter (setzt DB-Standardpfad + venv)
requirements.txt Abhängigkeiten
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
