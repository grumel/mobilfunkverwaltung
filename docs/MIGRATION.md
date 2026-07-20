# Migration zum Monorepository

## Ausgangslage

Die Anwendung bestand aus zwei eigenständigen Git-Repositories:

| Quelle | importierter Stand | Ziel |
| --- | --- | --- |
| `mdweb` / lokaler Stand `mdw-deployment-platforms` | `420fb1d` | `backend/` |
| `mdw-frontend` / Branch `ui/login-redesign` | `ceaeaf4` | `frontend/` |

Beide Quellen wurden ohne Squash über `git subtree add` importiert. Ihre
vollständigen Commit-Ketten sind damit weiterhin über die Eltern der beiden
Subtree-Merge-Commits erreichbar. Es wurden keine Dateien durch Kopieren ohne
Historie übernommen.

## Strukturänderungen

- Der Flask-Anwendungscode liegt jetzt unter `backend/`.
- Der React/Vite-Anwendungscode liegt jetzt unter `frontend/`.
- Die vorhandenen plattformspezifischen Deployment-Dateien wurden aus dem
  Backend nach `deploy/linux/` und `deploy/windows/` verschoben.
- Übergreifende Dokumentation liegt unter `docs/`.
- `scripts/` und `.github/` sind für spätere gemeinsame Automatisierung
  vorbereitet.
- Die getrennten Ignore-Dateien wurden in einer gemeinsamen `.gitignore` für
  Python, Node, Laufzeitdaten und lokale Werkzeuge zusammengeführt.

`deploy/windows/` war im importierten Backend bereits mit einer frühen
Waitress-/Caddy-Laufzeitvorbereitung belegt. Diese Dateien wurden zur
Verlustfreiheit übernommen und nur an die Monorepo-Pfade angepasst; sie gelten
nicht automatisch als vollständig produktionsreifes Windows-Deployment.

## Notwendige Pfadanpassungen

Die Änderungen betreffen ausschließlich den neuen Speicherort:

| Zweck | vorher | nachher |
| --- | --- | --- |
| Repository | zwei Checkouts unter `/opt/mobilfunk-web` und `/opt/mobilfunk-frontend` | `/opt/mobilfunkverwaltung` |
| Backend | Repository-Wurzel | `/opt/mobilfunkverwaltung/backend` |
| Frontend-Build | `/opt/mobilfunk-frontend/dist` | `/opt/mobilfunkverwaltung/frontend/dist` |
| Deployment-Dateien | Backend `deploy/` | Monorepo `deploy/` |
| Gunicorn WorkingDirectory/`--chdir` | `/opt/mobilfunk-web` | `/opt/mobilfunkverwaltung/backend` |
| PostgreSQL-Migrationsimport | Backend-Wurzel relativ zum Skript | `backend/` relativ zur Monorepo-Wurzel |

Der Linux-Installer aktualisiert nun ein Repository und baut das enthaltene
Frontend. Datenpfad (`/var/lib/mobilfunk`), Benutzer (`mobilfunk`), Ports,
Systemd-Dienstname, API-Routing und Datenbankverhalten bleiben unverändert.

## Servermigration

Für eine bestehende Installation wird das Monorepository nach
`/opt/mobilfunkverwaltung` geklont. Danach wird
`deploy/linux/install.sh` ausgeführt. Das Skript erzeugt die virtuelle Umgebung
unter `backend/.venv`, baut `frontend/dist`, aktualisiert die systemd-Unit und
installiert das angepasste Caddyfile. Die vorhandene SQLite-Datei unter
`/var/lib/mobilfunk/mobilfunk.db` wird nicht verschoben oder verändert.

Alte Checkouts können erst nach erfolgreicher Verifikation und unabhängig von
diesem Migrationscommit archiviert werden.

## Nicht geändert

- Backend- und Importlogik
- React-Komponenten, Styles und UI
- REST-Endpunkte und Request-/Response-Formate
- SQLAlchemy-Modelle und SQLite-Schema
- Authentifizierung und Berechtigungen

## Prüfung

Zur Abnahme gehören reproduzierbarer Frontend-Build, Python-Import/Start der
Flask-App, Login und authentifizierter API-Aufruf mit SQLite sowie eine
Validierung des Caddyfiles gegen `frontend/dist`. Die konkreten Ergebnisse sind
im Migrationsbericht des Abschlusscommits festgehalten.

## Remote- und Branch-Struktur

Das Monorepository verwendet folgende Remotes:

| Remote | URL | Zweck |
| --- | --- | --- |
| `origin` | `https://github.com/grumel/mobilfunkverwaltung.git` | neues gemeinsames Repository |
| `legacy-backend` | `https://github.com/grumel/mdwWeb.git` | historische Referenz |
| `legacy-frontend` | `https://github.com/grumel/mdw-frontend.git` | historische Referenz |

Die Migration wird auf `chore/monorepo-migration` veröffentlicht. Das bereits
vorhandene `origin/main` wird nicht überschrieben; die Übernahme erfolgt nach
erfolgreicher CI über einen Pull Request beziehungsweise einen kontrollierten
Merge.

## Gemeinsame CI

- `.github/workflows/backend.yml` kompiliert das Backend und prüft Flask,
  Login, Session-API und SQLite mit einer temporären Datenbank.
- `.github/workflows/frontend.yml` installiert reproduzierbar mit `npm ci`,
  führt vorhandene Tests aus und baut das Vite-Produktionsbundle.
- `.github/workflows/monorepo.yml` prüft Pflichtverzeichnisse, Shell-Syntax und
  Python-Kompilierung.

Die Workflows laufen auf Pull Requests nach `main` sowie auf Pushes nach `main`
und `chore/monorepo-migration`.

## Verbleibende Produktionsschritte

Die tatsächliche Serverumstellung ist absichtlich nicht Teil der
Repository-Migration. Sie muss auf dem Produktionsserver anhand von
[PRODUCTION_MIGRATION.md](PRODUCTION_MIGRATION.md) erfolgen. Erforderlich sind
insbesondere verifizierte Backups, Übernahme der bestehenden Environment-Datei
und Datenverzeichnisse, Installation der neuen systemd-/Caddy-Pfade,
Smoke-Tests und eine dokumentierte Rollback-Entscheidung.

## Offene Punkte

- Migrationsbranch nach erfolgreicher CI kontrolliert in `main` übernehmen.
- Bestehenden Produktionsserver anhand der rückrollbaren Anleitung vom alten
  Checkout auf den neuen Pfad umstellen.
- Native Windows- und Linux-Deploymenttests in CI ergänzen.
- Die in [CLEANUP.md](CLEANUP.md) dokumentierten Kandidaten erst nach separater
  Nutzungsanalyse und Regressionstests bereinigen.
