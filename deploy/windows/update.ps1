[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")))
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
if (Test-Path (Join-Path $RepositoryRoot ".git")) { & git -C $RepositoryRoot pull --ff-only; if ($LASTEXITCODE) { throw "Git-Update fehlgeschlagen." } }
& (Join-Path $PSScriptRoot "install.ps1") -RepositoryRoot $RepositoryRoot
