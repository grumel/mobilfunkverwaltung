"""
settings.py – Einstellungen (Admin): Datenbankpfad ändern (Programm/DB trennen).
Änderungen werden in der Web-Konfig gespeichert und beim nächsten Start aktiv.
"""

import os
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash

from webapp.security import require
from webapp import webconfig
from webapp import config as appconfig

bp = Blueprint("settings", __name__)


@bp.route("/einstellungen", methods=["GET", "POST"])
@require("admin")
def index():
    cfg = webconfig.load()
    env_override = bool(os.environ.get("DATABASE_URL"))

    if request.method == "POST":
        db_path = (request.form.get("db_path") or "").strip()
        database_url = (request.form.get("database_url") or "").strip()
        newcfg = dict(cfg)
        if database_url:
            newcfg["database_url"] = database_url
            newcfg.pop("db_path", None)
            flash("Volle DATABASE_URL gespeichert.")
        elif db_path:
            p = Path(db_path)
            newcfg["db_path"] = str(p)
            newcfg.pop("database_url", None)
            if not p.exists():
                flash("Achtung: Die angegebene Datei existiert (noch) nicht – bitte Pfad prüfen.")
            else:
                flash("Datenbankpfad gespeichert.")
        else:
            newcfg.pop("db_path", None)
            newcfg.pop("database_url", None)
            flash("Auf Standard-Datenbank zurückgesetzt.")
        webconfig.save(newcfg)
        flash("Bitte die Web-App neu starten, damit die Änderung aktiv wird.")
        return redirect(url_for("settings.index"))

    return render_template(
        "settings/index.html",
        cfg=cfg,
        current_url=appconfig.DATABASE_URL,          # effektiv seit Start
        default_path=appconfig.DEFAULT_DB_PATH,
        config_file=str(webconfig.config_file()),
        env_override=env_override,
        active_tab="einstellungen",
    )
