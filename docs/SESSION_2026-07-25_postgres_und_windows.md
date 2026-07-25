# Sitzungsprotokoll – 23.–25. Juli 2026

Festgehaltener Verlauf der Arbeitssitzung zu Windows-Runtime, docxtpl und dem
PostgreSQL-Umstieg. Dient als Nachvollziehbarkeit und Übergabe.

## 1. Windows-Runtime und docxtpl (PR #2, Branch `feature/docxtpl-vorlagen`)

- `stop.ps1` korrigiert: Port wird über den lauschenden Socket statt über die
  Kommandozeile aufgelöst (das Skript beendete vorher nie einen Prozess).
- Kündigung/Rücknahme über **docxtpl** statt eigener Run-Ersetzung; Vorlagen
  ohne Umlaut im Namen (`vorlage_kuendigung.docx` / `vorlage_ruecknahme.docx`),
  alte Namen übergangsweise lesbar.
- PDF-Erzeugung plattformgerecht: Windows über Word-COM, Linux über LibreOffice
  (`convert_to_pdf_auto`, `MOBILFUNK_PDF_ENGINE`, `MOBILFUNK_SOFFICE`).
- `bootstrap.ps1` (prüft/installiert Voraussetzungen per winget) und
  `uninstall.ps1` (entfernt nur Laufzeitartefakte, Daten bleiben) ergänzt.
- Offen: Abnahme auf einem echten Windows-Host; Entscheidung über eine
  gebündelte EXE (steht im Konflikt mit der SRP-Richtlinie bei ALPLA).

## 2. Datenbank auf SharePoint – geprüft und verworfen

Eine SQLite-Datei auf SharePoint (OneDrive-Sync, WebDAV, Netzlaufwerk) ist als
**aktive** Datenbank ungeeignet: kein verlässliches Datei-Locking, WAL
funktioniert nicht über Netz, paralleler Zugriff führt zu Korruption. SharePoint
taugt nur als Ablage für **vollständige, konsistente Sicherungen**.

Konsequenz: Für echten Mehrbenutzerzugriff wird auf PostgreSQL umgestellt.

## 3. Umstieg auf PostgreSQL (Branch `feature/postgresql-umstieg`)

Der Code war bereits DB-neutral (SQLAlchemy). Nötig war nur, den Treiber
`psycopg` in `backend/requirements-server.txt` zu aktivieren. Zusätzlich:

- `deploy/POSTGRES_SHARED.md`: Anleitung für mehrere Windows-Arbeitsplätze gegen
  eine zentrale Datenbank.
- `deploy/verify_migration.py`: prüft nach der Migration Zeilenzahlen und
  id-Sequenzen.

### Migration end-to-end getestet (lokales PostgreSQL 14, Fantasiedaten)

Gegen eine Wegwerf-SQLite-DB mit ausschließlich erfundenen Daten (keine
personenbezogenen Daten) migriert und verifiziert:

```text
Tabelle                   SQLite    PostgreSQL   Status
users                          2             2   OK
participants                  51            51   OK
tasks                         10            10   OK
unmatched_devices              5             5   OK
import_log                    20            20   OK
audit_log                     15            15   OK

Sequenz-Pruefung: participants max(id)=9999 → nächste ID 10000   OK
App gegen Postgres: Login OK, Vodafone=50, Telekom=1 (Provider-Filter greift)
ERGEBNIS: ALLES GLEICH
```

Damit sind Datenkopie, id-Sequenzen und der reale App-Zugriff über die JSON-API
gegen PostgreSQL nachgewiesen.

## 4. Ablauf der echten Migration (Zusammenfassung)

1. PostgreSQL-Host aufsetzen (immer laufend, im Netz erreichbar).
2. `psycopg` installieren (`pip install -r backend/requirements-server.txt`).
3. `deploy/linux/migrate_to_postgres.py` **einmalig** gegen die produktive
   SQLite-Datei laufen lassen (liest sie nur).
4. `deploy/verify_migration.py` ausführen – **vor** dem ersten Login.
5. Auf jedem Arbeitsplatz `DATABASE_URL` auf den gemeinsamen Host setzen.
6. Sicherung künftig zentral per `pg_dump`.

Rollback jederzeit: `DATABASE_URL` entfernen → lokale SQLite-Datei (unverändert).

Details: [`deploy/POSTGRES_SHARED.md`](../deploy/POSTGRES_SHARED.md),
[`deploy/linux/POSTGRES.md`](../deploy/linux/POSTGRES.md).
