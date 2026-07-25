# Technische Schulden und Konsolidierung

Stand: 21. Juli 2026, Phase 2 „Technische Konsolidierung“.

Diese Liste beschreibt Befunde aus einer statischen Analyse des Monorepositories.
Es wurden keine funktionalen Änderungen an Backend, API, Datenbank, React oder
Import-/Exportlogik vorgenommen.

| Fundstelle | Beschreibung | Risiko | Priorität | Empfehlung |
| --- | --- | --- | --- | --- |
| `backend/modules/database.py` und `backend/webapp/db.py` | Zwei absichtlich parallele Datenzugriffsschichten: Desktop-SQLite und Web-SQLAlchemy. | Änderungen können nur in einer Schicht landen; divergierende Schemaupdates möglich. | Hoch | Verantwortungsgrenzen und gemeinsame Schema-/Migrationsstrategie dokumentieren; erst danach schrittweise Tests ergänzen. |
| `backend/webapp/__init__.py:create_app` | `ensure_schema()` wird beim App-Start ausgeführt und exceptions werden vollständig verschluckt. | Start kann mit unvollständigem Schema fortgesetzt werden; Fehler bleiben unsichtbar. | Hoch | Fehler protokollieren und eine explizite, kontrollierte Migrations-/Health-Strategie entwerfen. Keine stille Änderung ohne Betriebskonzept. |
| `backend/webapp/blueprints/api.py`, `imports.py` | Upload-, Dokument- und Synology-Pfade werden an mehreren Stellen separat zusammengesetzt. | Path-Traversal- und Berechtigungsprüfungen können uneinheitlich werden. | Hoch | Gemeinsamen, getesteten Pfad-Resolver mit erlaubten Wurzeln einführen; API-Verträge dabei unverändert lassen. |
| `backend/webapp/blueprints/api.py` | Mehrere lokale Imports, Dateioperationen und Fallbackpfade in einer sehr großen Blueprint-Datei. | Schwer testbar; Fehlerbehandlung und Seiteneffekte sind gekoppelt. | Mittel | Nur in kleinen, API-neutralen Einheiten extrahieren; jeden Schritt mit Regressionstests absichern. |
| `backend/modules/database.py` | Dynamische SQL-Spaltennamen in `update_user` werden aus einer internen Feldliste gebaut. Werte sind parametrisiert, die Feldliste ist jedoch sicherheitskritisch. | Künftige Erweiterungen könnten SQL-Injection ermöglichen. | Hoch | Feldnamen strikt aus statischer Allowlist ableiten und einen Test für unbekannte Felder ergänzen. |
| `backend/webapp/config.py` / `modules/paths.py` | Daten-, Ressourcen-, Webconfig- und Datenbankpfade werden über mehrere Module aufgelöst. | Unterschiedliche Startkontexte können unterschiedliche Dateien verwenden. | Mittel | Eine dokumentierte Konfigurationsmatrix und zentrale Resolver-Schnittstelle etablieren. |
| `backend/run.py`, `run_webapp.py`, `deploy/linux/mobilfunk-web.service` | Mehrere Startwege für Desktop, lokale Webentwicklung und Gunicorn. | Lokale Tests können einen anderen Pfad als Produktion ausführen. | Mittel | Startmodi dokumentieren und mit Smoke-Tests gegen denselben App-Factory-Einstieg absichern. |
| `frontend/src/App.jsx` und `frontend/src/components/*` | UI-Orchestrierung und viele Fachbereiche liegen in einem gemeinsamen State-/Fetch-Fluss. | Unnötige Renderings und schwer isolierbare Fehler möglich. | Mittel | Komponentenweise Testgrenzen und Datenzugriffsschicht ausbauen; keine kosmetische oder API-Änderung. |
| `frontend/src/*.css` | Styles verteilen sich auf mehrere globale CSS-Dateien (`index`, `app-v2`, `shell-v2`, `login`). | Namensüberschneidungen und unbeabsichtigte Kaskaden. | Niedrig | CSS-Namenskonvention und Ownership dokumentieren; erst mit visuellen Regressionstests konsolidieren. |
| `frontend/public` und `frontend/dist` | `dist` ist ein erzeugtes Artefakt neben den Quellen; Icons existieren in `public` und im Build. | Veraltete Artefakte können lokale Prüfungen verwirren. | Niedrig | Build-Artefakte ausschließlich erzeugen und nicht als Quelle pflegen; keine produktive Datei im Rahmen dieser Phase löschen. |
| `deploy/windows/*` | Frühe Windows-Vorbereitung liegt neben produktivem Linux-Deployment. | Unklare Reifegrade und versehentliche Plattformänderungen. | Mittel | Als experimentell kennzeichnen und separat testen; nicht in Linux-Refactorings einbeziehen. |
| `deploy/linux/install.sh` | Installer führt Paketinstallation, Git-Update, Build, Konfigurationswechsel und Sleep-Maskierung in einem Skript aus. | Große Änderungsreichweite und erschwerte Rollbacks. | Mittel | Schritte in überprüfbare Funktionen/Phasen teilen; produktive Migration weiterhin über `docs/PRODUCTION_MIGRATION.md`. |
| `deploy/linux/migrate_to_postgres.py` | Optionale PostgreSQL-Migration kopiert ORM-Modelle, ist aber nicht Teil des SQLite-Produktivpfads. | Veraltete optionale Funktion kann bei Wiederverwendung Datenbestände falsch behandeln. | Niedrig | Separaten Test-/Runbook-Status dokumentieren; nicht automatisch aktivieren. |
| `scripts/` | Produktions-Smoke-Test deckt ohne Laufzeitvariablen keine Authentifizierung ab. | Login-/Berechtigungsregressionen können unentdeckt bleiben. | Hoch | Dediziertes Testkonto und CI-/Staging-Secret-Injektion bereitstellen; keine Produktivdaten verwenden. |
| Repository insgesamt | Keine dedizierte Unit-/Integration-Teststruktur für Importe, Uploads, Dokumente und Rollen. | Kritische Fachlogik ist nur durch Smoke-/manuelle Tests geschützt. | Hoch | Priorisierte Tests (siehe Abschnitt „Testlücken“) ergänzen, bevor interne Module verschoben werden. |
| `backend/modules/*` | Mehrere Desktop-Module sind im Web-Checkout weiterhin erforderlich, andere nur indirekt. | Ungenutzte Dateien werden fälschlich gelöscht oder bleiben ungewartet. | Mittel | Nutzung per Importgraph und Laufzeitprofil belegen; erst danach einzeln deprecaten. |
| Logging in Import-/Dokumentpfaden | Logging ist über Module verteilt; sensible Eingabewerte werden nicht zentral klassifiziert. | Risiko unbeabsichtigter personenbezogener Daten in Logs. | Mittel | Logging-Richtlinie und Tests für redigierte Werte definieren. |

## Testlücken und Prioritäten

1. **P0:** App-Factory, Login/Logout, Rollen (`read`/`write`/`admin`), Session-
   Cookie-Eigenschaften und `/api/me` mit temporärer SQLite-Datenbank.
2. **P0:** Uploadvalidierung, Dateinamen-Normalisierung, erlaubte Wurzeln und
   Download-/Dokumentzugriff einschließlich Traversal-Fälle.
3. **P1:** Teilnehmer-CRUD, Aufgaben, Gerätezuordnung, Suche/Filter und
   Statistiken mit festen Fixture-Daten.
4. **P1:** Vodafone-/Synology-Importe als Vorschau und Fehlerfälle; keine
   umfangreichen produktiven Imports.
5. **P1:** Export- und Dokumenterzeugung mit temporärem Datenverzeichnis.
6. **P2:** React-Komponententests und Browser-Smoke-Test mit stabilen Fixtures.
7. **P2:** Performance-Baseline für Teilnehmerliste, Dashboard und Importe.

## Sicherheitsbefunde

- Secret wird aus `MOBILFUNK_SECRET` oder einer persistenten Datei bezogen; die
  Produktionsdatei liegt außerhalb des Checkouts und ist `root:root`/`0600`.
- SQL-Werte werden überwiegend parametrisiert bzw. über SQLAlchemy gebunden;
  dynamische Spaltenlisten bleiben ein Review-Punkt.
- `secure_filename` und `basename` werden an Upload-/Download-Stellen genutzt;
  die erlaubten Zielwurzeln sollten zentral und testbar gemacht werden.
- Caddy setzt CSP, `nosniff`, `DENY` und Same-Origin-Referrer-Policy.
- Keine Secrets oder produktiven Daten wurden in diese Dokumentation oder den
  Git-Verlauf aufgenommen.

## Bewusst nicht geändert

Keine API-Routen, Datenbankmodelle, React-Komponenten, CSS-Regeln, Import-/
Exportabläufe, produktiven Konfigurationen oder Abhängigkeiten wurden geändert.
