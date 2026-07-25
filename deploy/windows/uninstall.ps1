[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
      [string]$DataDir = "",
      [int]$Port = 8000,
      [switch]$Force)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Entfernt ausschliesslich erzeugte Laufzeitartefakte aus dem Checkout.
# Datenbank, Dokumente, Logs und Secret bleiben unangetastet; sie liegen
# bewusst ausserhalb des Checkouts und werden hier nur angezeigt.

$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
# -Force unterdrueckt nur die Rueckfrage. -WhatIf und -Confirm behalten Vorrang.
if ($Force -and -not $PSBoundParameters.ContainsKey("Confirm")) { $ConfirmPreference = "None" }
if (-not $DataDir) { $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }; $DataDir = Join-Path $base "Mobilfunkverwaltung" }

# Laufende Instanz zuerst beenden, sonst sind Dateien im Venv gesperrt.
$stop = Join-Path $PSScriptRoot "stop.ps1"
if (Test-Path $stop) {
  try { & $stop -Port $Port } catch { Write-Warning "Stoppen uebersprungen: $($_.Exception.Message)" }
}

$targets = @(
  (Join-Path $RepositoryRoot "backend\.venv"),
  (Join-Path $RepositoryRoot "frontend\dist"),
  (Join-Path $RepositoryRoot "frontend\node_modules")
)
# __pycache__ nur in den Quellordnern; die Massen in .venv und node_modules
# verschwinden bereits mit den Verzeichnissen oben. Wuerde man sie hier mit
# aufnehmen, loeschte die Schleife .venv zuerst und stolperte danach ueber die
# bereits entfernten Unterordner.
$targets += Get-ChildItem -Path (Join-Path $RepositoryRoot "backend") -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\\.venv\\' -and $_.FullName -notmatch '\\node_modules\\' } |
  Select-Object -ExpandProperty FullName

# Nie ausserhalb des Checkouts loeschen, auch nicht bei manipulierten Parametern.
$root = $RepositoryRoot.TrimEnd("\") + "\"
$existing = @($targets | Where-Object { $_ -and (Test-Path $_) } |
  ForEach-Object { (Resolve-Path $_).Path } |
  Where-Object { $_.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) } |
  Select-Object -Unique)

if ($existing.Count -eq 0) {
  Write-Host "Keine Laufzeitartefakte gefunden. Der Checkout ist bereits sauber."
} else {
  Write-Host "Folgendes wird entfernt:"
  $existing | ForEach-Object { Write-Host "  $_" }
  if ($PSCmdlet.ShouldProcess($RepositoryRoot, "Laufzeitartefakte entfernen")) {
    # SilentlyContinue: sollte ein Pfad bereits mit einem Elternordner
    # verschwunden sein, bricht das Aufraeumen deshalb nicht ab.
    foreach ($path in $existing) { Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host "Laufzeitartefakte entfernt."
  } else {
    Write-Host "Es wurde nichts geloescht."
  }
}

Write-Host ""
Write-Host "Erhalten bleiben (bitte selbst pruefen und sichern):"
if (Test-Path $DataDir) {
  Write-Host "  Datenverzeichnis: $DataDir"
  foreach ($name in @("mobilfunk.db", "mobilfunk.env.ps1", "Dokumente", "Kuendigungen", "SynoDateien", "logs", "backups")) {
    $item = Join-Path $DataDir $name
    if (Test-Path $item) { Write-Host "    $name" }
  }
  Write-Host "  Vor dem Loeschen: backup.ps1 ausfuehren und die Sicherung pruefen."
} else {
  Write-Host "  Kein Datenverzeichnis unter $DataDir gefunden."
}
Write-Host ""
Write-Host "Der Checkout selbst wird nicht entfernt, da dieses Skript darin laeuft."
Write-Host "Danach von Hand loeschbar: $RepositoryRoot"
Write-Host "Es wurden weder Dienste, Registry-Eintraege noch Verknuepfungen angelegt;"
Write-Host "es bleibt also nichts weiter im System zurueck."
