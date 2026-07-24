#!/usr/bin/env python3
"""
verify_migration.py – Prueft nach der Migration, dass SQLite und PostgreSQL
zeilengleich sind und die id-Sequenzen in PostgreSQL korrekt hochgesetzt wurden.

Liest beide Datenbanken nur (keine Aenderung an der SQLite-Quelle). Der optionale
Sequenz-Check laeuft ausschliesslich gegen PostgreSQL.

Aufruf:
    backend/.venv/bin/python deploy/verify_migration.py \\
        --sqlite   /var/lib/mobilfunk/mobilfunk.db \\
        --postgres postgresql+psycopg://mobilfunk:PASSWORT@localhost:5432/mobilfunk

Exit-Code 0 = alles gleich, 1 = mindestens eine Abweichung.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, text

# Reihenfolge wie in migrate_to_postgres.py; alle Tabellen mit id-Spalte.
TABLES = ["users", "participants", "tasks", "unmatched_devices",
          "import_log", "audit_log"]


def _sqlite_url(path: str) -> str:
    return "sqlite:///" + str(Path(path).resolve()).replace("\\", "/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sqlite", required=True, help="Pfad zur mobilfunk.db")
    ap.add_argument("--postgres", required=True,
                    help="postgresql+psycopg://user:pw@host:5432/mobilfunk")
    args = ap.parse_args()

    src = create_engine(_sqlite_url(args.sqlite))
    dst = create_engine(args.postgres)

    print(f"{'Tabelle':22}{'SQLite':>10}{'PostgreSQL':>14}   Status")
    print("-" * 60)
    ok = True
    with src.connect() as s, dst.connect() as d:
        for t in TABLES:
            a = s.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            b = d.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            same = a == b
            ok = ok and same
            print(f"{t:22}{a:>10}{b:>14}   {'OK' if same else 'ABWEICHUNG'}")

        # Sequenz-Check: naechster id-Wert je Tabelle muss > max(id) sein,
        # sonst kollidiert der naechste Insert mit einer bestehenden Zeile.
        print("\nSequenz-Pruefung (PostgreSQL):")
        for t in TABLES:
            maxid = d.execute(text(f"SELECT COALESCE(max(id), 0) FROM {t}")).scalar()
            seqname = d.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": t}).scalar()
            if not seqname:
                print(f"  {t:22} keine id-Sequenz (uebersprungen)")
                continue
            nextval = d.execute(text(f"SELECT last_value FROM {seqname}")).scalar()
            seq_ok = nextval >= maxid
            ok = ok and seq_ok
            print(f"  {t:22} max(id)={maxid:<8} sequenz={nextval:<8} "
                  f"{'OK' if seq_ok else 'ZU NIEDRIG'}")

    print("\nERGEBNIS:", "ALLES GLEICH" if ok else "ABWEICHUNGEN GEFUNDEN")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
