#!/usr/bin/env python3
"""
migrate_to_postgres.py – Kopiert alle Daten aus der SQLite-Datenbank in eine
PostgreSQL-Datenbank. Beide Schemata sind identisch (webapp/models.py).

Die SQLite-Quelle bleibt unverändert (nur Lesen) – dient danach weiter als
Fallback/Backup.

Aufruf:
    .venv/bin/python deploy/migrate_to_postgres.py \\
        --sqlite /var/lib/mobilfunk/mobilfunk.db \\
        --postgres postgresql+psycopg://mobilfunk:PASSWORT@localhost:5432/mobilfunk

Danach in der App unter ⚙ Einstellungen (oder per DATABASE_URL) die
Postgres-URL hinterlegen und die Web-App neu starten.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from webapp.db import Base
from webapp.models import Participant, User, Task, UnmatchedDevice, ImportLog, AuditLog

# Reihenfolge relevant für Fremdschlüssel-freie, aber sinnvolle Migration
TABLES = [
    (User, "users"),
    (Participant, "participants"),
    (Task, "tasks"),
    (UnmatchedDevice, "unmatched_devices"),
    (ImportLog, "import_log"),
    (AuditLog, "audit_log"),
]


def _row_to_dict(model, row):
    return {c.name: getattr(row, c.name) for c in model.__table__.columns}


def migrate(sqlite_url: str, postgres_url: str, truncate: bool) -> None:
    src_engine = create_engine(sqlite_url, future=True)
    dst_engine = create_engine(postgres_url, future=True)
    SrcSession = sessionmaker(bind=src_engine, future=True)
    DstSession = sessionmaker(bind=dst_engine, future=True)

    print(f"Quelle:  {sqlite_url}")
    print(f"Ziel:    {postgres_url}")

    print("\n1/3  Zielschema anlegen (falls nicht vorhanden) …")
    Base.metadata.create_all(dst_engine)

    src = SrcSession()
    dst = DstSession()
    try:
        if truncate:
            print("\n     --truncate: bestehende Zieldaten werden geleert …")
            for model, name in reversed(TABLES):
                dst.execute(text(f"DELETE FROM {name}"))
            dst.commit()

        print("\n2/3  Daten kopieren …")
        for model, name in TABLES:
            rows = src.query(model).order_by(model.id).all()
            for row in rows:
                dst.add(model(**_row_to_dict(model, row)))
            dst.flush()
            print(f"     {name:<20} {len(rows):>5} Zeilen")
        dst.commit()

        print("\n3/3  Sequenzen (id-Zähler) auf max(id)+1 setzen …")
        # Nur relevant für PostgreSQL (SERIAL/IDENTITY-Sequenzen)
        if dst_engine.dialect.name == "postgresql":
            for model, name in TABLES:
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {name}), 1), "
                    f"(SELECT MAX(id) FROM {name}) IS NOT NULL)"
                ))
            dst.commit()
            print("     erledigt")
        else:
            print("     übersprungen (Ziel ist kein PostgreSQL)")

        print("\nFertig. Bitte Zeilenzahlen oben mit der Quelle vergleichen.")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sqlite", required=True, help="Pfad zur mobilfunk.db")
    ap.add_argument("--postgres", required=True,
                    help="Ziel-URL, z. B. postgresql+psycopg://user:pw@host:5432/mobilfunk")
    ap.add_argument("--truncate", action="store_true",
                    help="Zieltabellen vor dem Kopieren leeren (für Wiederholungen)")
    args = ap.parse_args()

    sqlite_url = args.sqlite
    if not sqlite_url.startswith("sqlite"):
        sqlite_url = "sqlite:///" + str(Path(sqlite_url).resolve()).replace("\\", "/")

    migrate(sqlite_url, args.postgres, args.truncate)
