# Architektur

## Laufzeit

```text
Browser
   |
   v
Caddy :80
   |-- /       -> frontend/dist (React/Vite, SPA-Fallback)
   `-- /api/*  -> Gunicorn :8000 -> Flask-App-Factory
                                  |-- Blueprints (HTML + JSON)
                                  |-- SQLAlchemy -> SQLite
                                  `-- modules/ (Desktop-/Import-/Dokumentlogik)
```

Im Linux-Produktivbetrieb lauscht Gunicorn ausschließlich auf Loopback. Caddy
ist der öffentliche Einstiegspunkt. Persistente Daten liegen außerhalb des
Git-Checkouts unter `/var/lib/mobilfunk`.

## Schichten

- `frontend/`: React 18 und Vite; API-Zugriff über `src/api.js`.
- `backend/webapp/`: Flask-App-Factory, Blueprints, Web-Konfiguration,
  SQLAlchemy-Modelle und Web-Servicefunktionen.
- `backend/modules/`: bestehende Desktop-, Import-, Dokument- und SQLite-
  Fachlogik. Diese Schicht ist teilweise auch vom Webbetrieb eingebunden.
- `backend/platform_support/`: plattformneutrale Ermittlung von Daten-,
  Ressourcen- und Logpfaden.
- `deploy/linux/`: systemd, Caddy, Installer, Rollback und optionale
  PostgreSQL-Dokumentation.
- `scripts/`: CI-Smoke-Test, Produktions-Smoke-Test und Rollback.

## Daten- und Konfigurationsfluss

`MOBILFUNK_DATA_DIR` bestimmt die persistente Datenwurzel. `DATABASE_URL` kann
die Datenbank explizit wählen; andernfalls folgen Web-Konfiguration und die
SQLite-Standarddatei. `MOBILFUNK_SECRET` wird von systemd außerhalb des
Checkouts geladen. Das Datenmodell liegt in `webapp/models.py`; die ältere
SQLite-Schicht bleibt für Desktop-/Importpfade erhalten.

## Änderungsregeln

API-Routen, JSON-Formate, Datenbankmodelle, Import-/Exportverträge und sichtbare
React-Oberflächen sind öffentliche Verhaltensbestandteile. Interne
Konsolidierungen benötigen Regressionstests und eigene, rückrollbare Commits.
