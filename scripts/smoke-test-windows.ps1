[CmdletBinding()]
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:$Port"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python fehlt." }
$version = Invoke-WebRequest -UseBasicParsing "$base/api/version" -TimeoutSec 5
if ($version.StatusCode -ne 200) { throw "/api/version liefert $($version.StatusCode)." }
$html = Invoke-WebRequest -UseBasicParsing "$base/" -TimeoutSec 5
if ($html.StatusCode -ne 200 -or $html.Content -notmatch '<html') { throw "Frontend liefert kein HTML." }
$asset = [regex]::Match($html.Content, 'src="([^"]+\.js)"').Groups[1].Value
if (-not $asset) { throw "Kein JavaScript-Asset im Frontend." }
$assetResponse = Invoke-WebRequest -UseBasicParsing "$base$asset" -TimeoutSec 5
if ($assetResponse.StatusCode -ne 200) { throw "Asset liefert $($assetResponse.StatusCode)." }
Write-Host "Windows-Smoke-Test erfolgreich. Login-Test optional über SMOKE_USERNAME/SMOKE_PASSWORD."
