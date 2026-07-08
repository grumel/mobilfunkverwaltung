"""
settings_store.py – Persistente Einstellungen als JSON-Datei.

Einstellungen werden beim ersten Zugriff geladen und danach gecacht.
Änderungen über save() werden sofort auf Disk geschrieben.
"""

import json
import logging
from pathlib import Path

from modules.paths import DATA_DIR

logger = logging.getLogger(__name__)

SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULTS: dict = {
    "dark_mode": False,
    "konto_plant": {
        "113883298": "Baesweiler",
        "113884819": "Berlin",
        "113884823": "Exter",
        "114834046": "Flörsheim",
        "113884824": "Föritztal",
        "112988240": "Gemünden",
        "113884818": "Holthausen",
        "113884821": "Kaiserslautern",
        "113241460": "Lübeck",
        "112179568": "Mainz",
        "113884817": "Markdorf",
        "120824395": "Alpla-Pharma",
        "120999194": "Heinlein",
    },
    "vodafone_columns": {
        "konto":          0,
        "gsm":            1,
        "rahmenvertrag":  3,
        "sim":            4,
        "tarif":         12,
        "vertragsbeginn":14,
        "vertragsende":  15,
        "kuendigung":    16,
    },
    "syno_columns": {
        "startdatum": 0,
        "syno":      12,
        "name":      13,
        "rufnummer": 15,
    },
}

_cache: dict | None = None


def load() -> dict:
    global _cache
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                stored = json.load(f)
            # Tiefes Merge: fehlende Schlüssel aus Defaults ergänzen
            _cache = _deep_merge(DEFAULTS, stored)
            logger.info("Einstellungen geladen: %s", SETTINGS_PATH)
        except Exception as exc:
            logger.error("Fehler beim Laden der Einstellungen: %s – Defaults werden verwendet", exc)
            _cache = _deep_copy(DEFAULTS)
    else:
        _cache = _deep_copy(DEFAULTS)
    return _cache


def save(data: dict) -> None:
    global _cache
    _cache = data
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Einstellungen gespeichert: %s", SETTINGS_PATH)
    except Exception as exc:
        logger.error("Fehler beim Speichern der Einstellungen: %s", exc)
        raise


def get() -> dict:
    global _cache
    if _cache is None:
        load()
    return _cache


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))
