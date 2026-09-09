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
  `auth, participants, tabs, imports, tasks, reports, settings, api`.
- **Zwei Frontends, ein Backend:** die klassische Jinja-Oberfläche (Server-gerendert,
  `webapp/templates/`) läuft **parallel** zur neuen **JSON-API** (`webapp/blueprints/api.py`,
  Präfix `/api`, Session-Auth, CSRF-exempt). Das eigentliche Frontend ist inzwischen
  **React** und liegt in **diesem Monorepo** unter `frontend/` (Vite), spricht nur
  die API an. Die Jinja-UI existiert noch, ist im Produktiv-Deployment aber nicht
  mehr über Port 80 eingebunden (siehe „Starten" unten).
- **SQLAlchemy** (DB-neutral): SQLite jetzt, **PostgreSQL-fähig** (echt gegen
  lokales Postgres 17 verifiziert, nicht nur theoretisch). Modelle in
  `webapp/models.py` passend zum bestehenden Schema.
- **`modules/`** ist eine **Kopie** der gemeinsamen Logik aus der Desktop-App
  (DB-Zugriff, Vodafone-/Syno-Import, Passwort-Hashing, `paths.py`). Web-UI und API
  nutzen daraus nur die GUI-freien Teile. Die Import-Funktionen
  `modules.vodafone_import.run_vodafone_import` / `modules.syno_import.run_syno_import`
  akzeptieren einen optionalen `db_module`-Parameter (Dependency Injection):
  Standard = unverändert `modules.database` (sqlite3). `webapp/import_adapter.py`
  ist ein SQLAlchemy-Backend mit derselben Funktionsoberfläche; die API
  (`_import_db_module()` in `api.py`) wählt ihn automatisch, sobald
  `DATABASE_URL` nicht mit `sqlite` beginnt. Dieselbe Import-Logik läuft also
  unverändert auf beiden Backends — kein Duplicated Code.
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
- **Plattformneutral:** `python run.py` → http://127.0.0.1:5001.
  Unter Windows startet Waitress, unter Linux bleibt dies der lokale
  Entwicklungsstart. `run_webapp.py` bleibt als kompatibler Alias erhalten.
- **Windows/lokal, Backend:** `run_webapp.bat` → http://127.0.0.1:5001 (Flask-Dev-Server).
- **Windows/lokal, Frontend:** im `frontend/`-Verzeichnis `npm run dev` → http://localhost:5173
  (Vite-Dev-Proxy leitet `/api` an Port 5001 weiter, dadurch same-origin/kein CORS).
- **Server (Linux, Port 80):** siehe `deploy/linux/INSTALL.md` bzw.
  `deploy/linux/install.sh`
  (idempotent, macht auch Updates). Topologie: **Caddy** auf Port 80 → `/api/*` zu
  **gunicorn** (127.0.0.1:8000), alles andere liefert Caddy als **statisches
  React-Bundle** (`frontend/dist`). Alles liegt im Monorepo unter
  `/opt/mobilfunkverwaltung`; schreibbare Daten getrennt unter `/var/lib/mobilfunk`.
  **Wichtig:** Kein fertiges Windows-Verzeichnis kopierbar — `.venv/` und
  `node_modules/` sind plattformgebunden; das Repo wird auf dem Server geklont und
  dort gebaut (macht der Installer automatisch). Die alte Jinja-UI bleibt im Backend
  erreichbar, aber nur direkt auf `127.0.0.1:8000` (nicht über Port 80 geroutet).

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
- Fertig (Backend, Jinja-UI): alle Provider-Tabs, Suche, Bearbeiten/Neu, Aktionen
  (verschieben/geprüft/löschen/kopieren/zu Aufgabe), Zusammenführen, Import
  (Vodafone mit Vorschau + Syno), Aufgaben, Statistik, Protokoll/Audit,
  Einstellungen (DB-Pfad), Härtung (Secret + CSRF).
- Fertig (React-Frontend, Phase 3 **vollständig**): Login, alle Provider-Tabs +
  abgeleitete Ansichten, Bearbeiten/Neu, Rechtsklick-Aktionen, Aufgaben,
  Statistik, Import, Einstellungen, Zusammenführen (Merge-Modus),
  Protokoll/Audit-Log — deckt alle Funktionen des Jinja-UI ab.
- Fertig: Linux-Deployment (Port 80, Backend **und** Frontend, `deploy/linux/install.sh`
  idempotent/Update-fähig).
- Fertig (Phase 2, **PostgreSQL**, optional/bei Bedarf aktivierbar): Import-Refactor
  (`db_module`-Parameter), `webapp/import_adapter.py`,
  `deploy/linux/migrate_to_postgres.py`, `deploy/linux/POSTGRES.md`. **Echt verifiziert**
  (nicht nur mit SQLite simuliert): lokales PostgreSQL 17 installiert, Migration
  einer DB-Kopie (353 Teilnehmer, 5616 Logs – exakt übertragen), Web-App komplett
  gegen Postgres getestet, **echter Vodafone-Import direkt gegen Postgres**
  (328 aktualisiert, per SQL gegengeprüft). SQLite-Pfad dabei unverändert
  (Regressionstest: identisches Ergebnis wie vorher).
- Stand: Die Anwendung läuft **produktiv unter Linux**. Offen (Details siehe
  Haupt-`README.md` und **ROADMAP.md**): HTTPS im LAN, Abnahme der Windows-Runtime
  auf einem echten Host, PostgreSQL für den Mehrbenutzerbetrieb in Betrieb nehmen
  (Treiber aktiv, Migration und Verifikation vorhanden und getestet – siehe
  `deploy/POSTGRES_SHARED.md`), alte Jinja-Templates irgendwann entfernen.
- Repo auf GitHub: **github.com/grumel/mobilfunkverwaltung** (Monorepo mit
  `backend/` und `frontend/`, Remote `origin`, Branch `main`). Die getrennten
  Legacy-Repos **mdwWeb** (Backend) und **mdw-frontend** (React) dienen nur noch
  als Referenz; Entwicklung und Releases laufen ausschließlich aus dem Monorepo.
