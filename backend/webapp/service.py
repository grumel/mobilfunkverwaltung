"""
service.py – Gemeinsame Bausteine für die Web-Version:
Provider-Definitionen, Datums-Konvertierung, Protokoll-Helfer (import_log /
audit_log) und kleine Teilnehmer-Operationen. DB-neutral (SQLite/PostgreSQL).
"""

import json
import re
from datetime import datetime

from sqlalchemy import func

from webapp.models import Participant, ImportLog, AuditLog

# --- Provider (entspricht dem Desktop: ein Register je Teilnehmer) -----------
PROVIDERS = ["Vodafone", "Telekom", "O2", "Ohne SIM", "Frei"]
SLUG_TO_PROVIDER = {
    "vodafone": "Vodafone",
    "telekom":  "Telekom",
    "o2":       "O2",
    "ohnesim":  "Ohne SIM",
    "frei":     "Frei",
}
PROVIDER_TO_SLUG = {v: k for k, v in SLUG_TO_PROVIDER.items()}

# Für die Tab-Leiste (Reihenfolge)
NAV_PROVIDERS = [(PROVIDER_TO_SLUG[p], p) for p in PROVIDERS]

# --- Bearbeiten-Formular (Reihenfolge/Labels wie modules/ui_editor.py) -------
# (feldname, label, typ)  typ ∈ {"text", "date"}
FORM_FIELDS = [
    ("gsm",            "GSM-Nummer",       "text"),
    ("name",           "Name",             "text"),
    ("plant",          "Werk (Plant)",     "text"),
    ("konto",          "Konto",            "text"),
    ("telefon",        "Telefon (alt)",    "text"),
    ("tarif",          "Tarif",            "text"),
    ("sim_nummer",     "SIM-Seriennummer", "text"),
    ("rahmenvertrag",  "Rahmenvertrag",    "text"),
    ("startdatum",     "Erstaktivierung",  "date"),
    ("vertragsbeginn", "Vertragsbeginn",   "date"),
    ("vertragsende",   "Vertragsende",     "date"),
    ("kuendigung",     "Kündigung zu",     "date"),
    ("syno",           "Syno-Gerät 1",     "text"),
    ("start_syno",     "Syno 1 seit",      "date"),
    ("syno2",          "Syno-Gerät 2",     "text"),
    ("start_syno2",    "Syno 2 seit",      "date"),
]


# --- Datum -------------------------------------------------------------------
def to_display_date(value):
    """YYYY-MM-DD -> DD.MM.YYYY (für die Anzeige)."""
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def from_display_date(value):
    """DD.MM.YYYY -> YYYY-MM-DD (für die DB). Leeres Feld -> None."""
    v = (value or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return v  # Rohwert beibehalten (Desktop-Verhalten)


def is_valid_gsm(gsm) -> bool:
    cleaned = re.sub(r"[\s\-]", "", gsm or "")
    return bool(re.match(r"^(\+\d{9,14}|\d{10,15})$", cleaned))


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- Protokoll (wie modules/database.log_import / log_audit) ------------------
def log_import(db, aktion, details="", participant_id=None, quelle="Web"):
    db.add(ImportLog(zeitpunkt=now_str(), quelle=quelle, aktion=aktion,
                     details=details, participant_id=participant_id))


def log_audit(db, user, aktion, details="", table_name=None, record_id=None):
    db.add(AuditLog(zeitpunkt=now_str(),
                    user_id=(user or {}).get("id"),
                    username=(user or {}).get("username"),
                    aktion=aktion, details=details,
                    table_name=table_name, record_id=record_id))


# --- Ausführliches Änderungsprotokoll mit Einzel-Rücknahme -------------------

def participant_snapshot(p) -> dict:
    """Kompletter Zustand einer Teilnehmer-Zeile als serialisierbares Dict."""
    return {c.name: getattr(p, c.name) for c in Participant.__table__.columns}


def _describe_changes(changes: dict) -> str:
    """Menschenlesbarer Diff-Text, z. B. tarif: 'A' → 'B'; plant: — → 'Werk'."""
    def fmt(v):
        if v is None or v == "":
            return "—"
        return f"'{v}'"
    return "; ".join(f"{f}: {fmt(old)} → {fmt(new)}" for f, (old, new) in changes.items())


def diff_fields(before: dict, after: dict) -> dict:
    """Liefert {feld: [alt, neu]} nur für tatsächlich geänderte Felder."""
    changes = {}
    for f, new in after.items():
        old = before.get(f)
        if old != new:
            changes[f] = [old, new]
    return changes


def log_change(db, user, aktion, table_name, record_id, details=None,
               changes=None, snapshot=None, undo_op=None, revert_of_id=None):
    """Schreibt einen ausführlichen Audit-Eintrag.

    `undo_op` bestimmt, was das Rückgängigmachen dieses Eintrags tut:
      - "restore_fields": setzt die Alt-Werte aus `changes` zurück
      - "delete_row":     entfernt die Zeile `record_id`
      - "insert_row":     stellt die Zeile aus `snapshot` wieder her
    """
    if details is None:
        details = _describe_changes(changes) if changes else ""
    db.add(AuditLog(
        zeitpunkt=now_str(),
        user_id=(user or {}).get("id"),
        username=(user or {}).get("username"),
        aktion=aktion, details=details,
        table_name=table_name, record_id=record_id,
        changes=json.dumps(changes, ensure_ascii=False) if changes else None,
        snapshot=json.dumps(snapshot, ensure_ascii=False, default=str) if snapshot else None,
        undo_op=undo_op, revert_of_id=revert_of_id,
    ))


def next_master_id(db) -> int:
    return (db.query(func.max(Participant.master_id)).scalar() or 0) + 1
