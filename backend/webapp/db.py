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


def ensure_schema():
    """Leichte Migration: fehlende Spalten nachrüsten (SQLite + PostgreSQL).
    Läuft beim App-Start; bei frischer DB (Tabelle fehlt noch) passiert nichts."""
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("participants")}
    except Exception:
        return
    # (Spaltenname, Typ/Default). Reihenfolge stabil, additiv, nicht-destruktiv.
    wanted = [
        ("overhead", "INTEGER DEFAULT 0"),
        ("imei", "TEXT"),      # IMEI-Nr. Gerät 1 (aus 'Syno seit' herausgelöst)
        ("imei2", "TEXT"),     # IMEI-Nr. Gerät 2
    ]
    missing = [(n, ddl) for n, ddl in wanted if n not in cols]
    if missing:
        with engine.begin() as conn:
            for name, ddl in missing:
                conn.execute(text(f"ALTER TABLE participants ADD COLUMN {name} {ddl}"))
