# Teststrategie

## Vorhandene Prüfungen

- Backend: `compileall` und `scripts/backend-ci-smoke.py` mit temporärer
  SQLite-Datenbank, App-Factory, Version, Login und Session.
- Phase 3: `scripts/backend-regression-tests.py` prüft zusätzlich ungültige
  Anmeldungen, Rollenbasis, Teilnehmerliste, Summary, Tasks, Statistik,
  Dokumentliste, Traversal-Fälle und Logout mit temporären Fixtures.
- Frontend: `npm ci` und `npm run build`.
- Linux: `scripts/smoke-test-linux.sh` prüft Backend, Caddy/Frontend und kann
  Login/Session über Laufzeitvariablen prüfen.
- CI: Backend-, Frontend- und Monorepo-Workflows prüfen Syntax, Struktur und
  Build.

## Fehlende Abdeckung

| Priorität | Bereich | Mindestumfang |
| --- | --- | --- |
| P0 | Authentifizierung | Login/Logout, Rollen, Session-Cookie, `/api/me`, ungültige Credentials |
| P0 | Uploads/Dokumente | erlaubte Endungen, Größenfehler, sichere Dateinamen, Traversal, Zugriffsschutz |
| P1 | Teilnehmer/Aufgaben | CRUD, Suche, Filter, Gerätezuordnung, Statusübergänge |
| P1 | Importe | Vodafone/Syno-Vorschau, Fehlerfälle, Duplikate, Rollback auf Fixture-Daten |
| P1 | Exporte/Dokumente | temporäre Vorlagen, PDF-/Dateierzeugung, Downloadrechte |
| P1 | SQLite | Schema-Check, WAL, konkurrierende Lesezugriffe, Bestandscounts |
| P2 | React | API-Fehlerzustände, Loginfluss, zentrale Komponenten mit stabilen Fixtures |
| P2 | Performance | Query-/Render-Baseline und Bundlegröße |

## Regeln

Tests verwenden temporäre Datenverzeichnisse und Testkonten. Produktive SQLite-
Dateien, Dokumente und Secrets werden nie für Schreibtests verwendet. Jede
interne Strukturänderung benötigt zuerst Regressionstests für den betroffenen
Vertrag und einen separaten Commit.
