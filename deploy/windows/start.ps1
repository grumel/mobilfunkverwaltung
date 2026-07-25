[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")), [string]$DataDir = "", [int]$Port = 8000, [switch]$OpenBrowser)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
$Backend = Join-Path $RepositoryRoot "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not $DataDir) { $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }; $DataDir = Join-Path $base "Mobilfunkverwaltung" }
$EnvFile = Join-Path $DataDir "mobilfunk.env.ps1"
if (-not (Test-Path $Python) -or -not (Test-Path $EnvFile) -or -not (Test-Path (Join-Path $RepositoryRoot "frontend\dist\index.html"))) { throw "Laufzeit fehlt. Zuerst install.ps1 ausführen." }
. $EnvFile
$env:MOBILFUNK_HOST = "127.0.0.1"
$env:MOBILFUNK_PORT = "$Port"
$env:MOBILFUNK_NO_BROWSER = "1"
$process = Start-Process -FilePath $Python -ArgumentList (Join-Path $Backend "run_windows.py") -WorkingDirectory $Backend -PassThru
try {
  $ready = $false
  for ($i = 0; $i -lt 40; $i++) { if ($process.HasExited) { throw "Waitress wurde beendet (Exit $($process.ExitCode))." }; try { $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/version" -TimeoutSec 1; if ($response.StatusCode -eq 200) { $ready = $true; break } } catch { Start-Sleep -Milliseconds 250 } }
  if (-not $ready) { throw "Backend wurde nicht bereit." }
  $url = "http://127.0.0.1:$Port/"
  Write-Host "Mobilfunkverwaltung läuft: $url"
  if ($OpenBrowser) { Start-Process $url }
  Wait-Process -Id $process.Id
} finally { if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force } }
