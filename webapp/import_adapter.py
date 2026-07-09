"""
import_adapter.py – SQLAlchemy-Adapter für den Excel-Import (Vodafone/Syno) auf
PostgreSQL (oder jeder anderen SQLAlchemy-Datenbank außer SQLite).

Hintergrund: modules/vodafone_import.py und modules/syno_import.py rufen ihre
Datenbankoperationen ausschließlich über ein injizierbares "db_module" auf
(Parameter db_module=). Der Standard ist modules.database (sqlite3, unverändert
– bleibt für die SQLite-Ablage exakt wie bisher). Dieser Adapter implementiert
dieselbe Funktionsoberfläche (gleiche Namen/Signaturen), aber auf einer
SQLAlchemy-Session – für den Fall, dass die konfigurierte DATABASE_URL nicht
SQLite ist. Damit landen Excel-Importe auch dann in der echten (Postgres-)
Datenbank, statt (falsch) in der lokalen SQLite-Datei.

Die "conn"-Parameter der aufrufenden Import-Logik sind hier tatsächlich
SQLAlchemy-Session-Objekte. Row-artige Rückgaben unterstützen __getitem__
(wie sqlite3.Row), damit dieselbe Import-Logik unverändert funktioniert.
"""

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import func

from webapp.db import SessionLocal
from webapp.models import Participant, ImportLog, UnmatchedDevice


class _Row:
    """Dünner Wrapper um ein ORM-Objekt für sqlite3.Row-artigen []-Zugriff."""
    __slots__ = ("_obj",)

    def __init__(self, obj):
        self._obj = obj

    def __getitem__(self, key):
        return getattr(self._obj, key)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Transaktionen
# ---------------------------------------------------------------------------

@contextmanager
def transaction():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def dry_run_transaction():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# participants
# ---------------------------------------------------------------------------

def clean_vodafone_plant_warnings(session) -> int:
    rows = (session.query(Participant)
            .filter(Participant.bemerkung.like("%[Vodafone-Import]%")).all())
    cleaned = 0
    for row in rows:
        parts = [p.strip() for p in (row.bemerkung or "").split("|")]
        parts = [p for p in parts if "[Vodafone-Import]" not in p]
        new_bem = " | ".join(parts).strip(" |") or None
        if new_bem != row.bemerkung:
            row.bemerkung = new_bem
            row.updated_at = _now()
            cleaned += 1
    return cleaned


def reset_vodafone_aktiv(session) -> None:
    session.query(Participant).update({"vodafone_aktiv": 0})


def set_vodafone_aktiv(session, pid: int) -> None:
    p = session.get(Participant, pid)
    if p is not None:
        p.vodafone_aktiv = 1


def get_participant_by_gsm(session, gsm: str):
    row = session.query(Participant).filter(Participant.gsm == gsm).first()
    return _Row(row) if row is not None else None


def get_participant_by_id(session, pid: int):
    row = session.get(Participant, pid)
    return _Row(row) if row is not None else None


def get_all_participants(session, provider=None):
    q = session.query(Participant)
    if provider is not None:
        q = q.filter(func.coalesce(Participant.provider, "Vodafone") == provider)
    return [_Row(r) for r in q.order_by(Participant.name).all()]


def _next_master_id(session) -> int:
    return (session.query(func.max(Participant.master_id)).scalar() or 0) + 1


def insert_participant(session, data: dict) -> int:
    p = Participant(
        master_id=data.get("master_id") or _next_master_id(session),
        gsm=data.get("gsm"), name=data.get("name"), plant=data.get("plant"),
        konto=data.get("konto"), telefon=data.get("telefon"), tarif=data.get("tarif"),
        geraet=data.get("geraet"), startdatum=data.get("startdatum"),
        sim_nummer=data.get("sim_nummer"), kuendigung=data.get("kuendigung"),
        vertragsbeginn=data.get("vertragsbeginn"), vertragsende=data.get("vertragsende"),
        rahmenvertrag=data.get("rahmenvertrag"), syno=data.get("syno"),
        start_syno=data.get("start_syno"), syno2=data.get("syno2"),
        start_syno2=data.get("start_syno2"), bemerkung=data.get("bemerkung"),
        verified=data.get("verified", 1), pruefung_grund=data.get("pruefung_grund"),
        vodafone_aktiv=data.get("vodafone_aktiv"),
        provider=data.get("provider") or "Vodafone",
        created_at=_now(), updated_at=_now(),
    )
    session.add(p)
    session.flush()
    return p.id


def update_participant_fields(session, pid: int, fields: dict) -> None:
    if not fields:
        return
    p = session.get(Participant, pid)
    if p is None:
        return
    for k, v in fields.items():
        setattr(p, k, v)
    p.updated_at = _now()


# ---------------------------------------------------------------------------
# unmatched_devices
# ---------------------------------------------------------------------------

def insert_unmatched_device(session, data: dict) -> int:
    u = UnmatchedDevice(
        quelle=data.get("quelle"), gsm=data.get("gsm"), benutzer=data.get("benutzer"),
        geraet=data.get("geraet"), startdatum=data.get("startdatum"),
        importdatum=_now(),
    )
    session.add(u)
    session.flush()
    return u.id


# ---------------------------------------------------------------------------
# import_log
# ---------------------------------------------------------------------------

def log_import(session, quelle: str, aktion: str, details: str = "",
                participant_id=None) -> None:
    session.add(ImportLog(zeitpunkt=_now(), quelle=quelle, aktion=aktion,
                          details=details, participant_id=participant_id))


# ---------------------------------------------------------------------------
# Syno-Geräte-Slots (identische Logik wie modules/database.assign_syno_device)
# ---------------------------------------------------------------------------

def assign_syno_device(session, pid: int, geraet, start) -> str:
    if not geraet:
        return "dup"
    row = get_participant_by_id(session, pid)
    if row is None:
        return "full"
    norm = geraet.strip().casefold()
    s1 = (row["syno"] or "").strip()
    s2 = (row["syno2"] or "").strip()
    if s1.casefold() == norm or s2.casefold() == norm:
        return "dup"
    if not s1:
        update_participant_fields(session, pid, {"syno": geraet, "start_syno": start})
        return "filled"
    if not s2:
        update_participant_fields(session, pid, {"syno2": geraet, "start_syno2": start})
        return "filled"
    return "full"
