[CmdletBinding()]
param([string]$RepositoryRoot = "",
      [string]$DataDir = "",
      [switch]$NoSampleData)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# $PSScriptRoot ist in Windows PowerShell 5.1 innerhalb des param()-Blocks noch leer,
# daher erst hier (nach Skriptstart) als Fallback verwenden.
if (-not $RepositoryRoot) { $RepositoryRoot = Join-Path $PSScriptRoot "..\.." }

# =====================================================================
#  Stellt die DATEN-Seite bereit (schnell, ohne pip/npm): Datenordner,
#  Dokumentvorlagen und - falls noch keine DB da ist - die Test-DB.
#  Bewusst idempotent und OHNE Ueberschreiben vorhandener Dateien, damit
#  es bei JEDEM Start laufen kann (install.ps1 UND das Statusfenster).
# =====================================================================

$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
if (-not $DataDir) {
  $base = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }
  $DataDir = Join-Path $base "Mobilfunkverwaltung"
}
$DocDir = Join-Path $DataDir "Dokumente"

New-Item -ItemType Directory -Force -Path `
  $DataDir, (Join-Path $DataDir "logs"), $DocDir, `
  (Join-Path $DataDir "Kuendigungen"), (Join-Path $DataDir "SynoDateien") | Out-Null

# --- Dokumentvorlagen: fehlende .docx nach ...\Dokumente\ kopieren ----
$TemplateSrc = Join-Path $PSScriptRoot "vorlagen"
if (Test-Path $TemplateSrc) {
  foreach ($tpl in (Get-ChildItem -Path $TemplateSrc -Filter *.docx -ErrorAction SilentlyContinue)) {
    $dest = Join-Path $DocDir $tpl.Name
    if (-not (Test-Path $dest)) {
      Copy-Item -Path $tpl.FullName -Destination $dest
      Write-Host "Dokumentvorlage eingerichtet: $($tpl.Name)"
    }
  }
}

# --- Test-Datenbank: nur wenn am Zielort noch KEINE DB liegt ----------
$TargetDb = Join-Path $DataDir "mobilfunk.db"
$SampleDb = Join-Path $PSScriptRoot "mobilfunk.sample.db"
if (-not $NoSampleData -and -not (Test-Path $TargetDb) -and (Test-Path $SampleDb)) {
  Copy-Item -Path $SampleDb -Destination $TargetDb
  Write-Host "Test-Datenbank eingerichtet: $TargetDb (Anmeldung admin/admin - nur zum Testen!)"
}
