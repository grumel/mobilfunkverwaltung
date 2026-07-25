[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
      [string]$DataDir = "")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
$Backend = Join-Path $RepositoryRoot "backend"
$Frontend = Join-Path $RepositoryRoot "frontend"
if (-not $DataDir) { $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }; $DataDir = Join-Path $base "Mobilfunkverwaltung" }
foreach ($cmd in @("python", "node", "npm")) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd wurde nicht gefunden." } }
if (-not (Test-Path (Join-Path $Backend "requirements.txt"))) { throw "Backend-Anforderungen fehlen: $Backend" }
if (-not (Test-Path (Join-Path $Frontend "package.json"))) { throw "Frontend-Paketdatei fehlt: $Frontend" }
$Venv = Join-Path $Backend ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) { & python -m venv $Venv; if ($LASTEXITCODE) { throw "Venv konnte nicht erstellt werden." } }
& $Python -m pip install -r (Join-Path $Backend "requirements.txt") -r (Join-Path $Backend "requirements-server.txt")
if ($LASTEXITCODE) { throw "Python-Abhängigkeiten konnten nicht installiert werden." }
Push-Location $Frontend
try { & npm ci --no-fund --no-audit; if ($LASTEXITCODE) { throw "npm ci fehlgeschlagen." }; & npm run build; if ($LASTEXITCODE) { throw "Frontend-Build fehlgeschlagen." } }
finally { Pop-Location }
New-Item -ItemType Directory -Force -Path $DataDir, (Join-Path $DataDir "logs"), (Join-Path $DataDir "Dokumente"), (Join-Path $DataDir "Kuendigungen"), (Join-Path $DataDir "SynoDateien") | Out-Null
$EnvFile = Join-Path $DataDir "mobilfunk.env.ps1"
if (-not (Test-Path $EnvFile)) {
  $secret = & $Python -c "import secrets; print(secrets.token_hex(32))"
  @"
`$env:MOBILFUNK_DATA_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_WEBCONFIG_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_SECRET = '$secret'
"@ | Set-Content -Path $EnvFile -Encoding UTF8
}
Write-Host "Windows-Laufzeit vorbereitet: $DataDir"
Write-Host "Start: powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1"
