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


def _is_duplicate_column(exc):
    """True, wenn der Fehler bedeutet „Spalte existiert bereits".

    Tritt auf, wenn ein zweiter Worker/Prozess dieselbe Spalte zeitgleich
    angelegt hat (Wettlauf beim Start mehrerer gunicorn-Worker). Deckt SQLite
    (`duplicate column name`) und PostgreSQL (`already exists`) ab."""
    msg = str(exc).lower()
    return "duplicate column" in msg or "already exists" in msg


def _ensure_columns(table, wanted):
    """Rüstet fehlende Spalten einer einzelnen Tabelle nach (siehe ensure_schema).
    Gibt die Liste tatsächlich hinzugefügter Spalten zurück; fehlt die Tabelle
    selbst (z. B. frische DB), wird das leise übersprungen (kein Fehler)."""
    try:
        cols = {c["name"] for c in inspect(engine).get_columns(table)}
    except Exception:
        return []
    missing = [(n, ddl) for n, ddl in wanted if n not in cols]
    added = []
    # Jede Spalte in EIGENER Transaktion nachrüsten. Legt ein anderer Worker
    # dieselbe Spalte zeitgleich an, ist „existiert schon" kein echter Fehler
    # (idempotent) – wir überspringen sie und machen mit der nächsten weiter.
    # Nur echte Fehler (gesperrte/nicht schreibbare DB o. Ä.) werden gemeldet.
    for name, ddl in missing:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            added.append(name)
        except Exception as exc:
            if _is_duplicate_column(exc):
                continue
            raise
    return added


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
        ("pin", "TEXT"),       # SIM-PIN, eigenes Feld neben der GSM-Nummer
    ]
    missing = [(n, ddl) for n, ddl in wanted if n not in cols]
    added = []
    try:
        for name, ddl in missing:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE participants ADD COLUMN {name} {ddl}"))
                added.append(name)
            except Exception as exc:
                if _is_duplicate_column(exc):
                    continue
                raise
        # users.notes – persönliches Notizfeld (Frontend-Knopf "Notizen").
        # Eigene Tabelle, eigener try/except-Block wäre unnötig doppelt; die
        # Helper-Funktion schluckt eine fehlende Tabelle bereits selbst.
        added += _ensure_columns("users", [("notes", "TEXT")])
        # audit_log – ausführliches Änderungsprotokoll mit Einzel-Rücknahme.
        added += _ensure_columns("audit_log", [
            ("changes", "TEXT"),
            ("snapshot", "TEXT"),
            ("undo_op", "TEXT"),
            ("reverted_at", "TEXT"),
            ("revert_of_id", "INTEGER"),
        ])
        SCHEMA_STATE.update(ok=True, added=added, error=None, note=None)
    except Exception as exc:
        SCHEMA_STATE.update(ok=False, added=added, error=str(exc), note=None)
        raise
