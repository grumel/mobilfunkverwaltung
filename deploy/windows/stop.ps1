[CmdletBinding()]
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match "run_windows.py" -and $_.CommandLine -match "-$Port|$Port" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "Mobilfunkverwaltung auf Port $Port beendet (falls aktiv)."
