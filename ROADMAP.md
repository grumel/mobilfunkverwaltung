# Roadmap

Geplante Ausbaustufen der Web-App. Tatsächliche Reihenfolge bisher: erst eine
laufende Lösung (Server/Deployment), dann das Frontend (React), dann die
Datenbank (PostgreSQL, Code + Migration fertig, gegen echtes Postgres
verifiziert). **Aktueller Fokus: Phase 1 abschließen** (ThinkPad produktiv
nehmen) — das ist der einzige noch offene Schritt vor dem Linux-Betrieb.

---

## Phase 1 — Server-Go-Live (aktuell)

Kleiner Linux-Rechner (Lenovo ThinkPad, Ubuntu/Debian Desktop genügt) im eigenen
Netz. Automatischer Installer `deploy/install.sh` richtet **beide** Repos ein:
Backend (gunicorn) + Frontend (React-Build) hinter Caddy (Port 80), systemd-Dienst,
Node.js, Backup-Cron, „Immer-an". Details: `deploy/INSTALL.md`.

Topologie: `Caddy :80` → `/api/*` zu gunicorn (Backend-JSON-API),
`/*` statisches React-Bundle (`mdw-frontend/dist`). Man kann kein fertiges
Windows-Verzeichnis kopieren (`.venv/`, `node_modules/` sind plattformgebunden) —
beide Repos werden auf dem Server geklont und dort gebaut; der Installer macht das.

- [x] Härtung: persistentes Secret + CSRF
- [x] Deployment-Paket + Installer (Port 80, Backend + Frontend)
- [ ] Server aufsetzen, DB `mobilfunk.db` übertragen, erster Lauf
- [ ] Danach optional **HTTPS** (im `Caddyfile` `:80` → DNS-Name; Caddy holt das Zertifikat)

Stabiler Zustand als Basis für Phase 2.

---

## Phase 2 — Datenbank-Umbau: SQLite → PostgreSQL ✅ (Code fertig, echt verifiziert)

**Ziel:** echte Mehrbenutzer-Gleichzeitigkeit, robustere Sperren/Backups, sauber
für den Netzwerkbetrieb. **Optional** — bei 2–3 Nutzern reicht SQLite weiterhin.

- [x] **Import-Refactor:** `modules/vodafone_import.py` / `modules/syno_import.py`
      bekamen einen injizierbaren `db_module`-Parameter (Dependency Injection).
      Standard (kein Parameter) = unverändertes SQLite-Verhalten — per Regressionstest
      bestätigt (328 aktualisiert, identisch zu vorher).
- [x] **`webapp/import_adapter.py`** — SQLAlchemy-Adapter mit derselben
      Funktionsoberfläche wie `modules/database.py`. Die API
      (`webapp/blueprints/api.py`, `_import_db_module()`) wählt ihn automatisch,
      sobald `DATABASE_URL` nicht mit `sqlite` beginnt.
- [x] **`deploy/migrate_to_postgres.py`** — Migrationsskript, Sequenzen werden
      korrekt gesetzt.
- [x] **`deploy/POSTGRES.md`** — Schritt-für-Schritt-Anleitung (optional, für
      später bei Bedarf).
- [x] **Echt verifiziert** (lokales PostgreSQL 17, nicht nur SQLite-Simulation):
      Migration einer Kopie der echten DB (353 Teilnehmer, 5616 Protokoll-
      Einträge – alle Zahlen exakt übertragen), Web-App komplett gegen Postgres
      (Lesen, Schreiben, Statistik, Aufgaben), und ein **echter Vodafone-Import
      direkt gegen Postgres** über den neuen Adapter (328 aktualisiert, korrekt
      protokolliert, per direkter SQL-Abfrage gegengeprüft).

**Für den produktiven Einsatz:** siehe `deploy/POSTGRES.md`. Kein Zwang — nur
sinnvoll bei mehr als ein paar gleichzeitigen Nutzern.

---

## Phase 3 — Komplettes Frontend in React ✅ (inhaltlich fertig)

**Ziel:** app-artige, interaktivere Oberfläche; Flask als JSON-API.
Die Geschäftslogik (`modules/`, SQLAlchemy, Rollen) bleibt erhalten.

Eigenes Repo: **github.com/grumel/mdw-frontend** (Vite + React). Spricht die
JSON-API (`webapp/blueprints/api.py`, Präfix `/api`) an, die **parallel** zur
bestehenden Jinja-Oberfläche im selben Backend läuft.

- [x] JSON-API in Flask (`api.py`, Session-Auth, CSRF-exempt für React)
- [x] React-App: Login, alle Provider-Tabs + abgeleitete Ansichten (Prüfungen/
      Unvollständig/Duplikate), Bearbeiten/Neu, Rechtsklick-Aktionen (geprüft/
      verschieben/löschen, rollenbasiert), Aufgaben (Zähler, rote Markierung),
      Statistik, Import (Vodafone Vorschau/Bestätigen, Syno), Einstellungen (DB-Pfad)
- [x] Deployment: Caddy liefert das React-Bundle unter `/`, `/api/*` → gunicorn
- [x] Zusammenführen (Merge-Modus) und Protokoll/Audit-Log — React deckt jetzt
      **alle** Funktionen des bisherigen Web-UI ab
- [ ] Alte Jinja-Templates entfernen, sobald sich niemand mehr auf sie verlässt
      (bewusst noch nicht — dienen als Fallback/Vergleichsreferenz)
- [ ] **Kündigung/Rücknahme/Neuvertrag fehlen noch** (im Desktop-UI vorhanden,
      nie migriert — hängen dort an Windows-COM: Word für PDF, Outlook für
      Mail-Entwurf, siehe `modules/kuendigung.py` / `modules/neuvertrag.py`).
      Läuft auf dem Linux-Server so nicht. Geplanter Ansatz:
      - Vorlage füllen (`python-docx`, bereits plattformunabhängig) → PDF
        über **LibreOffice headless** statt Word-COM erzeugen, Download-Button
        im React-Frontend.
      - Statt Outlook-Entwurf: Betreff/Text zum Kopieren anzeigen, PDF wird
        manuell an Outlook (Windows-Client) angehängt und verschickt.
      - Neuvertrag: eigenes Formular in React fehlt komplett, plus
        Werk→Konto-Zuordnung aus den Einstellungen (`konto_plant`) muss in
        die Web-Einstellungen übernommen werden.
      - Voraussetzung: LibreOffice auf dem Server installieren, Word-Vorlagen
        (`vorlage_kündigung.docx`, `vorlage_rücknahme.docx`) auf den Server
        übertragen.

**Mehrwert:** flüssiger (keine Reloads), Kennzahl-Kacheln/Balken, wiederverwendbare
Komponenten, mobil-/PWA-tauglich.

---

## Querschnitt (jederzeit)
- **HTTPS** produktiv (Caddy)
- **Alembic** für versionierte Schema-Änderungen (spätestens mit Phase 2)
- **Tests** je Ausbaustufe (wie bisher: gegen eine DB-Kopie)
