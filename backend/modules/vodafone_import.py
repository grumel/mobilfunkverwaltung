"""
vodafone_import.py – Monatlicher Vodafone-Datenimport.

Regeln:
- Matching ausschließlich über GSM.
- Darf nur folgende Felder aktualisieren:
    gsm, konto, tarif, sim_nummer, vertragsbeginn, vertragsende,
    rahmenvertrag, kuendigung
- Darf niemals überschreiben: name, plant, telefon, bemerkung, verified
- Kein Match -> neuen Datensatz anlegen mit verified=0 und Herkunftshinweis.
- Plant-Konto-Prüfung: wenn Zuordnung nicht passt -> verified=0 + Prüfhinweis.
- Importvorgang ist transaktional.
"""

import logging
import re
from pathlib import Path
from datetime import datetime

import openpyxl

from modules import database as db
from modules import settings_store
from modules.utils import normalize_gsm, normalize_date

logger = logging.getLogger(__name__)

# Erwartete Schlüsselbegriffe in den Spaltenköpfen für die Validierung
_HEADER_KEYWORDS: dict[str, str] = {
    "konto":          "konto",
    "gsm":            "teilnehmer",
    "rahmenvertrag":  "rahmen",
    "tarif":          "tarif",
    "vertragsbeginn": "beginn",
    "vertragsende":   "ende",
    "kuendigung":     "kündigung",
}

# Erwartete Inhalts-Art je Feld – für die inhaltliche Gegenprobe, falls der
# Spaltenkopf nicht exakt an der erwarteten Stelle steht (z. B. wenn die
# Datenzeilen gegenüber der Kopfzeile um eine leere Spalte verschoben sind).
_FIELD_KINDS: dict[str, str] = {
    "konto":          "int",
    "gsm":            "gsm",
    "tarif":          "text",
    "vertragsbeginn": "date",
    "vertragsende":   "date",
    "kuendigung":     "date",
}


def _get_cols() -> dict:
    return settings_store.get()["vodafone_columns"]


def _looks_like_date(v) -> bool:
    """True, wenn der Wert ein Datum ist (datetime/date) oder als Datum lesbar."""
    from datetime import date as _date
    if isinstance(v, (datetime, _date)):
        return True
    if v is None:
        return False
    s = str(v).strip()
    if not s:
        return False
    return bool(re.match(r"^\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$", s)
                or re.match(r"^\d{4}-\d{1,2}-\d{1,2}", s))


def _kind_matches(value, kind: str) -> bool:
    """Passt ein Zellwert zum erwarteten Feld-Typ?"""
    s = "" if value is None else str(value).strip()
    if kind == "date":
        return _looks_like_date(value)
    if kind == "int":
        return len(re.sub(r"[^\d]", "", s)) >= 4      # Kontonummern sind lang
    if kind == "gsm":
        return normalize_gsm(value) is not None
    if kind == "text":
        # Tarifname: nicht-leer und KEIN Datum (sonst wurde die falsche Spalte gelesen)
        return bool(s) and not _looks_like_date(value)
    return True


def _content_confirms(sample_rows: list | None, idx: int, kind: str) -> bool | None:
    """Prüft anhand einiger Datenzeilen, ob Spalte idx zum erwarteten Inhalt passt.

    True = passt, False = passt nicht, None = nicht beurteilbar (Spalte in der
    Stichprobe leer)."""
    if not sample_rows or idx < 0:
        return None
    nonempty = [r[idx] for r in sample_rows
                if idx < len(r) and r[idx] is not None and str(r[idx]).strip()]
    if not nonempty:
        return None
    hits = sum(1 for v in nonempty if _kind_matches(v, kind))
    return hits / len(nonempty) >= 0.6


def _header_keyword_near(header_row: list, idx: int, expected: str) -> bool:
    """True, wenn das Schlüsselwort am erwarteten Index oder direkt daneben
    (±1 Spalte) steht. Toleriert eine bekannte 1-Spalten-Verschiebung zwischen
    Kopfzeile und Datenzeilen."""
    for j in (idx, idx - 1, idx + 1):
        if 0 <= j < len(header_row) and expected in str(header_row[j] or "").lower():
            return True
    return False


def _validate_vodafone_headers(header_row: list, cols: dict,
                               sample_rows: list | None = None) -> list[str]:
    """Prüft die Spaltenzuordnung und gibt eine Liste von Abweichungen zurück
    (leer = alles ok). Bricht nicht ab – die Entscheidung trifft der Aufrufer.

    Robust gegen eine 1-Spalten-Verschiebung zwischen Kopfzeile und Daten: Es
    wird nur gewarnt, wenn WEDER der Spaltenkopf (am erwarteten Index oder direkt
    daneben) passt, NOCH der tatsächliche Spalteninhalt zum erwarteten Typ passt."""
    warnings = []
    for key, expected in _HEADER_KEYWORDS.items():
        col_idx = cols.get(key, -1)
        if col_idx < 0 or col_idx >= len(header_row):
            warnings.append(f"Spalte '{key}' (Index {col_idx}) fehlt in der Datei.")
            continue
        header_ok = _header_keyword_near(header_row, col_idx, expected)
        content = _content_confirms(sample_rows, col_idx, _FIELD_KINDS.get(key, "any"))
        if header_ok or content is True:
            continue
        actual = header_row[col_idx] if col_idx < len(header_row) else None
        if content is False:
            warnings.append(
                f"Spalte '{key}' (Index {col_idx}): Inhalt passt nicht zum "
                f"erwarteten Typ (Kopf: '{actual}')"
            )
        else:
            warnings.append(
                f"Spalte '{key}' (Index {col_idx}): erwartet '{expected}', "
                f"gefunden '{actual}'"
            )
    if warnings:
        logger.warning("Vodafone-Spaltenköpfe: %s", "; ".join(warnings))
    return warnings


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _normalize_konto(raw) -> str | None:
    if raw is None:
        return None
    s = re.sub(r"[^\d]", "", str(raw).strip())
    return s if s else None


def _cell_value(row, col_idx) -> str | None:
    if col_idx >= len(row):
        return None
    v = row[col_idx].value
    if v is None:
        return None
    return str(v).strip() or None



def find_by_gsm(filepath: str | Path, gsm: str) -> dict | None:
    """Sucht eine einzelne Zeile per GSM in der Vodafone-Exportdatei.

    Liest nur die Datei, schreibt nichts in die Datenbank – für den
    Einzel-Abgleich im Bearbeiten-Fenster. Gibt None zurück, wenn keine
    Zeile mit dieser GSM gefunden wurde.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Vodafone-Datei nicht gefunden: {filepath}")

    target = normalize_gsm(gsm)
    if not target:
        return None

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active
    cfg = settings_store.get()
    cols = cfg["vodafone_columns"]
    konto_plant = cfg["konto_plant"]

    for row in ws.iter_rows(min_row=2):
        raw_gsm = _cell_value(row, cols["gsm"])
        if normalize_gsm(raw_gsm) != target:
            continue
        raw_konto = _cell_value(row, cols["konto"])
        konto = _normalize_konto(raw_konto)
        result = {
            "konto":          konto,
            "tarif":          _cell_value(row, cols["tarif"]),
            "sim_nummer":     _cell_value(row, cols["sim"]),
            "vertragsbeginn": normalize_date(_cell_value(row, cols["vertragsbeginn"])),
            "vertragsende":   normalize_date(_cell_value(row, cols["vertragsende"])),
            "rahmenvertrag":  _cell_value(row, cols["rahmenvertrag"]),
            "kuendigung":     normalize_date(_cell_value(row, cols["kuendigung"])),
        }
        mapped_plant = konto_plant.get(konto) if konto else None
        if mapped_plant:
            result["plant"] = mapped_plant
        return result
    return None


# ---------------------------------------------------------------------------
# Öffentliche Importfunktion
# ---------------------------------------------------------------------------

def run_vodafone_import(filepath: str | Path, dry_run: bool = False,
                        db_module=None) -> dict:
    """
    Führt den Vodafone-Import durch.

    dry_run=True: liest und analysiert die Datei, schreibt aber nichts in die DB.
    db_module: austauschbares Datenbank-Backend (Standard: modules.database,
        SQLite). Muss dieselbe Funktionsoberfläche bieten – siehe
        webapp/import_adapter.py für die SQLAlchemy-Variante (z. B. PostgreSQL).

    Rückgabe:
        {
            "updated":     int,
            "created":     int,
            "skipped":     int,
            "errors":      list,
            "log_lines":   list,
            "new_entries": list[dict],   # nur bei dry_run sinnvoll
            "dry_run":     bool,
        }
    """
    dbm = db_module or db
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Vodafone-Datei nicht gefunden: {filepath}")

    logger.info("Vodafone-Import gestartet: %s", filepath)

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active

    cfg         = settings_store.get()
    cols        = cfg["vodafone_columns"]
    konto_plant = cfg["konto_plant"]

    # Spaltenköpfe prüfen (Zeile 1) – Abweichungen werden zurückgegeben,
    # damit der Aufrufer bei unsicherer Struktur nachfragen kann.
    header_row = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    sample_rows = [[c.value for c in r]
                   for r in ws.iter_rows(min_row=2, max_row=21)]
    header_warnings = _validate_vodafone_headers(header_row, cols, sample_rows)

    updated = 0
    created = 0
    skipped = 0
    review  = 0                 # fehlerhafte Zeilen → zur Prüfung abgelegt
    errors:      list[str]  = []
    log_lines:   list[str]  = []
    new_entries: list[dict] = []
    changes:     list[str]  = []   # inhaltliche Änderungen für den Report

    log_lines.append(f"=== Vodafone-Import {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} ===")
    log_lines.append(f"Datei: {filepath.name}")

    ctx = dbm.dry_run_transaction if dry_run else dbm.transaction
    with ctx() as conn:
        # Veraltete Plant-Warnungen aus alten Importen bereinigen
        cleaned = dbm.clean_vodafone_plant_warnings(conn)
        if cleaned:
            log_lines.append(f"Bereinigt: {cleaned} veraltete Werk-Warnungen aus Bemerkung entfernt")
            dbm.log_import(conn, "Vodafone", "CLEANUP", f"{cleaned} Plant-Warnungen bereinigt")

        # Alle Teilnehmer als "nicht in Vodafone" vormarkieren;
        # gematchte werden im Loop auf 1 gesetzt.
        dbm.reset_vodafone_aktiv(conn)

        for row in ws.iter_rows(min_row=2):
            raw_gsm   = _cell_value(row, cols["gsm"])
            raw_konto = _cell_value(row, cols["konto"])

            gsm   = normalize_gsm(raw_gsm)
            konto = _normalize_konto(raw_konto)

            # Zeile ohne GSM und ohne Konto überspringen
            if not gsm and not konto:
                skipped += 1
                continue

            tarif          = _cell_value(row, cols["tarif"])
            sim            = _cell_value(row, cols["sim"])
            vertragsbeginn = normalize_date(_cell_value(row, cols["vertragsbeginn"]))
            vertragsende   = normalize_date(_cell_value(row, cols["vertragsende"]))
            rahmenvertrag  = _cell_value(row, cols["rahmenvertrag"])
            kuendigung     = normalize_date(_cell_value(row, cols["kuendigung"]))

            # Werk aus Konto-Mapping ableiten (für bestehende und neue Einträge)
            mapped_plant = konto_plant.get(konto) if konto else None

            # Felder, die aktualisiert werden dürfen
            update_data = {
                "konto":          konto,
                "tarif":          tarif,
                "sim_nummer":     sim,
                "vertragsbeginn": vertragsbeginn,
                "vertragsende":   vertragsende,
                "rahmenvertrag":  rahmenvertrag,
                "kuendigung":     kuendigung,
            }
            if gsm:
                update_data["gsm"] = gsm
            if mapped_plant:
                update_data["plant"] = mapped_plant

            try:
                existing = dbm.get_participant_by_gsm(conn, gsm) if gsm else None

                if existing:
                    pid        = existing["id"]
                    old_plant  = existing["plant"]
                    old_tarif  = existing["tarif"]
                    name       = existing["name"] or ""

                    plant_note = ""
                    if mapped_plant and old_plant and old_plant != mapped_plant:
                        plant_note = (f"Werk korrigiert: '{old_plant}' → '{mapped_plant}'")
                        log_lines.append(f"WERK: GSM={gsm} {plant_note}")
                        dbm.log_import(conn, "Vodafone", "WERK", f"GSM={gsm} {plant_note}")
                        changes.append(f"Werk:  {name} ({gsm}): '{old_plant}' → '{mapped_plant}'")

                    # Tarifwechsel erkennen
                    if tarif and (old_tarif or "") != tarif:
                        changes.append(
                            f"Tarif: {name} ({gsm}): '{old_tarif or '—'}' → '{tarif}'")

                    dbm.update_participant_fields(conn, pid, update_data)
                    dbm.set_vodafone_aktiv(conn, pid)
                    dbm.log_import(
                        conn, "Vodafone", "UPDATE",
                        f"ID={pid} GSM={gsm} Konto={konto} Werk={mapped_plant or old_plant}"
                    )
                    updated += 1

                else:
                    # Kein Match -> neuen Datensatz anlegen
                    new_data = dict(update_data)
                    new_data["verified"] = 0
                    new_data["vodafone_aktiv"] = 1
                    new_data["bemerkung"] = "Neu aus Vodafone-Import ohne Master-Match"

                    pid = dbm.insert_participant(conn, new_data)
                    dbm.log_import(
                        conn, "Vodafone", "INSERT",
                        f"ID={pid} GSM={gsm} Konto={konto} – neu ohne Master-Match"
                    )
                    log_lines.append(
                        f"NEU: GSM={gsm} Konto={konto} – kein Masterbestand-Match"
                    )
                    new_entries.append({"gsm": gsm, "konto": konto,
                                        "tarif": tarif, "plant": mapped_plant})
                    changes.append(f"Neu:   GSM {gsm} (Konto {konto}, Tarif {tarif or '—'})")
                    created += 1

            except Exception as exc:
                # Unsichere Zeile NICHT verlieren: zur Prüfung in
                # "Nicht zugeordnet" ablegen und protokollieren.
                row_num = row[0].row if row else "?"
                msg = f"Zeile {row_num}: {exc}"
                logger.error(msg)
                errors.append(msg)
                try:
                    dbm.insert_unmatched_device(conn, {
                        "quelle":    "Vodafone-Fehler",
                        "gsm":       gsm,
                        "benutzer":  None,
                        "geraet":    f"Importfehler (Konto {konto}): {exc}",
                        "startdatum": None,
                    })
                    review += 1
                except Exception as exc2:
                    logger.error("Zeile %s konnte nicht zur Prüfung abgelegt "
                                 "werden: %s", row_num, exc2)
                    skipped += 1

        summary = (
            f"Vodafone-Import abgeschlossen: {updated} aktualisiert, "
            f"{created} neu angelegt, {review} zur Prüfung abgelegt, "
            f"{skipped} übersprungen, {len(errors)} Fehler"
        )
        dbm.log_import(conn, "Vodafone", "SUMMARY", summary)
        log_lines.append(summary)

    if header_warnings:
        log_lines.append("--- Spaltenköpfe weichen ab ---")
        log_lines.extend(header_warnings)
    # Änderungs-Report ganz oben einfügen (nach den ersten beiden Kopfzeilen)
    if changes:
        block = [f"--- Änderungen ({len(changes)}) ---", *changes, ""]
        log_lines[2:2] = block
    if errors:
        log_lines.append("--- Fehler (zur Prüfung in 'Nicht zugeordnet') ---")
        log_lines.extend(errors)

    logger.info(summary)
    return {
        "updated":     updated,
        "created":     created,
        "skipped":     skipped,
        "review":      review,
        "changes":     changes,
        "errors":      errors,
        "header_warnings": header_warnings,
        "log_lines":   log_lines,
        "new_entries": new_entries,
        "dry_run":     dry_run,
    }
