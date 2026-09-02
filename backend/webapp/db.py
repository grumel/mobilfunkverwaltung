"""
db.py – SQLAlchemy-Engine und Session-Factory (DB-neutral).

Läuft auf SQLite (aktuell) oder PostgreSQL (später) – nur die DATABASE_URL
ändert sich. Für SQLite wird check_same_thread deaktiviert, weil der
Flask-Entwicklungsserver mehrere Threads nutzen kann.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from webapp.config import DATABASE_URL

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, echo=False,
                       connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()

# Ergebnis der letzten Schema-Prüfung – für /api/health sichtbar, damit
# Migrationsfehler nicht mehr stillschweigend verschluckt werden.
SCHEMA_STATE = {"ok": None, "added": [], "error": None, "note": None}


def ensure_schema():
    """Leichte Migration: fehlende Spalten nachrüsten (SQLite + PostgreSQL).
    Läuft beim App-Start; bei frischer DB (Tabelle fehlt noch) passiert nichts.

    Das Ergebnis landet in SCHEMA_STATE. Ein echter Migrationsfehler (z. B.
    gesperrte/nicht schreibbare DB) wird protokolliert UND weitergereicht,
    statt ihn zu verschlucken."""
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("participants")}
    except Exception as exc:
        # Keine participants-Tabelle (z. B. frische DB) – kein Migrationsfehler,
        # nur ein Hinweis; die App darf starten.
        SCHEMA_STATE.update(ok=True, added=[], error=None,
                            note=f"Schema-Prüfung übersprungen: {exc}")
        return

    wanted = [
        ("overhead", "INTEGER DEFAULT 0"),
        ("imei", "TEXT"),      # IMEI-Nr. Gerät 1 (aus 'Syno seit' herausgelöst)
        ("imei2", "TEXT"),     # IMEI-Nr. Gerät 2
        ("archived", "INTEGER DEFAULT 0"),
    ]
    missing = [(n, ddl) for n, ddl in wanted if n not in cols]
    try:
        if missing:
            with engine.begin() as conn:
                for name, ddl in missing:
                    conn.execute(text(f"ALTER TABLE participants ADD COLUMN {name} {ddl}"))
        SCHEMA_STATE.update(ok=True, added=[n for n, _ in missing], error=None, note=None)
    except Exception as exc:
        SCHEMA_STATE.update(ok=False, added=[], error=str(exc), note=None)
        raise
