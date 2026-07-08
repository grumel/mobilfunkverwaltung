"""
config.py – Konfiguration der Web-App.

Die Datenbank ist bewusst vom Programm getrennt. DATABASE_URL wird bestimmt in
dieser Reihenfolge:
  1. Umgebungsvariable DATABASE_URL (höchste Priorität)
  2. Web-Konfig (Einstellungen-Seite): volle URL 'database_url' oder SQLite-Pfad 'db_path'
  3. Standard: mobilfunk.db in der DATA_DIR (siehe modules/paths.py)

Für PostgreSQL: DATABASE_URL bzw. database_url auf
'postgresql+psycopg://user:pw@host:5432/mobilfunk' setzen.
"""

import os
from pathlib import Path

from webapp.webconfig import load as _load_webcfg

try:
    from modules.paths import DATA_DIR
    _default_db = DATA_DIR / "mobilfunk.db"
except Exception:
    # Fallback: Projektwurzel (…/WebApp/webapp/config.py -> parents[2])
    _default_db = Path(__file__).resolve().parents[2] / "mobilfunk.db"


def _sqlite_url(path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


def resolve_database_url() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    cfg = _load_webcfg()
    if cfg.get("database_url"):
        return cfg["database_url"]
    if cfg.get("db_path"):
        return _sqlite_url(Path(cfg["db_path"]))
    return _sqlite_url(_default_db)


DATABASE_URL = resolve_database_url()
DEFAULT_DB_PATH = str(_default_db)
SECRET_KEY = os.environ.get("MOBILFUNK_SECRET", "dev-poc-secret-bitte-aendern")
