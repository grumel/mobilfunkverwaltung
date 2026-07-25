"""Zentrale, fachlogikfreie Plattform- und Basispfadauflösung.

Die Defaults entsprechen dem bisherigen Verhalten. Umgebungsvariablen bleiben
die öffentliche Konfigurationsschnittstelle für Deployments und Tests.
"""

import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_resource_directory() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return PROJECT_ROOT


def get_data_directory() -> Path:
    configured = os.environ.get("MOBILFUNK_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if is_windows():
        base = (os.environ.get("PROGRAMDATA") or os.environ.get("LOCALAPPDATA")
                or str(Path.home()))
        return (Path(base) / "Mobilfunkverwaltung").resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_database_path() -> Path:
    return get_data_directory() / "mobilfunk.db"


def get_log_directory() -> Path:
    return get_data_directory() / "logs"


def get_temp_directory() -> Path:
    return Path(tempfile.gettempdir()).resolve()


def get_config_directory() -> Path:
    base = (os.environ.get("MOBILFUNK_WEBCONFIG_DIR")
            or os.environ.get("LOCALAPPDATA")
            or str(Path.home()))
    return Path(base).expanduser() / "MobilfunkWeb"
