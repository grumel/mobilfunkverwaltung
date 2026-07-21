# Performance und Betrieb

## Baseline

Das Frontend wird als Vite-Produktionsbundle gebaut. Der Linux-Betrieb nutzt
Gunicorn mit zwei synchronen Workern und SQLite; Caddy komprimiert Antworten.
Die aktuellen Buildgrößen und Laufzeiten werden durch CI/Smoke-Test sichtbar,
aber noch nicht als dauerhafte Zeitreihe erfasst.

Eine reproduzierbare lokale Baseline kann mit
`backend/.venv/bin/python scripts/performance-baseline.py` erzeugt werden. Die
erste Messung mit 100 temporären Teilnehmer-Fixtures (Median aus fünf Läufen)
ergab: `/api/participants` 2,76 ms, `/api/summary` 1,24 ms, `/api/tasks`
1,11 ms und `/api/stats` 4,27 ms. Diese Werte sind Vergleichswerte für spätere
Änderungen, keine Produktions-SLOs.

## Beobachtete Kandidaten

- `webapp/__init__.py` berechnet offene Aufgaben im Context Processor pro Request
  und führt dafür zwei Datenbankabfragen aus.
- Teilnehmer-, Statistik- und Importpfade enthalten mehrere Abfragen und
  Python-seitige Filter; Änderungen benötigen Profiling mit realistischen
  Fixtures.
- React bündelt mehrere Fachbereiche in einem App-State; unnötige Renderings
  sind möglich, aber ohne Browserprofiling nicht belegt.
- Globale CSS-Dateien und das bestehende Bundle sind wartbar, aber noch nicht
  durch eine Größen-Budgetprüfung abgesichert.

## Sichere nächste Schritte

1. P1: Produktionsunabhängige Baseline für API-Latenzen, DB-Abfragen und
   Bundlegröße mit festen Fixtures.
2. P1: SQLAlchemy-/SQLite-Query-Profiling auf Teilnehmerliste, Dashboard und
   Statistik; erst danach gezielte Index-/Query-Entscheidungen.
3. P2: React Profiler und Browser-Smoke-Test für Renderhäufigkeit.
4. P2: CI-Budget für `frontend/dist/assets` und Caddy-Kompression beobachten.

Es wurden keine Caches, Queries, React-States oder Workerzahlen verändert, weil
dies ohne Messung funktionales oder betriebliches Verhalten verändern könnte.
