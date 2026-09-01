[CmdletBinding()]
param([string]$RepositoryRoot = "",
      [string]$DataDir = "",
      [switch]$NoSampleData)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# $PSScriptRoot ist in Windows PowerShell 5.1 innerhalb des param()-Blocks noch leer,
# daher erst hier (nach Skriptstart) als Fallback verwenden.
if (-not $RepositoryRoot) { $RepositoryRoot = Join-Path $PSScriptRoot "..\.." }
function Invoke-Native {
  # Fuehrt einen nativen Befehl aus, ohne dass PowerShell dessen stderr-Ausgaben
  # (Warnungen/Hinweise von pip, npm, ...) als terminierenden Fehler wertet.
  # Der Erfolg wird stattdessen ueber $LASTEXITCODE geprueft.
  param([Parameter(Mandatory)][ScriptBlock]$Command, [Parameter(Mandatory)][string]$ErrorMessage)
  $prevPref = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try { & $Command } finally { $ErrorActionPreference = $prevPref }
  if ($LASTEXITCODE) { throw $ErrorMessage }
}
$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
$Backend = Join-Path $RepositoryRoot "backend"
$Frontend = Join-Path $RepositoryRoot "frontend"
if (-not $DataDir) { $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }; $DataDir = Join-Path $base "Mobilfunkverwaltung" }
# Python ist immer Pflicht. Node/npm nur, wenn kein fertiger Frontend-Build
# mitgeliefert wurde (dann bauen wir aus dem Quellcode).
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) { throw "python wurde nicht gefunden." }
if (-not (Test-Path (Join-Path $Backend "requirements.txt"))) { throw "Backend-Anforderungen fehlen: $Backend" }
$DistIndex = Join-Path $Frontend "dist\index.html"
$NeedBuild = -not (Test-Path $DistIndex)
if ($NeedBuild) {
  if (-not (Test-Path (Join-Path $Frontend "package.json"))) { throw "Frontend-Paketdatei fehlt: $Frontend" }
  foreach ($cmd in @("node", "npm")) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd wurde nicht gefunden (fuer den Frontend-Build noetig)." } }
}
$Venv = Join-Path $Backend ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) { Invoke-Native -Command { & python -m venv $Venv } -ErrorMessage "Venv konnte nicht erstellt werden." }
Invoke-Native -Command { & $Python -m pip install -r (Join-Path $Backend "requirements.txt") -r (Join-Path $Backend "requirements-server.txt") } -ErrorMessage "Python-Abhängigkeiten konnten nicht installiert werden."
if ($NeedBuild) {
  Write-Host "Frontend wird aus dem Quellcode gebaut (kein fertiger Build im Paket) ..."
  Push-Location $Frontend
  try {
    Invoke-Native -Command { & npm ci --no-fund --no-audit } -ErrorMessage "npm ci fehlgeschlagen."
    Invoke-Native -Command { & npm run build } -ErrorMessage "Frontend-Build fehlgeschlagen."
  }
  finally { Pop-Location }
}
else {
  Write-Host "Fertiger Frontend-Build gefunden – npm/Node nicht noetig."
}
# Datenordner, Dokumentvorlagen und Test-DB bereitstellen (gemeinsames Skript,
# damit dieselbe Logik auch beim normalen Start greift).
$provArgs = @{ RepositoryRoot = $RepositoryRoot; DataDir = $DataDir }
if ($NoSampleData) { $provArgs.NoSampleData = $true }
& (Join-Path $PSScriptRoot "provision-data.ps1") @provArgs

$EnvFile = Join-Path $DataDir "mobilfunk.env.ps1"
if (-not (Test-Path $EnvFile)) {
  $secret = & $Python -c "import secrets; print(secrets.token_hex(32))"
  @"
`$env:MOBILFUNK_DATA_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_WEBCONFIG_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_SECRET = '$secret'
"@ | Set-Content -Path $EnvFile -Encoding UTF8
}


# Desktop-Verknuepfung anlegen, damit die App per Doppelklick gestartet werden kann.
$StartBat = Join-Path $PSScriptRoot "start.bat"
if (Test-Path $StartBat) {
  $IconPng = Join-Path $Frontend "public\icon-512.png"
  $IconIco = Join-Path $DataDir "mobilfunkverwaltung.ico"
  if ((Test-Path $IconPng) -and -not (Test-Path $IconIco)) {
    try {
      Add-Type -AssemblyName System.Drawing
      $bitmap = New-Object System.Drawing.Bitmap($IconPng)
      $resized = New-Object System.Drawing.Bitmap($bitmap, 256, 256)
      $hIcon = $resized.GetHicon()
      $icon = [System.Drawing.Icon]::FromHandle($hIcon)
      $fs = New-Object System.IO.FileStream($IconIco, [System.IO.FileMode]::Create)
      $icon.Save($fs)
      $fs.Close()
      $icon.Dispose(); $resized.Dispose(); $bitmap.Dispose()
    } catch { Write-Host "Hinweis: Icon konnte nicht erzeugt werden ($_)." -ForegroundColor Yellow }
  }
  $Desktop = [Environment]::GetFolderPath("Desktop")
  $ShortcutPath = Join-Path $Desktop "Mobilfunkverwaltung.lnk"
  $WshShell = New-Object -ComObject WScript.Shell
  $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $StartBat
  $Shortcut.WorkingDirectory = $PSScriptRoot
  $Shortcut.IconLocation = if (Test-Path $IconIco) { $IconIco } else { "$env:SystemRoot\System32\shell32.dll,220" }
  $Shortcut.Description = "Mobilfunkverwaltung starten"
  $Shortcut.Save()
  Write-Host "Desktop-Verknuepfung angelegt: $ShortcutPath"
}

Write-Host "Windows-Laufzeit vorbereitet: $DataDir"
Write-Host "Start: powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1"
