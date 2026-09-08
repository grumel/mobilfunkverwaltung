@echo off
rem =====================================================================
rem  Mobilfunkverwaltung - Ein-Klick-Start fuer Windows
rem  Doppelklick genuegt. Aus dem Release-ZIP ist nichts vorauszusetzen:
rem  Python und alle Abhaengigkeiten liegen als fertiges Bundle bereits
rem  im Paket, ebenso der fertige Frontend-Build - Node.js wird nicht
rem  gebraucht. Nur bei einem Checkout aus dem Quellcode (git clone)
rem  installiert der erste Start selbst eine virtuelle Umgebung samt
rem  Python-Paketen (sichtbare Konsole, kann einige Minuten dauern;
rem  dafuer ist dann Python 3.12+ selbst vorausgesetzt). Danach oeffnet
rem  sich ein schlankes Statusfenster mit Link und Beenden-Knopf; die
rem  Konsole bleibt versteckt.
rem =====================================================================
setlocal
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

rem Ist die Laufzeit schon eingerichtet?
rem Bei mitgeliefertem Bundle (Release-ZIP oder ein per Hand kopierter/
rem geteilter Ordner: backend\python-embed) IMMER install.ps1 durchlaufen
rem lassen - das ist ohne pip/npm sehr schnell (nur Datenordner/Secret/
rem Verknuepfung) und stellt sicher, dass jeder Rechner seine EIGENE
rem Ersteinrichtung unter %PROGRAMDATA% bekommt, auch wenn der Ordner
rem samt fertigem Bundle von einem anderen PC kopiert wurde.
if exist "backend\python-embed\python.exe" goto install
rem Quellcode-Checkout ohne Bundle: die (langsame) venv/pip-Installation
rem nur beim allerersten Start ausfuehren.
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
