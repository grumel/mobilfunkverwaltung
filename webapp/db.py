"""
db.py – SQLAlchemy-Engine und Session-Factory (DB-neutral).

Läuft auf SQLite (aktuell) oder PostgreSQL (später) – nur die DATABASE_URL
ändert sich. Für SQLite wird check_same_thread deaktiviert, weil der
Flask-Entwicklungsserver mehrere Threads nutzen kann.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from webapp.config import DATABASE_URL

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, echo=False,
                       connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()
