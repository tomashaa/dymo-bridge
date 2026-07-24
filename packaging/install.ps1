# SkyKeeper Print Helper — Windows installer (prototype)
# Requires: Windows 10+, Python 3.10+ on PATH (python.org or Microsoft Store)
# Installs to %LOCALAPPDATA%\SkyKeeper\dymo-bridge and starts at logon.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $env:LOCALAPPDATA "SkyKeeper\dymo-bridge"
$TaskName = "SkyKeeperPrintHelper"
$Port = if ($env:DYMO_BRIDGE_PORT) { $env:DYMO_BRIDGE_PORT } else { "41971" }

if (-not (Test-Path (Join-Path $Root "dymo_bridge.py"))) {
  Write-Host "Could not find dymo_bridge.py next to packaging\. Aborting."
  exit 1
}

Write-Host ""
Write-Host "============================================"
Write-Host "  SkyKeeper Print Helper — Windows install"
Write-Host "============================================"
Write-Host ""

function Get-PythonExe {
  foreach ($name in @("python", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  return $null
}

$Python = Get-PythonExe
if (-not $Python) {
  Write-Host "Python 3 was not found on PATH."
  Write-Host "Install from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then re-run."
  exit 1
}
Write-Host "==> Using Python: $Python"

Write-Host "==> Installing Python packages (pillow, qrcode, pywin32)…"
& $Python -m pip install --user --upgrade pip | Out-Null
& $Python -m pip install --user "pillow" "qrcode[pil]" "pywin32" "cryptography"
if ($LASTEXITCODE -ne 0) {
  Write-Host "pip install failed."
  exit 1
}

try {
  & $Python -c "import win32print, win32ui; print('pywin32 ok')"
} catch {
  Write-Host "pywin32 import check failed — trying pywin32_postinstall…"
  & $Python -m pywin32_postinstall -install
}

Write-Host "==> Copying files → $Dest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Force (Join-Path $Root "dymo_bridge.py") (Join-Path $Dest "dymo_bridge.py")
if (Test-Path (Join-Path $Root "test-print.py")) {
  Copy-Item -Force (Join-Path $Root "test-print.py") (Join-Path $Dest "test-print.py")
}

$PythonW = $Python -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $PythonW)) { $PythonW = $Python }

$Wrapper = Join-Path $Dest "run-helper.cmd"
@"
@echo off
set DYMO_BRIDGE_PORT=$Port
cd /d "%~dp0"
"$PythonW" "%~dp0dymo_bridge.py"
"@ | Set-Content -Encoding ASCII $Wrapper

Write-Host "==> Registering logon task '$TaskName'…"
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Wrapper`"" -WorkingDirectory $Dest
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "SkyKeeper Print Helper (HTTPS :$Port)" | Out-Null

Write-Host "==> Starting helper now…"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$Wrapper`"" -WorkingDirectory $Dest -WindowStyle Hidden

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. Open https://127.0.0.1:$Port/ and accept/trust the certificate"
Write-Host "  2. SkyKeeper → Settings → Printers → Refresh"
Write-Host "     (status should say SkyKeeper Print Helper)"
Write-Host "  3. Log: $Dest\dymo-bridge.log"
Write-Host "  4. Remove: Unregister-ScheduledTask -TaskName $TaskName"
Write-Host ""
