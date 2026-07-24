# SkyKeeper Print Helper — one-line Windows bootstrap
# Usage (PowerShell):
#   irm https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.ps1 | iex
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ZipUrl = "https://github.com/tomashaa/dymo-bridge/archive/refs/heads/main.zip"
$Tmp = Join-Path $env:TEMP ("sk-dymo-bridge-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

try {
  Write-Host "==> Downloading SkyKeeper Print Helper…"
  $Zip = Join-Path $Tmp "dymo-bridge.zip"
  Invoke-WebRequest -Uri $ZipUrl -OutFile $Zip -UseBasicParsing
  Expand-Archive -Path $Zip -DestinationPath $Tmp -Force
  $Src = Get-ChildItem -Path $Tmp -Directory | Where-Object { $_.Name -like "dymo-bridge-*" } | Select-Object -First 1
  if (-not $Src -or -not (Test-Path (Join-Path $Src.FullName "packaging\install.ps1"))) {
    throw "Could not find packaging\install.ps1 in the download."
  }
  Write-Host "==> Running installer…"
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Src.FullName "packaging\install.ps1")
} finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
