"""
syno_enrich.py – Syno-Importdatei vor dem Import mit DB-Daten anreichern.

Ablauf pro Zeile:
  1. GSM vorhanden und in DB gefunden → Name aus DB eintragen (korrigieren)
  2. GSM fehlt/falsch, aber Name eindeutig in DB → richtige GSM eintragen
  3. Kein Treffer → Zeile gelb markieren zur manuellen Prüfung

Ergebnis: angereicherte Kopie der Datei (Suffix _angereichert).
"""

import logging
from pathlib import Path
from datetime import datetime

import openpyxl
from openpyxl.styles import PatternFill, Font

from modules import database as db
from modules import settings_store
from modules.utils import normalize_gsm, normalize_name, names_match, name_subset_match

logger = logging.getLogger(__name__)

FILL_FIXED   = PatternFill("solid", fgColor="C6EFCE")  # grün  – automatisch ergänzt
FILL_WARN    = PatternFill("solid", fgColor="FFEB9C")  # gelb  – kein Treffer, manuell prüfen
FILL_CHANGED = PatternFill("solid", fgColor="BDD7EE")  # blau  – GSM korrigiert


def run_syno_enrich(filepath: str | Path) -> dict:
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")

    cols = settings_store.get()["syno_columns"]
    col_gsm  = cols["rufnummer"]
    col_name = cols["name"]

    wb = openpyxl.load_workbook(str(filepath))
    ws = wb.active

    with db.read_connection() as conn:
        # provider=None: auch Telekom-Teilnehmer für das Matching heranziehen
        all_participants = db.get_all_participants(conn, provider=None)

    # Index: gsm → row,  normname → [rows]
    gsm_index  = {}
    name_index = {}
    for p in all_participants:
        if p["gsm"]:
            gsm_index[normalize_gsm(p["gsm"])] = p
        nn = normalize_name(p["name"])
        if nn:
            name_index.setdefault(nn, []).append(p)

    fixed_gsm   = 0
    fixed_name  = 0
    changed_gsm = 0
    no_match    = 0

    for row in ws.iter_rows(min_row=2):
        if col_gsm >= len(row) and col_name >= len(row):
            continue

        raw_gsm  = row[col_gsm].value  if col_gsm  < len(row) else None
        raw_name = row[col_name].value if col_name < len(row) else None

        gsm_norm  = normalize_gsm(str(raw_gsm or ""))
        name_norm = normalize_name(str(raw_name or ""))

        matched = None

        # 1. GSM-Match
        if gsm_norm and gsm_norm in gsm_index:
            matched = gsm_index[gsm_norm]
            db_name = matched["name"] or ""
            # Name in Datei korrigieren/ergänzen falls abweichend
            if db_name and str(raw_name or "").strip() != db_name:
                row[col_name].value = db_name
                row[col_name].fill  = FILL_FIXED
                fixed_name += 1

        # 2. Name-Match (nur wenn GSM fehlt oder nicht gefunden)
        if not matched and name_norm:
            candidates = [p for p in all_participants
                          if names_match(name_norm, normalize_name(p["name"] or ""))]
            if not candidates:
                # Toleranter Rückfall: Name mit Zusatz ("Kessel Ralf ehem. …")
                candidates = [p for p in all_participants
                              if name_subset_match(name_norm, normalize_name(p["name"] or ""))]
            if len(candidates) == 1:
                matched = candidates[0]
                db_gsm = normalize_gsm(matched["gsm"] or "")
                if db_gsm:
                    old_gsm = str(raw_gsm or "").strip()
                    row[col_gsm].value = db_gsm
                    if old_gsm and old_gsm != db_gsm:
                        row[col_gsm].fill = FILL_CHANGED   # war falsch
                        changed_gsm += 1
                    else:
                        row[col_gsm].fill = FILL_FIXED     # war leer
                        fixed_gsm += 1

        # 3. Kein Treffer → gelb markieren
        if not matched:
            for cell in row:
                if cell.value is not None:
                    cell.fill = FILL_WARN
            no_match += 1

    # Legende in Zeile 1 (letzte Spalte+2)
    last_col = ws.max_column + 2
    ws.cell(1, last_col,     "Legende:").font = Font(bold=True)
    ws.cell(2, last_col,     "Automatisch ergänzt").fill  = FILL_FIXED
    ws.cell(3, last_col,     "GSM korrigiert").fill       = FILL_CHANGED
    ws.cell(4, last_col,     "Kein Treffer – bitte prüfen").fill = FILL_WARN

    out_path = filepath.with_stem(filepath.stem + "_angereichert")
    wb.save(str(out_path))

    summary = {
        "fixed_gsm":   fixed_gsm,
        "fixed_name":  fixed_name,
        "changed_gsm": changed_gsm,
        "no_match":    no_match,
        "out_path":    out_path,
    }
    logger.info(
        "Syno-Anreicherung: %d GSM ergänzt, %d GSM korrigiert, "
        "%d Namen ergänzt, %d ohne Treffer → %s",
        fixed_gsm, changed_gsm, fixed_name, no_match, out_path.name,
    )
    return summary
