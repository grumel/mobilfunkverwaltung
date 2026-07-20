"""
master_import.py – Vollständiger Neuimport aus Masterbestand_v4.xlsx.

Regel:
- Vor dem Import werden ALLE participants gelöscht (DELETE FROM participants).
- Danach vollständiger Neuaufbau aus der Excel-Datei.
- Gelb markierte Zeilen (Füllfarbe FFFFF59D) -> verified = 0
- Nicht markierte Zeilen -> verified = 1
- Importvorgang ist transaktional; bei schwerem Fehler vollständiger Rollback.
- Fehler in einzelnen Zeilen werden protokolliert, brechen den Gesamtimport nicht ab.
"""

import logging
from pathlib import Path
from datetime import datetime

import openpyxl

from modules import database as db
from modules.utils import normalize_gsm, normalize_date

logger = logging.getLogger(__name__)

# Füllfarbe für "zu prüfen"-Markierung im Masterbestand
YELLOW_FILL = "FFFFF59D"

# Spaltenzuordnung: Excel-Spaltenindex (0-basiert) -> DB-Feldname
# Tatsächliche Spalten in Masterbestand_v4.xlsx:
# A(0)=ID            B(1)=Name            C(2)=Konto
# D(3)=GSM           E(4)=Rahmenvertragsnummer  F(5)=SIM Seriennummer
# G(6)=Tarif         H(7)=Erstaktivierungsdatum I(8)=Gekündigt
# J(9)=Vertrags beginn  K(10)=Vertrags ende  L(11)=Plant
# M(12)=Telefon_alt  N(13)=Syno            O(14)=Syno seit
# P(15)=Notizen      Q(16)=Vodafone_Status (ignoriert)
COLUMN_MAP = {
    0:  "master_id",      # A = ID/lfd. Nummer (auch Träger der Gelb-Markierung)
    1:  "name",           # B = Name
    2:  "konto",          # C = Konto
    3:  "gsm",            # D = GSM
    4:  "rahmenvertrag",  # E = Rahmenvertragsnummer
    5:  "sim_nummer",     # F = SIM Seriennummer
    6:  "tarif",          # G = Tarif
    7:  "startdatum",     # H = Erstaktivierungsdatum
    8:  "kuendigung",     # I = Gekündigt
    9:  "vertragsbeginn", # J = Vertrags beginn
    10: "vertragsende",   # K = Vertrags ende
    11: "plant",          # L = Plant
    12: "telefon",        # M = Telefon_alt
    13: "syno",           # N = Syno
    14: "start_syno",     # O = Syno seit
    15: "bemerkung",      # P = Notizen
    16: None,             # Q = Vodafone_Status (nicht importiert)
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _cell_is_yellow(cell) -> bool:
    """Gibt True zurück, wenn die Zellfüllfarbe dem definierten Gelbton entspricht."""
    try:
        fill = cell.fill
        if not fill or fill.fill_type not in ("solid",):
            return False
        fg = fill.fgColor
        if fg is None or fg.type != "rgb":
            return False
        return fg.rgb.upper() == YELLOW_FILL.upper()
    except Exception:
        return False


DATE_FIELDS = {"vertragsbeginn", "vertragsende", "kuendigung", "start_syno", "startdatum"}


def _row_to_dict(row_cells: tuple, is_yellow: bool) -> dict:
    """Wandelt eine Zeile (Tuple von Cells) in ein Dict für die DB um."""
    data: dict = {}
    for col_idx, field in COLUMN_MAP.items():
        if field is None:
            continue
        if col_idx >= len(row_cells):
            data[field] = None
            continue
        raw = row_cells[col_idx].value
        if field in DATE_FIELDS:
            data[field] = normalize_date(raw)
        elif field == "gsm":
            data[field] = normalize_gsm(raw)
        elif field == "master_id":
            try:
                data[field] = int(raw) if raw is not None else None
            except (ValueError, TypeError):
                data[field] = None
        else:
            data[field] = str(raw).strip() if raw is not None else None

    data["verified"] = 0 if is_yellow else 1
    return data


# ---------------------------------------------------------------------------
# Öffentliche Importfunktion
# ---------------------------------------------------------------------------

def run_master_import(filepath: str | Path) -> dict:
    """
    Führt den vollständigen Masterimport durch.

    Rückgabe:
        {
            "imported": int,   # erfolgreich importierte Zeilen
            "skipped":  int,   # übersprungene Zeilen (leer oder Fehler)
            "errors":   list,  # Fehlermeldungen einzelner Zeilen
            "log_lines": list, # menschenlesbare Protokollzeilen
        }
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Masterbestand nicht gefunden: {filepath}")

    logger.info("Masterimport gestartet: %s", filepath)

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active  # erstes Blatt

    imported = 0
    skipped = 0
    duplicates = 0
    review = 0                 # fehlerhafte Zeilen → zur Prüfung abgelegt
    errors: list[str] = []
    warnings: list[str] = []
    log_lines: list[str] = []

    log_lines.append(f"=== Masterimport {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} ===")
    log_lines.append(f"Datei: {filepath.name}")

    with db.transaction() as conn:
        # Alle bestehenden Teilnehmer löschen
        deleted = db.delete_all_participants(conn)
        db.log_import(conn, "Masterbestand", "DELETE", f"{deleted} Datensätze gelöscht vor Neuimport")
        log_lines.append(f"Bestehende Datensätze gelöscht: {deleted}")

        # Kopfzeile überspringen (Zeile 1)
        rows = list(ws.iter_rows(min_row=2))
        log_lines.append(f"Zeilen in Excel (ohne Kopf): {len(rows)}")

        for row in rows:
            # Gelb-Prüfung: Spalte A (Index 0) trägt die Farbmarkierung
            id_cell   = row[0] if len(row) > 0 else None
            name_cell = row[1] if len(row) > 1 else None  # Spalte B = Name

            # Zeile überspringen wenn Name (Spalte B) und GSM (Spalte D) beide leer
            gsm_cell  = row[3] if len(row) > 3 else None
            if (name_cell is None or name_cell.value is None) and \
               (gsm_cell  is None or gsm_cell.value  is None):
                skipped += 1
                continue

            is_yellow = _cell_is_yellow(id_cell) if id_cell else False

            try:
                data = _row_to_dict(row, is_yellow)

                # Zeile überspringen, wenn weder Name noch GSM vorhanden
                if not data.get("name") and not data.get("gsm"):
                    skipped += 1
                    continue

                pid = db.insert_participant(conn, data)
                db.log_import(
                    conn, "Masterbestand", "INSERT",
                    f"ID={pid} GSM={data.get('gsm')} Name={data.get('name')} verified={data.get('verified')}"
                )
                imported += 1

            except Exception as exc:
                exc_str = str(exc)
                row_num = row[0].row if row else "?"
                if "UNIQUE constraint failed: participants.gsm" in exc_str:
                    gsm = data.get("gsm", "?") if "data" in dir() else "?"
                    msg = f"Zeile {row_num}: Doppelte GSM {gsm} – Zeile übersprungen (erster Eintrag bleibt)"
                    logger.warning(msg)
                    warnings.append(msg)
                    duplicates += 1
                else:
                    # Unsichere Zeile NICHT verlieren: zur Prüfung ablegen.
                    msg = f"Zeile {row_num}: {exc_str}"
                    logger.error(msg)
                    errors.append(msg)
                    d = data if "data" in dir() else {}
                    try:
                        db.insert_unmatched_device(conn, {
                            "quelle":    "Master-Fehler",
                            "gsm":       d.get("gsm"),
                            "benutzer":  d.get("name"),
                            "geraet":    f"Importfehler (Zeile {row_num}): {exc_str}",
                            "startdatum": None,
                        })
                        review += 1
                    except Exception as exc2:
                        logger.error("Zeile %s konnte nicht zur Prüfung abgelegt "
                                     "werden: %s", row_num, exc2)
                skipped += 1

        # Sicherheitsanker: Der Master-Import hat zuvor ALLE Teilnehmer gelöscht.
        # Wenn kein einziger Datensatz erfolgreich importiert wurde, wäre der
        # Bestand danach leer – das ist fast sicher ein Fehler (falsche Datei,
        # falsche Spalten). Exception → gesamte Transaktion wird zurückgerollt,
        # der bisherige Bestand bleibt vollständig erhalten.
        if imported == 0:
            raise RuntimeError(
                f"Masterimport abgebrochen: 0 von {len(rows)} Zeilen konnten "
                f"importiert werden – der bisherige Bestand bleibt unverändert. "
                f"Bitte Datei und Spaltenzuordnung prüfen."
            )

        summary = (
            f"Masterimport abgeschlossen: {imported} importiert, "
            f"{duplicates} doppelte GSM übersprungen, "
            f"{review} zur Prüfung abgelegt, "
            f"{skipped - duplicates} sonstige übersprungen, {len(errors)} Fehler"
        )
        db.log_import(conn, "Masterbestand", "SUMMARY", summary)
        log_lines.append(summary)

    if warnings:
        log_lines.append("--- Doppelte GSM (erster Eintrag behalten) ---")
        log_lines.extend(warnings)
    if errors:
        log_lines.append("--- Fehler (zur Prüfung in 'Nicht zugeordnet') ---")
        log_lines.extend(errors)

    logger.info(summary)
    return {
        "imported":   imported,
        "skipped":    skipped,
        "duplicates": duplicates,
        "review":     review,
        "warnings":   warnings,
        "errors":     errors,
        "log_lines":  log_lines,
    }
