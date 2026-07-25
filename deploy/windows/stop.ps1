[CmdletBinding()]
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# Der Port steht nicht in der Kommandozeile, sondern nur in der Umgebung des
# Prozesses. Deshalb wird der Port ueber den lauschenden Socket aufgeloest.
$owners = @()
try { $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique) } catch { $owners = @() }
if ($owners.Count -eq 0) { Write-Host "Auf Port $Port lauscht kein Prozess."; return }
$runtime = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match "run_windows\.py" -and $owners -contains $_.ProcessId })
if ($runtime.Count -eq 0) { throw "Port $Port wird von einem fremden Prozess belegt (PID $($owners -join ', ')). Es wurde nichts beendet." }
$runtime | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "Mobilfunkverwaltung auf Port $Port beendet (PID $(($runtime | ForEach-Object { $_.ProcessId }) -join ', '))."
