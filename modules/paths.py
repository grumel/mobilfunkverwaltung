"""
paths.py – Zentrale Pfadauflösung für Entwicklung UND gebaute EXE.

Hintergrund: In einer mit PyInstaller gebauten EXE zeigt ``__file__`` in einen
temporären Entpack-Ordner (``sys._MEIPASS``), der beim Beenden gelöscht wird.
Würde die App ihre Datenbank dort ablegen, wäre sie nach jedem Start weg.

Deshalb zwei getrennte Wurzeln:

DATA_DIR
    Schreibbare Daten (Datenbank, Einstellungen, Logs, Backups, Kündigungen).
    Override per Umgebungsvariable ``MOBILFUNK_DATA_DIR`` (z. B. Netzlaufwerk,
    Tests, oder wenn das Programm in C:\\Program Files liegt).
    Sonst: gebaute EXE -> Ordner der EXE; Entwicklung -> Projektwurzel.

RESOURCE_DIR
    Gebündelte, nur-lesbare Ressourcen (z. B. Icon).
    onefile-EXE  -> Entpack-Ordner (sys._MEIPASS).
    Entwicklung  -> Projektwurzel.
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FROZEN = getattr(sys, "frozen", False)

if _FROZEN:
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
else:
    RESOURCE_DIR = _PROJECT_ROOT

_env_data = os.environ.get("MOBILFUNK_DATA_DIR")
if _env_data:
    DATA_DIR = Path(_env_data).expanduser().resolve()
elif _FROZEN:
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    DATA_DIR = _PROJECT_ROOT
