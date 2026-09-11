"""
models.py – SQLAlchemy-Modelle, exakt passend zum bestehenden Schema
(modules/database.py). Datums-/Zeitfelder sind als Text gespeichert (ISO-Strings)
– das bleibt so, damit SQLite und PostgreSQL identisch funktionieren.
"""

from sqlalchemy import Column, Integer, Text

from webapp.db import Base


class Participant(Base):
    __tablename__ = "participants"
    id             = Column(Integer, primary_key=True)
    master_id      = Column(Integer)
    gsm            = Column(Text)
    pin            = Column(Text)   # SIM-PIN, unabhaengig von der GSM-Nummer
    name           = Column(Text)
    plant          = Column(Text)
    konto          = Column(Text)
    telefon        = Column(Text)
    tarif          = Column(Text)
    geraet         = Column(Text)
    startdatum     = Column(Text)
    sim_nummer     = Column(Text)
    kuendigung     = Column(Text)
    vertragsbeginn = Column(Text)
    vertragsende   = Column(Text)
    rahmenvertrag  = Column(Text)
    syno           = Column(Text)
    start_syno     = Column(Text)   # Synodatum (Gerät 1)
    imei           = Column(Text)   # IMEI-Nr. (Gerät 1)
    syno2          = Column(Text)
    start_syno2    = Column(Text)   # Synodatum (Gerät 2)
    imei2          = Column(Text)   # IMEI-Nr. (Gerät 2)
    bemerkung      = Column(Text)
    verified       = Column(Integer, default=1)
    created_at     = Column(Text)
    updated_at     = Column(Text)
    vodafone_aktiv = Column(Integer)
    pruefung_grund = Column(Text)
    provider       = Column(Text, default="Vodafone")
    overhead       = Column(Integer, default=0)
    archived       = Column(Integer, default=0)


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    username        = Column(Text, nullable=False, unique=True)
    password_hash   = Column(Text, nullable=False)
    role            = Column(Text, nullable=False, default="read")
    active          = Column(Integer, nullable=False, default=1)
    force_pw_change = Column(Integer, nullable=False, default=0)
    last_login      = Column(Text)
    created_at      = Column(Text)
    windows_login   = Column(Text)
    notes           = Column(Text)  # persönliches Notizfeld (Frontend-Knopf "Notizen")


class Task(Base):
    __tablename__ = "tasks"
    id             = Column(Integer, primary_key=True)
    participant_id = Column(Integer)
    name           = Column(Text)
    gsm            = Column(Text)
    plant          = Column(Text)
    konto          = Column(Text)
    tarif          = Column(Text)
    kommentar      = Column(Text)
    erledigt       = Column(Integer, default=0)
    created_by     = Column(Text)
    created_at     = Column(Text)
    done_at        = Column(Text)
    faellig_am     = Column(Text)
    prioritaet     = Column(Integer, default=0)


class UnmatchedDevice(Base):
    __tablename__ = "unmatched_devices"
    id          = Column(Integer, primary_key=True)
    quelle      = Column(Text, nullable=False)
    gsm         = Column(Text)
    benutzer    = Column(Text)
    geraet      = Column(Text)
    startdatum  = Column(Text)
    importdatum = Column(Text)


class ImportLog(Base):
    __tablename__ = "import_log"
    id             = Column(Integer, primary_key=True)
    zeitpunkt      = Column(Text)
    quelle         = Column(Text, nullable=False)
    aktion         = Column(Text, nullable=False)
    details        = Column(Text)
    participant_id = Column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id         = Column(Integer, primary_key=True)
    zeitpunkt  = Column(Text)
    user_id    = Column(Integer)
    username   = Column(Text)
    aktion     = Column(Text, nullable=False)
    details    = Column(Text)
    table_name = Column(Text)
    record_id  = Column(Integer)
    # Ausführliches Änderungsprotokoll mit Einzel-Rücknahme:
    changes      = Column(Text)     # JSON {feld: [alt, neu], …} – Feld-Diff
    snapshot     = Column(Text)     # JSON der kompletten Zeile (für Löschen/Wiederherstellen)
    undo_op      = Column(Text)     # was das Rückgängigmachen dieses Eintrags tut:
                                    # "restore_fields" | "delete_row" | "insert_row"
    reverted_at  = Column(Text)     # gesetzt, sobald dieser Eintrag zurückgenommen wurde
    revert_of_id = Column(Integer)  # ID des Eintrags, den dieser Eintrag zurücknimmt
