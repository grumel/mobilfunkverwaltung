# Projektkontext für Claude (Mobilfunkverwaltung – Web)

Diese Datei fasst zusammen, was eine neue Sitzung wissen sollte. Sprache: Deutsch.

## Was & Warum
Web-Version der **Mobilfunkverwaltung** (Flask). Ausgelagert aus der Desktop-App
(Tkinter, liegt separat unter `MobilDatenVerwaltung`) in dieses **eigene Repo**.
Grund: Auf den Firmen-PCs (ALPLA) blockiert eine **SRP/Gruppenrichtlinie**
unsignierte EXE/`python.exe`. Eine Web-App umgeht das komplett — im Browser wird
nichts installiert. Es sind **personenbezogene Daten** (Namen, Rufnummern) →
**intern** hosten (DSGVO), nicht in der Cloud.

## Architektur
- **Flask App-Factory** in `webapp/__init__.py` (`create_app()`), Blueprints:
  `auth, participants, tabs, imports, tasks, reports, settings`.
- **SQLAlchemy** (DB-neutral): SQLite jetzt, **PostgreSQL-fähig**. Modelle in
  `webapp/models.py` passend zum bestehenden Schema.
- **`modules/`** ist eine **Kopie** der gemeinsamen Logik aus der Desktop-App
  (DB-Zugriff, Vodafone-/Syno-Import, Passwort-Hashing, `paths.py`). Die Web-App
  nutzt daraus nur die GUI-freien Teile; die Import-Blueprints rufen
  `modules.vodafone_import` / `modules.syno_import` direkt auf (schreiben noch via
  sqlite3 über `modules/database.py`).
- **Rollen** (`webapp/security.py`): `read` < `write` < `admin`. Login-Benutzer =
  dieselben wie in der Desktop-App (users-Tabelle, alle 4 sind Admin).

## Datenbank ist vom Programm getrennt
`webapp/config.py` bestimmt die DB in dieser Reihenfolge:
1. Umgebungsvariable `DATABASE_URL`
2. Web-Konfig `webconfig.json` (Ort: `MOBILFUNK_WEBCONFIG_DIR`, sonst
   `%LOCALAPPDATA%\MobilfunkWeb` bzw. `~/MobilfunkWeb`) – gesetzt über **⚙ Einstellungen**
3. Default: `mobilfunk.db` in `MOBILFUNK_DATA_DIR` (in `run_webapp.bat` / systemd gesetzt)

Session-Secret: `MOBILFUNK_SECRET` oder persistenter Zufallswert
(`webconfig.get_or_create_secret()` → `secret.key` neben der Konfig).

## Starten
- **Windows/lokal:** `run_webapp.bat` → http://127.0.0.1:5001 (Flask-Dev-Server).
- **Server (Linux, Port 80):** siehe `deploy/INSTALL.md` — Caddy (Port 80) →
  gunicorn (127.0.0.1:8000) → App, als **systemd**-Dienst. `deploy/` enthält
  `mobilfunk-web.service`, `Caddyfile`, `INSTALL.md`.

## Sicherheit / Härtung
- **CSRF-Schutz** aktiv (Flask-WTF) für alle POST-Formulare und JS-Aktionen;
  per `MOBILFUNK_CSRF=0` abschaltbar (nur für Tests).
- Über Netzwerk sind **HTTPS** (Caddy, ein DNS-Name im Caddyfile) und ein echtes
  `MOBILFUNK_SECRET` Pflicht.

## Tests (Muster)
Immer gegen eine **Kopie** der echten DB, nie gegen das Original:
`sqlite3 backup` in ein Temp-Verzeichnis, dann `MOBILFUNK_DATA_DIR` +
`MOBILFUNK_WEBCONFIG_DIR` auf Temp setzen, `MOBILFUNK_CSRF=0`, und die App per
`create_app().test_client()` ansprechen (Session per `session_transaction`).

## Konventionen
- Sprache Deutsch (UI, Kommentare, Commits).
- Commits: `feat:` / `fix:` / `chore:`, am Ende `Co-Authored-By`-Trailer.

## Stand & offene Punkte
- Fertig: alle Provider-Tabs, Suche, Bearbeiten/Neu, Aktionen (verschieben/
  geprüft/löschen/kopieren/zu Aufgabe), Zusammenführen, Import (Vodafone mit
  Vorschau + Syno), Aufgaben, Statistik, Protokoll/Audit, Einstellungen (DB-Pfad),
  Härtung (Secret + CSRF), Linux-Deployment (Port 80).
- Offen: **HTTPS** produktiv, **PostgreSQL** (Phase 4; Import-Module dafür von
  sqlite3 auf SQLAlchemy umstellen), Remote/GitHub, ThinkPad-Server aufsetzen.
