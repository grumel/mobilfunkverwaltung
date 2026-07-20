# Dokumentierte Cleanup-Kandidaten

Diese Bestandsaufnahme entstand während der Monorepo-Migration. Die genannten
Dateien und Überschneidungen wurden bewusst **nicht** gelöscht oder
zusammengeführt, damit sich das Laufzeitverhalten durch die Migration nicht
ändert. Vor einer Bereinigung müssen Nutzung, Produktionsdaten und fachliche
Abhängigkeiten separat geprüft werden.

## Parallele Einstiegspunkte

| Fundstelle | Beobachtung | Empfehlung für eine spätere Prüfung |
| --- | --- | --- |
| `backend/run.py` | Gemeinsamer aktueller Einstieg für Flask beziehungsweise Waitress. | Als kanonischen lokalen Einstieg bestätigen. |
| `backend/run_webapp.py` | Kompatibler Python-Starter für ältere Aufrufe. | Server-, Desktop- und Benutzerverknüpfungen inventarisieren, bevor er entfallen könnte. |
| `backend/run_webapp.bat` | Windows-Doppelklick-Starter mit eigener Umgebungsinitialisierung. | Nach Festlegung des Windows-Betriebsmodells gegen `deploy/windows/start.ps1` abgrenzen. |

## Parallele Oberflächen

- `backend/webapp/templates/` und `backend/webapp/static/app.css` enthalten die
  servergerenderte Flask-Oberfläche.
- `frontend/src/` enthält die produktive React-Oberfläche.

Die Flask-Oberfläche ist als dokumentierter Fallback weiterhin erreichbar und
deshalb kein sicher ungenutzter Code. Vor einer Entfernung müssen sämtliche
direkten Backend-URLs, Importseiten und Administrationsabläufe geprüft werden.

## Doppelte oder überlappende Hilfsfunktionen

- Upload-Speicherung ist sowohl in `backend/webapp/blueprints/api.py` als auch
  in `backend/webapp/blueprints/imports.py` implementiert. Die Funktionen
  bedienen derzeit unterschiedliche Oberflächen.
- Authentifizierungslogik existiert in `backend/modules/auth.py` und als
  HTTP-Blueprint in `backend/webapp/blueprints/auth.py`. Der Blueprint verwendet
  die gemeinsamen Hash-/Prüffunktionen; es handelt sich nicht um zwei getrennte
  Passwortformate.
- Datenbankzugriff liegt sowohl in `backend/modules/database.py` als auch in
  `backend/webapp/db.py`. Ersterer gehört zur übernommenen Desktop-/Importlogik,
  letzterer zur Flask-/SQLAlchemy-Anwendung.
- SQLite-Konfiguration wird von `backend/modules/paths.py`,
  `backend/platform_support/__init__.py`, `backend/webapp/config.py` und
  `backend/webapp/webconfig.py` gemeinsam bestimmt. Die Ebenen haben
  unterschiedliche Zuständigkeiten, sollten aber vor späteren Änderungen als
  ein Konfigurationsfluss dokumentiert oder getestet werden.

## Mögliche Legacy-Module

Die Dateien `backend/modules/ui_*.py`, `backend/modules/theme.py` und
`backend/modules/orchestrator.py` stammen aus der Desktop-Anwendung. Ihre
vollständige Nutzung durch die Webanwendung ist nicht nachgewiesen. Sie bleiben
erhalten, weil Import-, Dokument- oder Administrationsabläufe indirekt darauf
zugreifen können und die Migration keine Funktionalität entfernen darf.

## Deployment-Überschneidungen

- `deploy/linux/Caddyfile` und `deploy/windows/Caddyfile` sind bewusst getrennte
  Plattformkonfigurationen, obwohl Routing und Sicherheitsheader ähnlich sind.
- `deploy/linux/mobilfunk-web.service` ist eine statische Referenz-Unit;
  `deploy/linux/install.sh` erzeugt zusätzlich eine Unit dynamisch. Beide müssen
  bei Änderungen synchron gehalten werden.
- `deploy/linux/INSTALL.md`, `deploy/README.md`, `backend/README.md` und die
  zentrale `README.md` beschreiben teilweise dieselben Start- und
  Installationswege. Die Detaildokumente bleiben für bestehende Links erhalten.
- `deploy/windows/` enthält bereits die aus dem Backend übernommene frühe
  Waitress-/Caddy-Vorbereitung und ist damit mehr als ein leerer Platzhalter.
  Sie wird durch die Monorepo-Migration nicht als produktionsreif erklärt und
  wurde ausschließlich auf `backend/` und `frontend/` umgestellt.

## Repository- und Build-Artefakte

- Lokale Verzeichnisse wie `backend/.venv`, `frontend/node_modules`,
  `frontend/dist` und `__pycache__` sind über die zentrale `.gitignore`
  ausgeschlossen und nicht Teil der importierten Historien.
- `backend/CLAUDE.md` und `frontend/CLAUDE.md` enthalten projektspezifische
  Arbeitsanweisungen. Eine Zusammenführung wäre möglich, könnte aber
  komponentenspezifischen Kontext verlieren.
- Umfassende fachliche Unit-/Integrationstests fehlen weiterhin. Die gemeinsame
  CI prüft derzeit Kompilierung, Struktur, Frontend-Build und einen isolierten
  Backend-Smoke-Test; sie ersetzt keine vollständige Regressionstest-Suite.

## Empfohlene Reihenfolge einer späteren Bereinigung

1. Produktionsaufrufe und direkte URLs inventarisieren.
2. Regressionstests für Authentifizierung, CRUD, Import, Export und Dokumente
   ergänzen.
3. Einstiegspunkte und Deployment-Dokumentation konsolidieren.
4. Erst danach nachweislich ungenutzte Desktop- oder Fallback-Dateien entfernen.
