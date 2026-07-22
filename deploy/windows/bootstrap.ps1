[CmdletBinding(SupportsShouldProcess)]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
      [string]$DataDir = "",
      [switch]$Install,
      [switch]$CheckOnly)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Prueft die Voraussetzungen der Windows-Runtime, installiert Fehlendes auf
# Wunsch per winget und startet danach install.ps1. Bewusst ohne EXE und ohne
# Signatur: es wird nichts ausgefuehrt, was eine Softwarerichtlinie blockieren
# koennte, ausser diesem Skript selbst.

$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path

function Get-ToolVersion {
    <#  Liefert die Version eines Kommandozeilenwerkzeugs oder $null.
        Der Store-Platzhalter von python.exe gibt keine Version aus und gilt
        deshalb korrekterweise als nicht vorhanden. #>
    param([string]$Command, [string[]]$Arguments = @("--version"))
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { return $null }
    try { $output = & $Command @Arguments 2>&1 | Out-String } catch { return $null }
    $match = [regex]::Match($output, '(\d+)\.(\d+)(?:\.(\d+))?')
    if (-not $match.Success) { return $null }
    return [version]$match.Value
}

function Test-ComComponent {
    param([string]$ProgId)
    try {
        $key = [Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey($ProgId)
        if ($key) { $key.Close(); return $true }
    } catch { }
    return $false
}

function Update-SessionPath {
    # winget aktualisiert die Umgebung des laufenden Prozesses nicht.
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

function Install-Tool {
    param([string]$Name, [string]$PackageId)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget fehlt. 'App Installer' aus dem Microsoft Store nachruesten oder $Name von Hand installieren."
    }
    if (-not $PSCmdlet.ShouldProcess($Name, "per winget installieren ($PackageId)")) { return $false }
    Write-Host "Installiere $Name ..."
    # Erst im Benutzerkontext versuchen; das kommt ohne Administratorrechte aus.
    & winget install --id $PackageId --exact --silent --scope user `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Installation im Benutzerkontext fehlgeschlagen, versuche systemweit (benoetigt Administratorrechte)."
        & winget install --id $PackageId --exact --silent `
            --accept-package-agreements --accept-source-agreements
    }
    Update-SessionPath
    return ($LASTEXITCODE -eq 0)
}

# --- Bestandsaufnahme -------------------------------------------------------

$python = Get-ToolVersion -Command "python"
$node = Get-ToolVersion -Command "node"
$npm = Get-ToolVersion -Command "npm"
$git = Get-ToolVersion -Command "git"
$word = Test-ComComponent -ProgId "Word.Application"
$outlook = Test-ComComponent -ProgId "Outlook.Application"
$soffice = [bool](Get-Command soffice -ErrorAction SilentlyContinue)

$requirements = @(
    [pscustomobject]@{ Name = "Python 3.12+"; Ist = $python; Erfuellt = ($python -and $python -ge [version]"3.12"); Pflicht = $true;  Paket = "Python.Python.3.12" }
    [pscustomobject]@{ Name = "Node.js 20+";  Ist = $node;   Erfuellt = ($node -and $node -ge [version]"20.0");    Pflicht = $true;  Paket = "OpenJS.NodeJS.LTS" }
    [pscustomobject]@{ Name = "npm";          Ist = $npm;    Erfuellt = [bool]$npm;                                Pflicht = $true;  Paket = "OpenJS.NodeJS.LTS" }
    [pscustomobject]@{ Name = "Git";          Ist = $git;    Erfuellt = [bool]$git;                                Pflicht = $true;  Paket = "Git.Git" }
    [pscustomobject]@{ Name = "PDF-Erzeugung (Word oder LibreOffice)"; Ist = $null; Erfuellt = ($word -or $soffice); Pflicht = $false; Paket = "TheDocumentFoundation.LibreOffice" }
    [pscustomobject]@{ Name = "Outlook (Mail-Entwuerfe)"; Ist = $null; Erfuellt = $outlook; Pflicht = $false; Paket = "" }
)

Write-Host ""
Write-Host "Voraussetzungen der Windows-Runtime"
Write-Host "-----------------------------------"
foreach ($item in $requirements) {
    $mark = if ($item.Erfuellt) { "[ok]  " } elseif ($item.Pflicht) { "[fehlt]" } else { "[offen]" }
    $version = if ($item.Ist) { " ($($item.Ist))" } else { "" }
    Write-Host ("{0} {1}{2}" -f $mark, $item.Name, $version)
}
Write-Host ""
if ($word) { Write-Host "Word gefunden: PDF wird ueber Word erzeugt, LibreOffice ist nicht noetig." }
elseif ($soffice) { Write-Host "Kein Word, aber LibreOffice gefunden: PDF wird darueber erzeugt." }
else { Write-Warning "Weder Word noch LibreOffice: Kuendigung und Ruecknahme lassen sich als .docx erzeugen, aber nicht als PDF." }
if (-not $outlook) { Write-Warning "Kein Outlook: die Anwendung zeigt den Mailtext an, statt einen Entwurf zu oeffnen." }

# Ausfuehrungsrichtlinie ist der haeufigste Stolperstein im verwalteten Netz.
$policy = Get-ExecutionPolicy
if ($policy -in @("AllSigned", "Restricted")) {
    Write-Warning "Ausfuehrungsrichtlinie ist '$policy'. Ist sie per Gruppenrichtlinie gesetzt, laesst sie sich mit -ExecutionPolicy Bypass nicht umgehen; dann muessen die Skripte signiert oder von der IT freigegeben werden."
}

# --- Fehlendes nachinstallieren --------------------------------------------

$missing = @($requirements | Where-Object { $_.Pflicht -and -not $_.Erfuellt })
if ($missing.Count -gt 0) {
    Write-Host ""
    if (-not $Install) {
        Write-Host "Es fehlen: $(($missing | ForEach-Object { $_.Name }) -join ', ')"
        Write-Host "Zum automatischen Nachinstallieren erneut mit -Install starten:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\deploy\windows\bootstrap.ps1 -Install"
        return
    }
    foreach ($item in ($missing | Sort-Object -Property Paket -Unique)) {
        Install-Tool -Name $item.Name -PackageId $item.Paket | Out-Null
    }

    Update-SessionPath
    $stillMissing = @()
    $python = Get-ToolVersion -Command "python"
    $node = Get-ToolVersion -Command "node"
    $git = Get-ToolVersion -Command "git"
    if (-not $python -or $python -lt [version]"3.12") { $stillMissing += "Python 3.12+" }
    if (-not $node -or $node -lt [version]"20.0") { $stillMissing += "Node.js 20+" }
    if (-not $git) { $stillMissing += "Git" }
    if ($stillMissing.Count -gt 0) {
        throw ("Weiterhin nicht verfuegbar: {0}. Haeufigste Ursache: die Installation hat den PATH erst fuer neue Sitzungen gesetzt. Bitte PowerShell neu oeffnen und bootstrap.ps1 erneut ausfuehren." -f ($stillMissing -join ", "))
    }
    Write-Host "Alle Pflichtwerkzeuge sind jetzt vorhanden."
}

# --- Weiter zur eigentlichen Installation -----------------------------------

if ($CheckOnly) {
    Write-Host ""
    Write-Host "Nur geprueft. install.ps1 wurde nicht gestartet."
    return
}

Write-Host ""
Write-Host "Starte install.ps1 ..."
$installArgs = @{ RepositoryRoot = $RepositoryRoot }
if ($DataDir) { $installArgs.DataDir = $DataDir }
& (Join-Path $PSScriptRoot "install.ps1") @installArgs
