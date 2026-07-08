"""
webconfig.py – Persistente Web-Konfiguration (Datenbankpfad).

Bewusst getrennt vom Programm: Die Konfig liegt in einem schreibbaren,
programm-unabhängigen Ort (Standard: %LOCALAPPDATA%\\MobilfunkWeb\\webconfig.json),
damit das Programmverzeichnis auch schreibgeschützt sein darf (z. B. Program Files)
und die Datenbank frei woanders liegen kann.

Override des Speicherorts per Umgebungsvariable MOBILFUNK_WEBCONFIG_DIR.
"""

import json
import os
from pathlib import Path


def config_dir() -> Path:
    base = (os.environ.get("MOBILFUNK_WEBCONFIG_DIR")
            or os.environ.get("LOCALAPPDATA")
            or str(Path.home()))
    return Path(base) / "MobilfunkWeb"


def config_file() -> Path:
    return config_dir() / "webconfig.json"


def load() -> dict:
    f = config_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(data: dict) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_file().write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")
