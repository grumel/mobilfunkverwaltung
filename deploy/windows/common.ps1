# =====================================================================
#  Gemeinsame Hilfsfunktionen fuer die Windows-Runtime-Skripte.
#  Per Dot-Sourcing einbinden: . (Join-Path $PSScriptRoot "common.ps1")
# =====================================================================

function Test-BundledPython {
  <#  Prueft, ob ein vorinstalliertes Python-Bundle mitgeliefert wurde
      (backend\python-embed\python.exe – wird von
      scripts/publish-windows-zip.sh ins Release-ZIP gepackt und enthaelt
      bereits alle Abhaengigkeiten). In diesem Fall sind auf dem Zielrechner
      weder Python noch Internetzugang fuer pip noetig. #>
  param([Parameter(Mandatory)][string]$Backend)
  return Test-Path (Join-Path $Backend "python-embed\python.exe")
}

function Resolve-BackendPython {
  <#  Liefert den Python-Interpreter fuer die Windows-Runtime: bevorzugt
      das mitgelieferte Bundle, faellt sonst auf die klassische .venv
      zurueck (Quellcode-Checkout, von install.ps1 selbst angelegt). #>
  param([Parameter(Mandatory)][string]$Backend)
  if (Test-BundledPython $Backend) { return (Join-Path $Backend "python-embed\python.exe") }
  return (Join-Path $Backend ".venv\Scripts\python.exe")
}
