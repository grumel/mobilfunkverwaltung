# =====================================================================
#  Mobilfunkverwaltung – kleines Statusfenster
#  Startet den lokalen Server im Hintergrund (Konsole versteckt) und
#  zeigt ein schlankes Fenster mit Statussymbol, Link und Beenden-Knopf.
#  Aufruf (versteckt) am besten ueber Mobilfunkverwaltung-Fenster.cmd.
# =====================================================================
[CmdletBinding()]
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"

# --- Eigene Konsole verstecken (falls doch eine sichtbar ist) --------
try {
  $win = Add-Type -PassThru -Name W -Namespace Native -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern System.IntPtr GetConsoleWindow();
[DllImport("user32.dll")]   public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
'@
  if ($win -is [array]) { $win = $win[0] }
  $win::ShowWindow($win::GetConsoleWindow(), 0) | Out-Null   # 0 = SW_HIDE
} catch { }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Pfade -----------------------------------------------------------
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $RepositoryRoot "backend"
$Python  = Join-Path $Backend ".venv\Scripts\python.exe"
$RunPy   = Join-Path $Backend "run_windows.py"
$Dist    = Join-Path $RepositoryRoot "frontend\dist\index.html"
$base    = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }
$DataDir = Join-Path $base "Mobilfunkverwaltung"
$EnvFile = Join-Path $DataDir "mobilfunk.env.ps1"
$Url     = "http://127.0.0.1:$Port/"

function Show-Error($text) {
  [System.Windows.Forms.MessageBox]::Show($text, "Mobilfunkverwaltung",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
}

if (-not (Test-Path $Python) -or -not (Test-Path $Dist) -or -not (Test-Path $EnvFile)) {
  Show-Error("Die Laufzeit ist noch nicht eingerichtet.`n`nBitte zuerst einmal " +
             "'Mobilfunkverwaltung.cmd' ausfuehren (Erstinstallation).")
  return
}

# --- Umgebung laden und Server im Hintergrund starten ----------------
. $EnvFile
$env:MOBILFUNK_HOST = "127.0.0.1"
$env:MOBILFUNK_PORT = "$Port"
$env:MOBILFUNK_NO_BROWSER = "1"

$script:proc = $null
try {
  $script:proc = Start-Process -FilePath $Python -ArgumentList $RunPy `
      -WorkingDirectory $Backend -WindowStyle Hidden -PassThru
} catch {
  Show-Error("Server konnte nicht gestartet werden:`n$($_.Exception.Message)")
  return
}

function Stop-Server {
  if ($script:proc -and -not $script:proc.HasExited) {
    try { Stop-Process -Id $script:proc.Id -Force -ErrorAction SilentlyContinue } catch { }
  }
}

# --- Fenster aufbauen ------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "Mobilfunkverwaltung"
$form.Size = New-Object System.Drawing.Size(430, 250)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblInfo = New-Object System.Windows.Forms.Label
$lblInfo.Text = "Die Mobilfunk-Datenverwaltung laeuft lokal auf diesem Rechner. Sobald der Status gruen ist, ist sie im Browser unter diesem Link erreichbar:"
$lblInfo.Location = New-Object System.Drawing.Point(18, 15)
$lblInfo.Size = New-Object System.Drawing.Size(390, 55)
$form.Controls.Add($lblInfo)

$llUrl = New-Object System.Windows.Forms.LinkLabel
$llUrl.Text = $Url
$llUrl.Location = New-Object System.Drawing.Point(18, 72)
$llUrl.Size = New-Object System.Drawing.Size(390, 22)
$llUrl.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$llUrl.Add_LinkClicked({ Start-Process $Url }) | Out-Null
$form.Controls.Add($llUrl)

# Statuszeile: farbiges Symbol + Text
$lblDot = New-Object System.Windows.Forms.Label
$lblDot.Text = [char]0x25CF   # ●
$lblDot.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$lblDot.ForeColor = [System.Drawing.Color]::Orange
$lblDot.Location = New-Object System.Drawing.Point(18, 108)
$lblDot.Size = New-Object System.Drawing.Size(24, 26)
$form.Controls.Add($lblDot)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Status: wird gestartet ..."
$lblStatus.Location = New-Object System.Drawing.Point(44, 112)
$lblStatus.Size = New-Object System.Drawing.Size(364, 22)
$form.Controls.Add($lblStatus)

# Knöpfe
$btnOpen = New-Object System.Windows.Forms.Button
$btnOpen.Text = "Im Browser oeffnen"
$btnOpen.Location = New-Object System.Drawing.Point(18, 160)
$btnOpen.Size = New-Object System.Drawing.Size(180, 40)
$btnOpen.Enabled = $false
$btnOpen.Add_Click({ Start-Process $Url }) | Out-Null
$form.Controls.Add($btnOpen)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = "Beenden"
$btnStop.Location = New-Object System.Drawing.Point(228, 160)
$btnStop.Size = New-Object System.Drawing.Size(180, 40)
$btnStop.Add_Click({ $form.Close() }) | Out-Null
$form.Controls.Add($btnStop)

# --- Statusabfrage per Timer ----------------------------------------
$script:opened = $false
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({
  if ($script:proc.HasExited) {
    $lblDot.ForeColor = [System.Drawing.Color]::Red
    $lblStatus.Text = "Status: gestoppt (Server-Prozess beendet)"
    $btnOpen.Enabled = $false
    return
  }
  $ok = $false
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 "http://127.0.0.1:$Port/api/version"
    if ($r.StatusCode -eq 200) { $ok = $true }
  } catch { $ok = $false }
  if ($ok) {
    $lblDot.ForeColor = [System.Drawing.Color]::SeaGreen
    $lblStatus.Text = "Status: laeuft - im Browser erreichbar"
    $btnOpen.Enabled = $true
    if (-not $script:opened) { $script:opened = $true; Start-Process $Url }
  } else {
    $lblDot.ForeColor = [System.Drawing.Color]::Orange
    $lblStatus.Text = "Status: wird gestartet ..."
  }
})
$timer.Start()

# Beim Schliessen sauber stoppen
$form.Add_FormClosing({ $timer.Stop(); Stop-Server }) | Out-Null

[void]$form.ShowDialog()
Stop-Server
