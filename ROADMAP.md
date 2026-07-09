# Roadmap

Geplante Ausbaustufen der Web-App. Reihenfolge bewusst so gewählt: erst eine
laufende Lösung, dann Datenbank, dann Frontend.

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

## Phase 2 — Datenbank-Umbau: SQLite → PostgreSQL

**Ziel:** echte Mehrbenutzer-Gleichzeitigkeit, robustere Sperren/Backups, sauber
für den Netzwerkbetrieb. Die Architektur ist bereits vorbereitet (SQLAlchemy,
`DATABASE_URL`); es fehlt v. a. ein Code-Punkt (Import-Pfad) und die Migration.

**Voraussetzungen**
- PostgreSQL-Server (kann auf demselben Rechner laufen)
- `psycopg[binary]` in der venv (steht auskommentiert in `requirements-server.txt`)

**Schritte**
1. **Postgres einrichten:** Dienst installieren, Datenbank + Benutzer anlegen
   (z. B. DB `mobilfunk`, User `mobilfunk` mit Passwort).
2. **Schema erzeugen:** empfohlen **Alembic** (versionierte Migrationen) mit einer
   Initial-Migration aus den SQLAlchemy-Modellen (`webapp/models.py`). Pragmatisch
   alternativ: `Base.metadata.create_all(engine)` + manuell die Sonderfälle
   (eindeutiger Teil-Index auf `gsm`, wo nicht leer).
3. **⚠ Import-Pfad umstellen (größter Brocken):** `modules/vodafone_import.py` und
   `modules/syno_import.py` schreiben aktuell **direkt über sqlite3**
   (`modules/database.py`). Für Postgres müssen die Importe auf **SQLAlchemy**
   umgestellt (oder in der Web-App neu implementiert) werden. Bis dahin laufen auf
   Postgres nur Lesen + die Web-Aktionen (die nutzen schon SQLAlchemy), **nicht**
   die Excel-Importe.
4. **Daten migrieren:** Skript, das alle Tabellen aus der SQLite-DB liest und in
   Postgres einfügt (Modelle sind DB-neutral). Anschließend die id-Sequenzen in
   Postgres auf `max(id)+1` setzen.
5. **Umschalten:** in **⚙ Einstellungen** (oder `DATABASE_URL`) die Postgres-URL
   `postgresql+psycopg://user:pw@host:5432/mobilfunk` eintragen, Dienst neu starten.
   SQLite-Datei als Fallback/Backup behalten.
6. **Verifizieren:** Datensatzzahlen je Tabelle vor/nach vergleichen; Login, Listen,
   eine Bearbeitung testen. Bei Problemen einfach zurück auf die SQLite-URL.

**Stand:** Phase 3 (React + JSON-API) ist bereits fertig — die API-Schicht existiert
also schon. Der Import-Refactor (Schritt 3) ist damit der nächste konkrete Schritt
für Phase 2, kein „zusammen mit" mehr.

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
- [ ] Rest: **Zusammenführen** (Merge-Modus) und **Protokoll/Audit-Log**-Ansicht
      fehlen in React noch (existieren im alten Jinja-UI)
- [ ] Alte Jinja-Templates entfernen, sobald React sie vollständig abdeckt

**Mehrwert:** flüssiger (keine Reloads), Kennzahl-Kacheln/Balken, wiederverwendbare
Komponenten, mobil-/PWA-tauglich.

---

## Querschnitt (jederzeit)
- **HTTPS** produktiv (Caddy)
- **Alembic** für versionierte Schema-Änderungen (spätestens mit Phase 2)
- **Tests** je Ausbaustufe (wie bisher: gegen eine DB-Kopie)
