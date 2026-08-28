@echo off
rem =====================================================================
rem  Mobilfunkverwaltung - Ein-Klick-Start fuer Windows
rem  Doppelklick genuegt. Beim ersten Mal wird automatisch installiert
rem  (virtuelle Umgebung + Python-Pakete, sichtbare Konsole). Danach
rem  oeffnet sich ein schlankes Statusfenster mit Link und Beenden-Knopf;
rem  die Konsole bleibt versteckt.
rem  Voraussetzung: Python 3.12+ ist installiert. Node.js wird NICHT
rem  gebraucht - der Frontend-Build liegt bereits im Paket.
rem =====================================================================
setlocal
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

rem Ist die Laufzeit schon eingerichtet? (venv + Frontend-Build vorhanden)
if not exist "backend\.venv\Scripts\python.exe" goto install
if not exist "frontend\dist\index.html" goto install
goto window

:install
echo.
echo === Erstinstallation (nur beim ersten Start, kann einige Minuten dauern) ===
echo.
%PS% -File ".\deploy\windows\install.ps1"
if errorlevel 1 goto fail

:window
rem Statusfenster oeffnen; Server laeuft im Hintergrund, Konsole versteckt.
rem Dieses schwarze Fenster schliesst sich gleich von selbst.
start "" %PS% -WindowStyle Hidden -File ".\deploy\windows\gui.ps1"
goto end

:fail
echo.
echo ------------------------------------------------------------------
echo  Es ist ein Fehler aufgetreten.
echo  Haeufigste Ursachen:
echo   - Python 3.12+ ist nicht installiert  (https://www.python.org/downloads/)
echo   - Kein Internet fuer die einmalige Paket-Installation
echo  Details siehe WINDOWS_INSTALL.md, Abschnitt "Fehlersuche".
echo ------------------------------------------------------------------
echo.
pause

:end
endlocal
