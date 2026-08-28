[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
      [string]$DataDir = "",
      [switch]$NoSampleData)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
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
if (-not (Test-Path $Python)) { & python -m venv $Venv; if ($LASTEXITCODE) { throw "Venv konnte nicht erstellt werden." } }
& $Python -m pip install -r (Join-Path $Backend "requirements.txt") -r (Join-Path $Backend "requirements-server.txt")
if ($LASTEXITCODE) { throw "Python-Abhängigkeiten konnten nicht installiert werden." }
if ($NeedBuild) {
  Write-Host "Frontend wird aus dem Quellcode gebaut (kein fertiger Build im Paket) ..."
  Push-Location $Frontend
  try { & npm ci --no-fund --no-audit; if ($LASTEXITCODE) { throw "npm ci fehlgeschlagen." }; & npm run build; if ($LASTEXITCODE) { throw "Frontend-Build fehlgeschlagen." } }
  finally { Pop-Location }
}
else {
  Write-Host "Fertiger Frontend-Build gefunden – npm/Node nicht noetig."
}
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
# Test-Datenbank bereitstellen: nur wenn am Zielort noch KEINE DB liegt
# (eine echte Datenbank wird niemals überschrieben). Mit -NoSampleData abschaltbar.
$TargetDb = Join-Path $DataDir "mobilfunk.db"
$SampleDb = Join-Path $PSScriptRoot "mobilfunk.sample.db"
if (-not $NoSampleData -and -not (Test-Path $TargetDb) -and (Test-Path $SampleDb)) {
  Copy-Item -Path $SampleDb -Destination $TargetDb
  Write-Host ""
  Write-Host "Test-Datenbank eingerichtet: $TargetDb" -ForegroundColor Yellow
  Write-Host "  Anmeldung: admin / admin  (nur zum Testen!)" -ForegroundColor Yellow
  Write-Host "  Fuer den Echtbetrieb diese Datei durch die richtige mobilfunk.db" -ForegroundColor Yellow
  Write-Host "  ersetzen bzw. die Passwoerter aendern." -ForegroundColor Yellow
}
elseif (Test-Path $TargetDb) {
  Write-Host "Vorhandene Datenbank bleibt unveraendert: $TargetDb"
}

# Dokumentvorlagen (Kuendigung/Ruecknahme) bereitstellen: mitgelieferte .docx
# nach ...\Dokumente\ kopieren, aber nur wenn dort noch keine gleichnamige liegt
# (echte, angepasste Vorlagen werden nie ueberschrieben).
$TemplateSrc = Join-Path $PSScriptRoot "vorlagen"
$DocDir = Join-Path $DataDir "Dokumente"
if (Test-Path $TemplateSrc) {
  foreach ($tpl in (Get-ChildItem -Path $TemplateSrc -Filter *.docx -ErrorAction SilentlyContinue)) {
    $dest = Join-Path $DocDir $tpl.Name
    if (-not (Test-Path $dest)) {
      Copy-Item -Path $tpl.FullName -Destination $dest
      Write-Host "Dokumentvorlage eingerichtet: $($tpl.Name)"
    }
  }
}

Write-Host "Windows-Laufzeit vorbereitet: $DataDir"
Write-Host "Start: powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1"
