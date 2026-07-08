# Roadmap

Geplante Ausbaustufen der Web-App. Reihenfolge bewusst so gewählt: erst eine
laufende Lösung, dann Datenbank, dann Frontend.

---

## Phase 1 — Server-Go-Live (aktuell)

Kleiner Linux-Rechner (Lenovo ThinkPad, Ubuntu/Debian Desktop genügt) im eigenen
Netz. Automatischer Installer `deploy/install.sh` richtet alles ein: gunicorn +
Caddy (Port 80), systemd-Dienst, Backup-Cron, „Immer-an".

- [x] Härtung: persistentes Secret + CSRF
- [x] Deployment-Paket + Installer (Port 80)
- [ ] Server aufsetzen, DB `mobilfunk.db` übertragen, erster Lauf
- [ ] Danach optional **HTTPS** (im `Caddyfile` `:80` → DNS-Name; Caddy holt das Zertifikat)

Stabiler Zustand als Basis für Phase 2 und 3.

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

**Reihenfolge-Tipp:** Wenn Phase 3 (React/API) ohnehin kommt, bietet es sich an,
den Import-Refactor (Schritt 3) **zusammen mit der API-Schicht** zu erledigen —
dann ist alles konsistent auf SQLAlchemy/Postgres.

---

## Phase 3 — Komplettes Frontend in React

**Ziel:** app-artige, interaktivere Oberfläche; Flask wird zur reinen JSON-API.
Die Geschäftslogik (`modules/`, SQLAlchemy, Rollen) bleibt erhalten.

**Vorgehen (sanfter Übergang, kein „großer Knall")**
1. **JSON-API** in Flask aufbauen — **neben** der bestehenden Oberfläche. Pro
   Bereich Endpunkte (Teilnehmer, Aufgaben, Import, Statistik, Auth). Auth per
   Session-Cookie oder Token; CSRF/CORS beachten.
2. **React-App** (Vite + React) aufsetzen, Routing, Datenabruf (fetch/React-Query).
3. **Tab für Tab** von Jinja auf React umstellen; beide Wege laufen parallel, die
   App bleibt durchgehend benutzbar.
4. **Build/Deploy:** React-Build (npm/Vite) → statisches Bundle, von Caddy
   ausgeliefert; API bleibt hinter demselben Reverse-Proxy.
5. Alte Jinja-Templates entfernen, wenn ein Bereich vollständig in React läuft.

**Mehrwert:** flüssiger (keine Reloads), schöne Charts (z. B. Recharts),
wiederverwendbare Komponenten, mobil-/PWA-tauglich.

---

## Querschnitt (jederzeit)
- **HTTPS** produktiv (Caddy)
- **Alembic** für versionierte Schema-Änderungen (spätestens mit Phase 2)
- **Tests** je Ausbaustufe (wie bisher: gegen eine DB-Kopie)
