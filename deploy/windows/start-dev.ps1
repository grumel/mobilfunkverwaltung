[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")), [switch]$OpenBrowser)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "install.ps1") -RepositoryRoot $RepositoryRoot
& (Join-Path $PSScriptRoot "start.ps1") -RepositoryRoot $RepositoryRoot -OpenBrowser:$OpenBrowser
