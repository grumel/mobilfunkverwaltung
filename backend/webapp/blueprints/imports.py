"""
imports.py – Vodafone-/Syno-Import über die Weboberfläche (nur Admin).

Wiederverwendung der getesteten Desktop-Logik:
  modules.vodafone_import.run_vodafone_import(path, dry_run=…)
  modules.syno_import.run_syno_import(path)
Beide schreiben über modules/database.py in dieselbe SQLite-Datei, die auch die
Web-App liest (gleiche DATA_DIR). Vor echten Importen wird ein Backup erstellt.
"""

import os
import tempfile

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)
from werkzeug.utils import secure_filename

from webapp.security import require

from modules import vodafone_import, syno_import
from modules import database as ddb

bp = Blueprint("imports", __name__)


def _save_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Bitte eine Excel-Datei auswählen.")
        return None, None
    if not f.filename.lower().endswith((".xlsx", ".xls")):
        flash("Nur Excel-Dateien (.xlsx/.xls) werden unterstützt.")
        return None, None
    fd, path = tempfile.mkstemp(suffix="_" + secure_filename(f.filename))
    os.close(fd)
    f.save(path)
    return path, f.filename


@bp.route("/import")
@require("admin")
def index():
    return render_template("imports/index.html", active_tab="import")


# --- Vodafone: Vorschau (dry-run) -> Bestätigen -> echter Import ------------
@bp.post("/import/vodafone")
@require("admin")
def vodafone_preview():
    path, filename = _save_upload()
    if not path:
        return redirect(url_for("imports.index"))
    try:
        preview = vodafone_import.run_vodafone_import(path, dry_run=True)
    except Exception as exc:
        try: os.unlink(path)
        except OSError: pass
        flash(f"Importfehler: {exc}")
        return redirect(url_for("imports.index"))
    session["vodafone_import_path"] = path
    session["vodafone_import_name"] = filename
    return render_template("imports/vodafone_preview.html",
                           preview=preview, filename=filename, active_tab="import")


@bp.post("/import/vodafone/confirm")
@require("admin")
def vodafone_confirm():
    path = session.pop("vodafone_import_path", None)
    filename = session.pop("vodafone_import_name", "?")
    if not path or not os.path.exists(path):
        flash("Import-Datei nicht mehr vorhanden – bitte erneut hochladen.")
        return redirect(url_for("imports.index"))
    try:
        ddb.create_backup()
        result = vodafone_import.run_vodafone_import(path)
    except Exception as exc:
        flash(f"Import fehlgeschlagen: {exc}")
        return redirect(url_for("imports.index"))
    finally:
        try: os.unlink(path)
        except OSError: pass
    flash(f"Vodafone-Import abgeschlossen: {result.get('updated',0)} aktualisiert, "
          f"{result.get('created',0)} neu.")
    return render_template("imports/result.html", title="Vodafone-Import",
                           filename=filename, result=result, kind="vodafone",
                           active_tab="import")


# --- Syno: direkt (mit Backup) ---------------------------------------------
@bp.post("/import/syno")
@require("admin")
def syno_run():
    path, filename = _save_upload()
    if not path:
        return redirect(url_for("imports.index"))
    try:
        ddb.create_backup()
        result = syno_import.run_syno_import(path)
    except Exception as exc:
        flash(f"Import fehlgeschlagen: {exc}")
        return redirect(url_for("imports.index"))
    finally:
        try: os.unlink(path)
        except OSError: pass
    flash(f"Syno-Import abgeschlossen: {result.get('matched_gsm',0)+result.get('matched_name',0)} zugeordnet.")
    return render_template("imports/result.html", title="Syno-Import",
                           filename=filename, result=result, kind="syno",
                           active_tab="import")
