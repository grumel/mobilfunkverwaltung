[CmdletBinding()]
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\backend")),
    [string]$FrontendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\frontend")),
    [string]$DataDir = (Join-Path $env:ProgramData "Mobilfunkverwaltung")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $IsAdmin) {
    throw "PowerShell muss als Administrator gestartet werden."
}

function Require-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "'$Name' wurde nicht gefunden. $Hint"
    }
}

Require-Command "python" "Python 3 installieren und zum PATH hinzufügen."
Require-Command "node" "Node.js LTS installieren und zum PATH hinzufügen."
Require-Command "npm" "Node.js einschließlich npm installieren."
Require-Command "caddy" "Caddy für Windows installieren und zum PATH hinzufügen."

$SofficeDir = Join-Path $env:ProgramFiles "LibreOffice\program"
if (-not (Get-Command soffice -ErrorAction SilentlyContinue) -and
    -not (Test-Path (Join-Path $SofficeDir "soffice.exe"))) {
    throw "LibreOffice wurde nicht gefunden. Es wird für den PDF-Export benötigt."
}

$BackendDir = (Resolve-Path $BackendDir).Path
if (-not (Test-Path (Join-Path $BackendDir "requirements.txt"))) {
    throw "Backend-Repository nicht gefunden: $BackendDir"
}
if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    throw "Frontend-Repository nicht gefunden: $FrontendDir"
}

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    & python -m venv (Join-Path $BackendDir ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Virtuelle Umgebung konnte nicht erstellt werden." }
}

$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
. $VenvActivate
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip konnte nicht aktualisiert werden." }
& $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt") -r (Join-Path $BackendDir "requirements-server.txt")
if ($LASTEXITCODE -ne 0) { throw "Python-Abhängigkeiten konnten nicht installiert werden." }

Push-Location $FrontendDir
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci ist fehlgeschlagen." }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend-Build ist fehlgeschlagen." }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $DataDir, (Join-Path $DataDir "logs") | Out-Null
$DataDir = (Resolve-Path $DataDir).Path
$EnvironmentFile = Join-Path $DataDir "mobilfunk.env.ps1"
if (-not (Test-Path $EnvironmentFile)) {
    $Secret = & $VenvPython -c "import secrets; print(secrets.token_hex(32))"
    @"
`$env:MOBILFUNK_DATA_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_WEBCONFIG_DIR = '$($DataDir.Replace("'", "''"))'
`$env:MOBILFUNK_SECRET = '$Secret'
"@ | Set-Content -Path $EnvironmentFile -Encoding UTF8
}
$CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $EnvironmentFile /inheritance:r /grant:r "${CurrentUser}:(F)" "SYSTEM:(F)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Zugriffsrechte der Secret-Datei konnten nicht gesetzt werden." }

Write-Host "Windows-Laufzeit ist vorbereitet." -ForegroundColor Green
Write-Host "Start: powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\start.ps1`""
