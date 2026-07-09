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
  **React** — eigenes Repo **github.com/grumel/mdw-frontend** (Vite), spricht nur die
  API an. Die Jinja-UI existiert noch, ist im Produktiv-Deployment aber nicht mehr
  über Port 80 eingebunden (siehe „Starten" unten).
- **SQLAlchemy** (DB-neutral): SQLite jetzt, **PostgreSQL-fähig**. Modelle in
  `webapp/models.py` passend zum bestehenden Schema.
- **`modules/`** ist eine **Kopie** der gemeinsamen Logik aus der Desktop-App
  (DB-Zugriff, Vodafone-/Syno-Import, Passwort-Hashing, `paths.py`). Web-UI und API
  nutzen daraus nur die GUI-freien Teile; die Import-Endpunkte rufen
  `modules.vodafone_import` / `modules.syno_import` direkt auf (schreiben noch via
  sqlite3 über `modules/database.py` — das ist der Haken für Phase 2/PostgreSQL).
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
- **Windows/lokal, Backend:** `run_webapp.bat` → http://127.0.0.1:5001 (Flask-Dev-Server).
- **Windows/lokal, Frontend:** im `mdw-frontend`-Repo `npm run dev` → http://localhost:5173
  (Vite-Dev-Proxy leitet `/api` an Port 5001 weiter, dadurch same-origin/kein CORS).
- **Server (Linux, Port 80):** siehe `deploy/INSTALL.md` bzw. `deploy/install.sh`
  (idempotent, macht auch Updates). Topologie: **Caddy** auf Port 80 → `/api/*` zu
  **gunicorn** (127.0.0.1:8000, Backend-Repo `/opt/mobilfunk-web`), alles andere
  liefert Caddy als **statisches React-Bundle** (`/opt/mobilfunk-frontend/dist`,
  gebaut aus dem Frontend-Repo). **Wichtig:** Kein fertiges Windows-Verzeichnis
  kopierbar — `.venv/` und `node_modules/` sind plattformgebunden; beide Repos
  werden auf dem Server geklont und dort gebaut (macht der Installer automatisch).
  Die alte Jinja-UI bleibt im Backend erreichbar, aber nur direkt auf
  `127.0.0.1:8000` (nicht über Port 80 geroutet).

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
- Fertig (React-Frontend, Phase 3 inhaltlich abgeschlossen): Login, alle
  Provider-Tabs + abgeleitete Ansichten, Bearbeiten/Neu, Rechtsklick-Aktionen,
  Aufgaben, Statistik, Import, Einstellungen. **Fehlt in React noch:**
  Zusammenführen (Merge-Modus), Protokoll/Audit-Log-Ansicht.
- Fertig: Linux-Deployment (Port 80, Backend **und** Frontend, `deploy/install.sh`
  idempotent/Update-fähig).
- Offen (Details siehe **ROADMAP.md**): ThinkPad-Server aufsetzen (Phase 1),
  Datenbank-Umbau **SQLite → PostgreSQL** inkl. **Import-Refactor** von sqlite3 auf
  SQLAlchemy (Phase 2), HTTPS, restliche React-Lücken (Merge, Protokoll/Audit),
  alte Jinja-Templates irgendwann entfernen.
- Repos auf GitHub: **github.com/grumel/mdwWeb** (Backend, Remote `origin`,
  Branch `main`) und **github.com/grumel/mdw-frontend** (React-Frontend, eigenes
  Repo, eigene `CLAUDE.md`/README empfehlenswert dort). Desktop-App separat:
  github.com/grumel/mobilfunkverwaltung.
