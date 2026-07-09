# PostgreSQL statt SQLite (Phase 2)

Wechselt die Datenbank von SQLite auf PostgreSQL. Sinnvoll bei mehr
Gleichzeitigkeit/Nutzern. Bei 2–3 Nutzern ist SQLite weiterhin völlig
ausreichend – dieser Schritt ist **optional**.

## 0. Voraussetzung
`Import-Refactor` ist bereits umgesetzt: `modules/vodafone_import.py` und
`modules/syno_import.py` akzeptieren einen `db_module`-Parameter. Die API
(`webapp/blueprints/api.py`) wählt automatisch den passenden Adapter
(`webapp/import_adapter.py`, SQLAlchemy) sobald `DATABASE_URL` nicht mit
`sqlite` beginnt – **keine Code-Änderung nötig**, nur Konfiguration.

## 1. PostgreSQL installieren (Debian/Ubuntu)
```bash
sudo apt install -y postgresql
sudo -u postgres psql -c "CREATE USER mobilfunk WITH PASSWORD 'BITTE-AENDERN';"
sudo -u postgres psql -c "CREATE DATABASE mobilfunk OWNER mobilfunk;"
```

## 2. Treiber installieren
```bash
cd /opt/mobilfunk-web
sudo -u mobilfunk sed -i 's/^# psycopg/psycopg/' requirements-server.txt
sudo -u mobilfunk .venv/bin/pip install -r requirements-server.txt
```

## 3. Daten migrieren
Die App läuft währenddessen weiter auf SQLite (Quelle wird nur gelesen):
```bash
cd /opt/mobilfunk-web
sudo -u mobilfunk .venv/bin/python deploy/migrate_to_postgres.py \
    --sqlite /var/lib/mobilfunk/mobilfunk.db \
    --postgres "postgresql+psycopg://mobilfunk:BITTE-AENDERN@localhost:5432/mobilfunk"
```
Gibt je Tabelle die kopierte Zeilenzahl aus – mit der SQLite-Quelle vergleichen
(z. B. `sqlite3 mobilfunk.db "SELECT COUNT(*) FROM participants;"`).

## 4. Umschalten
In der App unter **⚙ Einstellungen** (Admin) im Feld „DATABASE_URL" die
Postgres-URL eintragen, dann:
```bash
sudo systemctl restart mobilfunk-web
```
Alternativ per Environment-Datei (`/var/lib/mobilfunk/mobilfunk.env`):
```
DATABASE_URL=postgresql+psycopg://mobilfunk:BITTE-AENDERN@localhost:5432/mobilfunk
```
(hat Vorrang vor der Einstellungen-Seite).

## 5. Verifizieren
- Login funktioniert
- Alle Tabs zeigen dieselben Datensatzzahlen wie vorher
- Eine Bearbeitung speichern und prüfen, dass sie ankommt
- **Einen echten Vodafone-/Syno-Import testen** (kleine Testdatei oder
  Vorschau) – das ist der Teil, der neu auf SQLAlchemy läuft

Bei Problemen: `DATABASE_URL` wieder auf die SQLite-Datei zurücksetzen
(Einstellungen leeren oder Environment-Variable entfernen) und
`systemctl restart mobilfunk-web` – die SQLite-Datei ist unverändert erhalten
geblieben (Migration liest sie nur).

## Was sich technisch ändert
- Teilnehmer-CRUD, Aufgaben, Statistik, Merge, Logs: liefen schon vorher über
  SQLAlchemy (`webapp/models.py`) – funktionieren unverändert mit Postgres.
- Excel-Importe (Vodafone/Syno): laufen ab jetzt bei Postgres über
  `webapp/import_adapter.py` statt über das SQLite-spezifische
  `modules/database.py`. Gleiche Geschäftslogik (identische Datei,
  `db_module`-Parameter injiziert), unabhängig getestet.
- Backups: das automatische SQLite-Backup vor jedem Import entfällt bei
  Postgres (macht keinen Sinn mehr). Für Postgres regelmäßig `pg_dump`
  einplanen, z. B. per Cron:
  ```bash
  pg_dump -U mobilfunk mobilfunk | gzip > /var/backups/mobilfunk_$(date +%F).sql.gz
  ```
