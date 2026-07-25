[CmdletBinding()]
param([string]$DataDir = "", [string]$BackupRoot = "")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (-not $DataDir) { $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }; $DataDir = Join-Path $base "Mobilfunkverwaltung" }
if (-not $BackupRoot) { $BackupRoot = Join-Path $DataDir "backups" }
$Stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Target = Join-Path $BackupRoot $Stamp
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$Database = Join-Path $DataDir "mobilfunk.db"
if (Test-Path $Database) { Copy-Item $Database (Join-Path $Target "mobilfunk.db") -ErrorAction Stop }
foreach ($name in @("Dokumente", "Kuendigungen", "SynoDateien", "logs")) { $source = Join-Path $DataDir $name; if (Test-Path $source) { Copy-Item $source (Join-Path $Target $name) -Recurse -Force } }
$envFile = Join-Path $DataDir "mobilfunk.env.ps1"
if (Test-Path $envFile) { Copy-Item $envFile (Join-Path $Target "mobilfunk.env.ps1") }
Write-Host "Backup erstellt: $Target"
