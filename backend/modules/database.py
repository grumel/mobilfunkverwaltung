"""
database.py – Zentrales Datenbankmodul für die Mobilfunkverwaltung.

Verantwortlichkeiten:
- Datenbankverbindung verwalten
- Schema initialisieren und migrieren
- CRUD-Operationen für alle Tabellen kapseln
- Keine Geschäftslogik; nur Datenzugriff
"""

import json
import os
import socket
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from modules.paths import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH  = DATA_DIR / "mobilfunk.db"
LOCK_PATH = DB_PATH.with_suffix(".lock")


# ---------------------------------------------------------------------------
# Lock-Datei (Schutz bei OneDrive/Netzwerk-Ablage)
# ---------------------------------------------------------------------------

def acquire_lock(username: str) -> dict | None:
    """Versucht die Lock-Datei zu setzen.
    Gibt None zurück wenn erfolgreich, sonst dict mit Infos des aktuellen Inhabers."""
    if LOCK_PATH.exists():
        try:
            info = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            # Prüfen ob der Prozess noch läuft (nur lokal aussagekräftig)
            age_seconds = (datetime.now() - datetime.fromisoformat(info["seit"])).total_seconds()
            # Lock älter als 4 Stunden → vermutlich verwaist
            if age_seconds > 14400:
                logger.warning("Verwaiste Lock-Datei gefunden (%.0f h alt) – wird übernommen.", age_seconds / 3600)
                _write_lock(username)
                return None
            return info
        except Exception:
            pass  # Beschädigte Lock-Datei → überschreiben
    _write_lock(username)
    return None


def release_lock() -> None:
    """Löscht die Lock-Datei beim Beenden der App."""
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception as exc:
        logger.warning("Lock-Datei konnte nicht gelöscht werden: %s", exc)


def _write_lock(username: str) -> None:
    info = {
        "benutzer":  username,
        "rechner":   socket.gethostname(),
        "pid":       os.getpid(),
        "seit":      datetime.now().isoformat(timespec="seconds"),
    }
    LOCK_PATH.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Verbindung
# ---------------------------------------------------------------------------

def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def read_connection(path: Path = DB_PATH):
    """Kontextmanager für lesende Zugriffe – schließt die Verbindung garantiert."""
    conn = get_connection(path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(path: Path = DB_PATH):
    """Liefert eine Verbindung; commit bei Erfolg, rollback bei Fehler."""
    conn = get_connection(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def dry_run_transaction(path: Path = DB_PATH):
    """Wie transaction(), aber immer rollback – für Import-Vorschau."""
    conn = get_connection(path)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'read',
    active          INTEGER NOT NULL DEFAULT 1,
    force_pw_change INTEGER NOT NULL DEFAULT 0,
    last_login      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    zeitpunkt      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    user_id        INTEGER,
    username       TEXT,
    aktion         TEXT    NOT NULL,
    details        TEXT,
    table_name     TEXT,
    record_id      INTEGER
);

CREATE TABLE IF NOT EXISTS participants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id       INTEGER,
    gsm             TEXT,
    name            TEXT,
    plant           TEXT,
    konto           TEXT,
    telefon         TEXT,
    tarif           TEXT,
    geraet          TEXT,
    startdatum      TEXT,
    sim_nummer      TEXT,
    kuendigung      TEXT,
    vertragsbeginn  TEXT,
    vertragsende    TEXT,
    rahmenvertrag   TEXT,
    syno            TEXT,
    start_syno      TEXT,
    syno2           TEXT,
    start_syno2     TEXT,
    bemerkung       TEXT,
    verified        INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Eindeutiger Index auf gsm; leere Strings und NULL ausgenommen
CREATE UNIQUE INDEX IF NOT EXISTS uix_participants_gsm
    ON participants (gsm)
    WHERE gsm IS NOT NULL AND gsm != '';

CREATE TABLE IF NOT EXISTS unmatched_devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    quelle      TEXT    NOT NULL,
    gsm         TEXT,
    benutzer    TEXT,
    geraet      TEXT,
    startdatum  TEXT,
    importdatum TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS import_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    zeitpunkt TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    quelle    TEXT NOT NULL,
    aktion    TEXT NOT NULL,
    details   TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id INTEGER,
    name           TEXT,
    gsm            TEXT,
    plant          TEXT,
    konto          TEXT,
    tarif          TEXT,
    kommentar      TEXT,
    erledigt       INTEGER NOT NULL DEFAULT 0,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    done_at        TEXT,
    faellig_am     TEXT,
    prioritaet     INTEGER NOT NULL DEFAULT 0
);
"""


def create_backup(path: Path = DB_PATH, max_keep: int = 10) -> Path:
    """Erstellt eine datierte Kopie der Datenbank und behält nur die letzten
    max_keep regulären Backups. Vor-Restore-Sicherungen ('…_vor-restore_…')
    unterliegen der Rotation NICHT – sie sind Sicherheitsnetze und bleiben."""
    import shutil
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = backup_dir / f"{path.stem}_{ts}.db"
    shutil.copy2(str(path), str(dest))
    logger.info("Backup erstellt: %s", dest)
    # Nur reguläre Backups rotieren (vor-restore ausnehmen)
    existing = sorted(f for f in backup_dir.glob(f"{path.stem}_*.db")
                      if "vor-restore" not in f.name)
    for old in existing[:-max_keep]:
        old.unlink(missing_ok=True)
        logger.info("Altes Backup gelöscht: %s", old)
    return dest


def list_backups(path: Path = DB_PATH) -> list:
    """Vorhandene Backups (neueste zuerst) als Liste von (Path, Größe, Zeitpunkt)."""
    backup_dir = path.parent / "backups"
    if not backup_dir.exists():
        return []
    out = []
    for f in sorted(backup_dir.glob(f"{path.stem}_*.db"), reverse=True):
        try:
            st = f.stat()
            out.append((f, st.st_size, datetime.fromtimestamp(st.st_mtime)))
        except OSError:
            continue
    return out


def restore_backup(backup_path: Path, path: Path = DB_PATH) -> Path:
    """Spielt ein Backup zurück. Sichert vorher den AKTUELLEN Stand
    (Datei mit Präfix 'vor-restore_'), damit die Wiederherstellung selbst
    rückgängig gemacht werden kann. Gibt die Sicherung des vorigen Stands zurück."""
    import shutil
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup nicht gefunden: {backup_path}")
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safety = backup_dir / f"{path.stem}_vor-restore_{ts}.db"
    if path.exists():
        shutil.copy2(str(path), str(safety))
        logger.info("Vor-Restore-Sicherung erstellt: %s", safety)
    shutil.copy2(str(backup_path), str(path))
    logger.info("Backup zurückgespielt: %s → %s", backup_path, path)
    return safety


def data_quality_check(conn: sqlite3.Connection, konto_plant: dict | None = None) -> dict:
    """Prüft den Bestand auf typische Datenprobleme.

    Rückgabe: dict {Kategorie: [Zeilen …]} – jede Zeile ist ein sqlite3.Row
    des Teilnehmers, ergänzt (als eigener Schlüssel via dict) ist nicht nötig,
    die Kategorie steckt im dict-Schlüssel.
    """
    from datetime import date
    today = date.today().isoformat()
    konto_plant = konto_plant or {}
    parts = conn.execute("SELECT * FROM participants").fetchall()

    def is_placeholder_gsm(g: str | None) -> bool:
        if not g:
            return False
        s = str(g).strip()
        if any(c.isalpha() for c in s):          # "Teams only", "keine SIM" …
            return True
        digits = "".join(ch for ch in s if ch.isdigit())
        if digits in ("123456789", "17200000") or len(digits) < 6:
            return True
        return False

    konto_werk_mismatch = []
    placeholder_gsm     = []
    expired_active      = []
    device_no_gsm       = []
    ohne_werk           = []

    # Provider, bei denen eine SIM/GSM erwartet wird (bei "Ohne SIM"/"Frei" nicht)
    sim_provider = {"Vodafone", "Telekom", "O2"}

    for p in parts:
        provider = (p["provider"] or "Vodafone").strip()
        konto = (p["konto"] or "").strip()
        plant = (p["plant"] or "").strip()
        gsm   = (p["gsm"] or "").strip()

        if konto and konto in konto_plant and plant and konto_plant[konto] != plant:
            konto_werk_mismatch.append(p)
        if provider in sim_provider and is_placeholder_gsm(gsm):
            placeholder_gsm.append(p)
        ende = (p["vertragsende"] or "").strip()
        if ende and ende < today and (p["vodafone_aktiv"] == 1):
            expired_active.append(p)
        has_dev = (p["syno"] or "").strip() or (p["syno2"] or "").strip()
        if provider in sim_provider and has_dev and not gsm:
            device_no_gsm.append(p)
        if not plant:
            ohne_werk.append(p)

    return {
        "Konto passt nicht zum Werk": konto_werk_mismatch,
        "Platzhalter-/ungültige Nummer (SIM-Provider)": placeholder_gsm,
        "Vertrag abgelaufen, aber aktiv": expired_active,
        "Gerät ohne GSM-Nummer (SIM-Provider)": device_no_gsm,
        "Kein Werk hinterlegt": ohne_werk,
    }


def init_db(path: Path = DB_PATH) -> None:
    """Erstellt alle Tabellen, falls sie noch nicht existieren, und migriert das Schema."""
    with transaction(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
    logger.info("Datenbank initialisiert: %s", path)


def _migrate(conn: sqlite3.Connection) -> None:
    """Fügt fehlende Spalten hinzu (idempotent)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(participants)").fetchall()}
    if "vodafone_aktiv" not in existing:
        conn.execute("ALTER TABLE participants ADD COLUMN vodafone_aktiv INTEGER")
        logger.info("Migration: Spalte vodafone_aktiv hinzugefügt")
    if "pruefung_grund" not in existing:
        conn.execute("ALTER TABLE participants ADD COLUMN pruefung_grund TEXT")
        logger.info("Migration: Spalte pruefung_grund hinzugefügt")
    if "provider" not in existing:
        conn.execute("ALTER TABLE participants ADD COLUMN provider TEXT NOT NULL DEFAULT 'Vodafone'")
        logger.info("Migration: Spalte provider hinzugefügt")

    if "in_register" in existing:
        # Register-Konzept abgeschafft (Juli 2026)
        conn.execute("ALTER TABLE participants DROP COLUMN in_register")
        logger.info("Migration: Spalte in_register entfernt")

    if "syno2" not in existing:
        conn.execute("ALTER TABLE participants ADD COLUMN syno2 TEXT")
        conn.execute("ALTER TABLE participants ADD COLUMN start_syno2 TEXT")
        logger.info("Migration: Spalten syno2/start_syno2 hinzugefügt")

    log_cols = {row[1] for row in conn.execute("PRAGMA table_info(import_log)").fetchall()}
    if "participant_id" not in log_cols:
        conn.execute("ALTER TABLE import_log ADD COLUMN participant_id INTEGER")
        logger.info("Migration: Spalte participant_id in import_log hinzugefügt")

    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "windows_login" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN windows_login TEXT")
        logger.info("Migration: Spalte windows_login in users hinzugefügt")

    task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if task_cols and "faellig_am" not in task_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN faellig_am TEXT")
        conn.execute("ALTER TABLE tasks ADD COLUMN prioritaet INTEGER NOT NULL DEFAULT 0")
        logger.info("Migration: Spalten faellig_am/prioritaet in tasks hinzugefügt")


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# participants – Schreiben
# ---------------------------------------------------------------------------

_PARTICIPANT_FIELDS = [
    "master_id", "gsm", "name", "plant", "konto", "telefon", "tarif", "geraet",
    "startdatum", "sim_nummer", "kuendigung", "vertragsbeginn",
    "vertragsende", "rahmenvertrag", "syno", "start_syno",
    "syno2", "start_syno2",
    "bemerkung", "verified", "pruefung_grund",
]


def _next_master_id(conn: sqlite3.Connection) -> int:
    """Nächste freie laufende Nummer (Master-Nr.) – bestehende Nummern bleiben unverändert."""
    return (conn.execute("SELECT MAX(master_id) FROM participants").fetchone()[0] or 0) + 1


def insert_participant(conn: sqlite3.Connection, data: dict) -> int:
    values = {f: data.get(f) for f in _PARTICIPANT_FIELDS}
    if not values.get("master_id"):
        values["master_id"] = _next_master_id(conn)
    values["created_at"] = _now()
    values["updated_at"] = _now()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(f":{k}" for k in values.keys())
    cur = conn.execute(
        f"INSERT INTO participants ({cols}) VALUES ({placeholders})", values
    )
    return cur.lastrowid


def update_participant_fields(conn: sqlite3.Connection, pid: int, fields: dict) -> None:
    """Aktualisiert gezielt einzelne Felder eines Teilnehmers."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = dict(fields)
    params["id"] = pid
    params["updated_at"] = _now()
    conn.execute(
        f"UPDATE participants SET {set_clause}, updated_at = :updated_at WHERE id = :id",
        params,
    )


def delete_all_participants(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM participants")
    return cur.rowcount


def delete_participant(conn: sqlite3.Connection, pid: int) -> None:
    conn.execute("DELETE FROM participants WHERE id = ?", (pid,))


def set_verified(conn: sqlite3.Connection, pid: int, value: int) -> None:
    conn.execute(
        "UPDATE participants SET verified = ?, updated_at = ? WHERE id = ?",
        (value, _now(), pid),
    )


def clean_vodafone_plant_warnings(conn: sqlite3.Connection) -> int:
    """Entfernt veraltete Plant-Warnungen aus dem Vodafone-Import aus allen Bemerkungen."""
    rows = conn.execute(
        "SELECT id, bemerkung FROM participants WHERE bemerkung LIKE '%[Vodafone-Import]%'"
    ).fetchall()
    cleaned = 0
    for row in rows:
        parts = [p.strip() for p in (row["bemerkung"] or "").split("|")]
        parts = [p for p in parts if "[Vodafone-Import]" not in p]
        new_bem = " | ".join(parts).strip(" |") or None
        if new_bem != row["bemerkung"]:
            conn.execute(
                "UPDATE participants SET bemerkung = ?, updated_at = ? WHERE id = ?",
                (new_bem, _now(), row["id"]),
            )
            cleaned += 1
    return cleaned


def reset_vodafone_aktiv(conn: sqlite3.Connection) -> None:
    """Markiert alle Teilnehmer als 'nicht in Vodafone' – vor dem Vodafone-Import aufrufen."""
    conn.execute("UPDATE participants SET vodafone_aktiv = 0")


def set_vodafone_aktiv(conn: sqlite3.Connection, pid: int) -> None:
    """Markiert einen Teilnehmer als 'in Vodafone vorhanden'."""
    conn.execute(
        "UPDATE participants SET vodafone_aktiv = 1 WHERE id = ?", (pid,)
    )


# ---------------------------------------------------------------------------
# participants – Lesen
# ---------------------------------------------------------------------------

def get_incomplete_participants(conn: sqlite3.Connection) -> list:
    """Teilnehmer mit fehlenden Pflichtfeldern (GSM, Werk oder Konto)."""
    return conn.execute(
        """SELECT * FROM participants
           WHERE ((gsm IS NULL OR gsm = '')
              OR (plant IS NULL OR plant = '')
              OR (konto IS NULL OR konto = ''))
           ORDER BY name"""
    ).fetchall()


def get_werk_overview(conn: sqlite3.Connection) -> list:
    """Gibt je Werk: Gesamt, Ungeprüft, Ohne Vodafone."""
    return conn.execute(
        """SELECT
               COALESCE(plant, '(kein Werk)') AS werk,
               COUNT(*)                        AS gesamt,
               SUM(CASE WHEN verified = 0 THEN 1 ELSE 0 END)         AS ungeprueft,
               SUM(CASE WHEN vodafone_aktiv = 0 THEN 1 ELSE 0 END)   AS ohne_vodafone
           FROM participants
           GROUP BY COALESCE(plant, '(kein Werk)')
           ORDER BY werk"""
    ).fetchall()


def get_all_participants(conn: sqlite3.Connection, provider: str | None = "Vodafone") -> list:
    """provider=None liefert Teilnehmer aller Provider (z. B. fürs Import-Matching)."""
    if provider is None:
        return conn.execute("SELECT * FROM participants ORDER BY name").fetchall()
    return conn.execute(
        "SELECT * FROM participants WHERE COALESCE(provider,'Vodafone') = ? ORDER BY name",
        (provider,),
    ).fetchall()


def set_provider(conn: sqlite3.Connection, pid: int, provider: str) -> None:
    conn.execute(
        "UPDATE participants SET provider = ?, updated_at = ? WHERE id = ?",
        (provider, _now(), pid),
    )


def get_participant_by_id(conn: sqlite3.Connection, pid: int):
    return conn.execute(
        "SELECT * FROM participants WHERE id = ?", (pid,)
    ).fetchone()


def get_participant_by_gsm(conn: sqlite3.Connection, gsm: str):
    return conn.execute(
        "SELECT * FROM participants WHERE gsm = ?", (gsm,)
    ).fetchone()


def assign_syno_device(conn: sqlite3.Connection, pid: int,
                       geraet: str | None, start: str | None) -> str:
    """Trägt ein Syno-Gerät in den ersten freien Slot (syno / syno2) ein.

    Verhalten ("nur leere Slots füllen"):
      - Gerät schon in einem Slot vorhanden  -> "dup"  (nichts geändert)
      - freier Slot vorhanden                -> "filled" (dort eingetragen)
      - beide Slots mit anderen Geräten belegt -> "full" (nichts geändert)

    Liest den Datensatz frisch aus der DB, damit mehrere Zeilen desselben
    Imports (2 Geräte, gleiche Nummer) korrekt Slot 1 und Slot 2 füllen.
    """
    if not geraet:
        return "dup"
    row = get_participant_by_id(conn, pid)
    if row is None:
        return "full"
    norm = geraet.strip().casefold()
    s1 = (row["syno"] or "").strip()
    s2 = (row["syno2"] or "").strip()
    if s1.casefold() == norm or s2.casefold() == norm:
        return "dup"
    if not s1:
        update_participant_fields(conn, pid, {"syno": geraet, "start_syno": start})
        return "filled"
    if not s2:
        update_participant_fields(conn, pid, {"syno2": geraet, "start_syno2": start})
        return "filled"
    return "full"


def get_unverified_participants(conn: sqlite3.Connection, provider: str = "Vodafone") -> list:
    return conn.execute(
        "SELECT * FROM participants WHERE verified = 0 AND COALESCE(provider,'Vodafone') = ? ORDER BY name",
        (provider,),
    ).fetchall()


def get_neuvertraege(conn: sqlite3.Connection) -> list:
    """Teilnehmer, die über das Neuvertrag-Register bestellt wurden."""
    return conn.execute(
        "SELECT * FROM participants WHERE pruefung_grund LIKE 'Neuvertrag%' "
        "ORDER BY created_at DESC"
    ).fetchall()


def search_participants(conn: sqlite3.Connection, term: str) -> list:
    like = f"%{term}%"
    return conn.execute(
        """
        SELECT * FROM participants
        WHERE name LIKE :t OR gsm LIKE :t OR plant LIKE :t
           OR konto LIKE :t OR tarif LIKE :t OR bemerkung LIKE :t
        ORDER BY name
        """,
        {"t": like},
    ).fetchall()


# ---------------------------------------------------------------------------
# unmatched_devices
# ---------------------------------------------------------------------------

def insert_unmatched_device(conn: sqlite3.Connection, data: dict) -> int:
    fields = ["quelle", "gsm", "benutzer", "geraet", "startdatum"]
    values = {f: data.get(f) for f in fields}
    values["importdatum"] = _now()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(f":{k}" for k in values.keys())
    cur = conn.execute(
        f"INSERT INTO unmatched_devices ({cols}) VALUES ({placeholders})", values
    )
    return cur.lastrowid


def get_all_unmatched(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM unmatched_devices ORDER BY importdatum DESC"
    ).fetchall()


def delete_unmatched_device(conn: sqlite3.Connection, uid: int) -> None:
    conn.execute("DELETE FROM unmatched_devices WHERE id = ?", (uid,))


# ---------------------------------------------------------------------------
# import_log
# ---------------------------------------------------------------------------

def log_import(
    conn: sqlite3.Connection, quelle: str, aktion: str,
    details: str = "", participant_id: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO import_log (quelle, aktion, details, participant_id) VALUES (?, ?, ?, ?)",
        (quelle, aktion, details, participant_id),
    )


def get_import_log(conn: sqlite3.Connection, limit: int = 2000) -> list:
    return conn.execute(
        "SELECT * FROM import_log ORDER BY zeitpunkt DESC LIMIT ?", (limit,)
    ).fetchall()


# ---------------------------------------------------------------------------
# tasks – Aufgabenverwaltung
# ---------------------------------------------------------------------------

def find_unique_participant(conn: sqlite3.Connection, gsm: str | None, name: str | None):
    """Sucht einen eindeutigen Teilnehmer per GSM (bevorzugt) oder Namen.

    Gibt die Teilnehmer-Row zurück, wenn genau ein Treffer existiert – sonst
    None (kein oder mehrdeutiger Treffer). Für die automatische Verknüpfung von
    Aufgaben aus 'Nicht zugeordnet'.
    """
    from modules.utils import normalize_name, normalize_gsm
    gg = normalize_gsm(gsm or "")
    if gg:
        hits = conn.execute("SELECT * FROM participants WHERE gsm = ?", (gg,)).fetchall()
        if len(hits) == 1:
            return hits[0]
    nn = normalize_name(name or "")
    if nn:
        hits = [p for p in conn.execute("SELECT * FROM participants").fetchall()
                if normalize_name(p["name"]) == nn]
        if len(hits) == 1:
            return hits[0]
    return None


def create_task(conn: sqlite3.Connection, participant, kommentar: str,
                created_by: str | None = None,
                faellig_am: str | None = None, prioritaet: int = 0) -> int:
    """Legt eine Aufgabe an und übernimmt die Stammdaten des Teilnehmers."""
    cur = conn.execute(
        """INSERT INTO tasks (participant_id, name, gsm, plant, konto, tarif,
                              kommentar, created_by, faellig_am, prioritaet)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (participant["id"], participant["name"], participant["gsm"],
         participant["plant"], participant["konto"], participant["tarif"],
         kommentar, created_by, faellig_am or None, int(prioritaet or 0)),
    )
    return cur.lastrowid


def update_task_details(conn: sqlite3.Connection, task_id: int,
                        kommentar: str, faellig_am: str | None,
                        prioritaet: int) -> None:
    conn.execute(
        "UPDATE tasks SET kommentar = ?, faellig_am = ?, prioritaet = ? WHERE id = ?",
        (kommentar, faellig_am or None, int(prioritaet or 0), task_id),
    )


def get_tasks(conn: sqlite3.Connection, include_done: bool = False) -> list:
    where = "" if include_done else "WHERE erledigt = 0"
    # Offene zuerst; dann überfällige/dringende oben, dann nach Fälligkeit
    return conn.execute(
        f"""SELECT * FROM tasks {where}
            ORDER BY erledigt,
                     prioritaet DESC,
                     CASE WHEN faellig_am IS NULL OR faellig_am = '' THEN 1 ELSE 0 END,
                     faellig_am,
                     created_at DESC"""
    ).fetchall()


def count_open_tasks(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(id) FROM tasks WHERE erledigt = 0").fetchone()[0]


def get_participants_with_open_tasks(conn: sqlite3.Connection) -> list:
    """Teilnehmer, die mindestens eine offene Aufgabe haben (für Tab-Suchen)."""
    return conn.execute(
        """SELECT DISTINCT p.* FROM participants p
           JOIN tasks t ON t.participant_id = p.id
           WHERE t.erledigt = 0"""
    ).fetchall()


def get_open_task_participant_ids(conn: sqlite3.Connection) -> set:
    """IDs aller Teilnehmer mit mindestens einer offenen Aufgabe.

    Aufgaben ohne direkten participant_id-Bezug (z. B. aus 'Nicht zugeordnet'
    angelegt) werden zusätzlich per eindeutigem GSM- oder Namens-Treffer einem
    Teilnehmer zugeordnet, damit auch dessen Zeile markiert wird.
    """
    from modules.utils import normalize_name, normalize_gsm
    ids = {r[0] for r in conn.execute(
        "SELECT DISTINCT participant_id FROM tasks "
        "WHERE erledigt = 0 AND participant_id IS NOT NULL"
    ).fetchall()}
    orphans = conn.execute(
        "SELECT name, gsm FROM tasks WHERE erledigt = 0 AND participant_id IS NULL"
    ).fetchall()
    if orphans:
        by_name: dict = {}
        by_gsm: dict = {}
        for p in conn.execute("SELECT id, name, gsm FROM participants").fetchall():
            nn = normalize_name(p["name"])
            if nn:
                by_name.setdefault(nn, []).append(p["id"])
            gg = normalize_gsm(p["gsm"] or "")
            if gg:
                by_gsm.setdefault(gg, []).append(p["id"])
        for t in orphans:
            gg = normalize_gsm(t["gsm"] or "")
            match = by_gsm.get(gg) if gg else None
            if not match:
                nn = normalize_name(t["name"])
                match = by_name.get(nn) if nn else None
            if match and len(match) == 1:   # nur eindeutige Treffer markieren
                ids.add(match[0])
    return ids


def set_task_done(conn: sqlite3.Connection, task_id: int, done: bool) -> None:
    conn.execute(
        "UPDATE tasks SET erledigt = ?, done_at = ? WHERE id = ?",
        (1 if done else 0, _now() if done else None, task_id),
    )


def delete_task(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def get_participant_history(conn: sqlite3.Connection, pid: int) -> list:
    """Alle Logeinträge zu einem bestimmten Teilnehmer."""
    return conn.execute(
        """SELECT zeitpunkt, quelle, aktion, details
           FROM import_log
           WHERE participant_id = ?
           ORDER BY zeitpunkt DESC""",
        (pid,),
    ).fetchall()


def get_duplicates_detail(conn: sqlite3.Connection) -> list:
    """Alle Teilnehmer, deren Name (normalisiert) mehrfach vorkommt."""
    return conn.execute(
        """SELECT * FROM participants
           WHERE lower(trim(name)) IN (
               SELECT lower(trim(name)) FROM participants
               WHERE name IS NOT NULL AND name != ''
               GROUP BY lower(trim(name))
               HAVING COUNT(id) > 1
           )
           ORDER BY lower(trim(name)), id"""
    ).fetchall()


def get_stats(conn: sqlite3.Connection) -> dict:
    """Kennzahlen für das Statistik-Dashboard."""
    from datetime import date, timedelta
    today     = date.today().isoformat()
    in_30     = (date.today() + timedelta(days=30)).isoformat()
    in_60     = (date.today() + timedelta(days=60)).isoformat()
    in_90     = (date.today() + timedelta(days=90)).isoformat()

    def scalar(sql, params=()):
        return conn.execute(sql, params).fetchone()[0] or 0

    return {
        "total":        scalar("SELECT COUNT(id) FROM participants"),
        "verified":     scalar("SELECT COUNT(id) FROM participants WHERE verified = 1"),
        "zur_pruefung": scalar("SELECT COUNT(id) FROM participants WHERE verified = 0"),
        "ohne_gsm":     scalar("SELECT COUNT(id) FROM participants WHERE gsm IS NULL OR gsm=''"),
        "mit_syno":     scalar("SELECT COUNT(id) FROM participants WHERE (syno IS NOT NULL AND syno != '') OR (syno2 IS NOT NULL AND syno2 != '')"),
        "abgelaufen":   scalar("SELECT COUNT(id) FROM participants WHERE vertragsende < ?", (today,)),
        "ablauf_30":    scalar("SELECT COUNT(id) FROM participants WHERE vertragsende>=? AND vertragsende<=?", (today, in_30)),
        "ablauf_60":    scalar("SELECT COUNT(id) FROM participants WHERE vertragsende>? AND vertragsende<=?", (in_30, in_60)),
        "ablauf_90":    scalar("SELECT COUNT(id) FROM participants WHERE vertragsende>? AND vertragsende<=?", (in_60, in_90)),
        "werke":        conn.execute(
            """SELECT COALESCE(plant,'(kein Werk)') AS werk, COUNT(id) AS n
               FROM participants GROUP BY COALESCE(plant,'(kein Werk)') ORDER BY n DESC"""
        ).fetchall(),
        "ablauf_liste": conn.execute(
            """SELECT name, gsm, plant, vertragsende, provider FROM participants
               WHERE vertragsende >= ? AND vertragsende <= ?
               ORDER BY vertragsende""",
            (today, in_90),
        ).fetchall(),
    }


def get_expired_contracts(conn: sqlite3.Connection) -> list:
    """Alle Teilnehmer mit abgelaufenem Vertragsende (über alle Provider)."""
    from datetime import date
    today = date.today().isoformat()
    return conn.execute(
        """SELECT * FROM participants
           WHERE vertragsende IS NOT NULL AND vertragsende != '' AND vertragsende < ?
           ORDER BY vertragsende DESC""",
        (today,),
    ).fetchall()


def search_global(conn: sqlite3.Connection, term: str) -> dict:
    """Durchsucht alle relevanten Tabellen nach term.

    Rückgabe: dict mit Kategorien als Schlüssel, Listen von sqlite3.Row als Werte.
    """
    like = f"%{term}%"
    base = """
        AND (name LIKE :t OR gsm LIKE :t OR plant LIKE :t
          OR konto LIKE :t OR tarif LIKE :t OR bemerkung LIKE :t
          OR sim_nummer LIKE :t OR syno LIKE :t OR syno2 LIKE :t)
    """
    participants = conn.execute(
        f"SELECT * FROM participants WHERE COALESCE(provider,'Vodafone')='Vodafone' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    telekom = conn.execute(
        f"SELECT * FROM participants WHERE provider='Telekom' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    frei = conn.execute(
        f"SELECT * FROM participants WHERE provider='Frei' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    o2 = conn.execute(
        f"SELECT * FROM participants WHERE provider='O2' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    ohnesim = conn.execute(
        f"SELECT * FROM participants WHERE provider='Ohne SIM' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    unverified = conn.execute(
        f"SELECT * FROM participants WHERE verified=0 AND COALESCE(provider,'Vodafone')='Vodafone' {base} ORDER BY name",
        {"t": like},
    ).fetchall()
    unmatched = conn.execute(
        """SELECT * FROM unmatched_devices
           WHERE gsm LIKE :t OR benutzer LIKE :t OR geraet LIKE :t
           ORDER BY importdatum DESC""",
        {"t": like},
    ).fetchall()
    return {
        "Teilnehmer":       participants,
        "Telekom":          telekom,
        "O2":               o2,
        "Ohne SIM":         ohnesim,
        "Frei":             frei,
        "Offene Prüfungen": unverified,
        "Nicht zugeordnet": unmatched,
    }


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def get_all_users(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM users ORDER BY username"
    ).fetchall()


def get_user_by_id(conn: sqlite3.Connection, uid: int):
    return conn.execute(
        "SELECT * FROM users WHERE id = ?", (uid,)
    ).fetchone()


def get_user_by_name(conn: sqlite3.Connection, username: str):
    return conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def get_user_by_windows_login(conn: sqlite3.Connection, winlogin: str):
    """Aktiver Benutzer, dessen Windows-Anmeldename passt (Groß/Klein egal)."""
    if not winlogin:
        return None
    return conn.execute(
        "SELECT * FROM users WHERE lower(windows_login) = lower(?) AND active = 1",
        (winlogin.strip(),),
    ).fetchone()


def create_user(conn: sqlite3.Connection, data: dict) -> int:
    fields = ["username", "password_hash", "role", "active", "force_pw_change",
              "windows_login"]
    values = {f: data.get(f) for f in fields}
    values["created_at"] = _now()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(f":{k}" for k in values.keys())
    cur = conn.execute(
        f"INSERT INTO users ({cols}) VALUES ({placeholders})", values
    )
    return cur.lastrowid


def update_user(conn: sqlite3.Connection, uid: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = dict(fields)
    params["id"] = uid
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = :id", params)


def delete_user(conn: sqlite3.Connection, uid: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))


def ensure_default_admin(path: Path = DB_PATH) -> None:
    """Legt Admin-Konto an, falls noch keine Benutzer existieren."""
    from modules.auth import hash_password
    with read_connection(path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        with transaction(path) as conn:
            conn.execute(
                """INSERT INTO users (username, password_hash, role, active, force_pw_change)
                   VALUES (?, ?, 'admin', 1, 1)""",
                ("admin", hash_password("admin")),
            )
        logger.info("Standard-Admin 'admin' angelegt (Passwort muss beim ersten Login geändert werden).")


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------

def log_audit(
    conn: sqlite3.Connection,
    user_id: int | None,
    username: str | None,
    aktion: str,
    details: str = "",
    table_name: str | None = None,
    record_id: int | None = None,
) -> None:
    conn.execute(
        """INSERT INTO audit_log (user_id, username, aktion, details, table_name, record_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, username, aktion, details, table_name, record_id),
    )


def get_audit_log(conn: sqlite3.Connection, limit: int = 1000) -> list:
    return conn.execute(
        "SELECT * FROM audit_log ORDER BY zeitpunkt DESC LIMIT ?", (limit,)
    ).fetchall()
