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

from platform_support import get_data_directory, get_resource_directory


DATA_DIR = get_data_directory()
RESOURCE_DIR = get_resource_directory()
