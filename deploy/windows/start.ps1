[CmdletBinding()]
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$FrontendDir = (Join-Path (Split-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")) -Parent) "mdw-frontend"),
    [string]$DataDir = (Join-Path $env:ProgramData "Mobilfunkverwaltung")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $IsAdmin) {
    throw "PowerShell muss zum Binden von Port 80 als Administrator gestartet werden."
}

$BackendDir = (Resolve-Path $BackendDir).Path
$FrontendDir = (Resolve-Path $FrontendDir).Path
$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$FrontendDist = Join-Path $FrontendDir "dist"
$EnvironmentFile = Join-Path $DataDir "mobilfunk.env.ps1"

foreach ($Required in @($VenvActivate, $VenvPython, (Join-Path $FrontendDist "index.html"), $EnvironmentFile)) {
    if (-not (Test-Path $Required)) {
        throw "Fehlende Laufzeitdatei: $Required. Zuerst install.ps1 ausführen."
    }
}
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    throw "Caddy wurde nicht im PATH gefunden."
}

. $VenvActivate
. $EnvironmentFile
$SofficeDir = Join-Path $env:ProgramFiles "LibreOffice\program"
if (Test-Path (Join-Path $SofficeDir "soffice.exe")) {
    $env:PATH = "$SofficeDir;$($env:PATH)"
}

$Settings = @{}
Get-Content (Join-Path $PSScriptRoot "waitress.conf") | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        $Settings[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$env:HOST = $Settings.HOST
$env:PORT = $Settings.PORT
$env:WAITRESS_THREADS = $Settings.THREADS
$env:WAITRESS_CONNECTION_LIMIT = $Settings.CONNECTION_LIMIT
$env:WAITRESS_CHANNEL_TIMEOUT = $Settings.CHANNEL_TIMEOUT
$env:MOBILFUNK_NO_BROWSER = "1"
$env:MOBILFUNK_FRONTEND_DIST = $FrontendDist.Replace("\", "/")

$Backend = Start-Process -FilePath $VenvPython -ArgumentList @("run.py") `
    -WorkingDirectory $BackendDir -PassThru -NoNewWindow
try {
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        if ($Backend.HasExited) {
            throw "Waitress wurde unerwartet beendet (Exit-Code $($Backend.ExitCode))."
        }
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($env:PORT)/api/version" -TimeoutSec 1
            if ($Response.StatusCode -eq 200) { $Ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $Ready) { throw "Waitress ist nicht innerhalb des Zeitlimits bereit geworden." }
    Write-Host "Mobilfunkverwaltung: http://localhost/" -ForegroundColor Green
    & caddy run --config (Join-Path $PSScriptRoot "Caddyfile") --adapter caddyfile
    if ($LASTEXITCODE -ne 0) { throw "Caddy wurde mit Exit-Code $LASTEXITCODE beendet." }
} finally {
    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id -Force
    }
}
