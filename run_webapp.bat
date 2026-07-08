@echo off
REM Eigenstaendige Web-App (Programm getrennt von Desktop-App und Datenbank).
cd /d "%~dp0"

REM --- Datenbank-Standardort (Programm und DB getrennt) --------------------
REM Zeigt standardmaessig auf die vorhandene Datenbank. Hier anpassen ODER
REM spaeter in der App unter "Einstellungen" den Datenbankpfad aendern.
set "MOBILFUNK_DATA_DIR=C:\Users\hjohn\Desktop\MobilDatenVerwaltung"

if not exist ".venv\Scripts\python.exe" (
    echo FEHLER: .venv nicht gefunden. Einmalige Einrichtung:
    echo    python -m venv .venv
    echo    .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo Web-App laeuft auf http://127.0.0.1:5001  (Fenster offen lassen; Strg+C beendet)
".venv\Scripts\python.exe" run_webapp.py
