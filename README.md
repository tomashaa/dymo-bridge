# dymo-bridge (SkyKeeper Print Helper)

Local label-print helper for [SkyKeeper](https://skykeeper.aero). Speaks the same API as DYMO Connect, on a **dedicated port** so both can coexist:

| Service | Port | Role |
|---------|------|------|
| **SkyKeeper Print Helper** (this repo) | `41971` | Preferred by SkyKeeper |
| Official DYMO Connect | `41951`–`41960` | Automatic fallback |

| OS | Status | Backend | Autostart |
|----|--------|---------|-----------|
| **Linux** | Supported | CUPS / `lp` | `systemd --user` |
| **macOS** | Supported | CUPS / `lpstat`+`lp` | LaunchAgent |
| **Windows** | Prototype | win32print / GDI | Scheduled Task |

---

## Linux & macOS — easy install

Same one-liner (detects OS):

```bash
curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
```

Then:

1. Open https://127.0.0.1:41971/ and **trust** the certificate  
2. SkyKeeper → **Settings → Printers → Refresh** → **SkyKeeper Print Helper**

### Manual

```bash
# Linux
bash packaging/install.sh

# macOS
bash packaging/install-mac.sh
```

---

## Windows — prototype install

1. Install [Python 3](https://www.python.org/downloads/) (tick **Add python.exe to PATH**)
2. DYMO printer drivers installed
3. PowerShell:

```powershell
irm https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.ps1 | iex
```

---

## Requirements

- DYMO LabelWriter visible to the OS
- Linux: apt/dnf packages via `install.sh`
- macOS: `python3` + `pip install pillow qrcode cryptography` (done by installer)
- Windows: `pillow`, `qrcode`, `pywin32`, `cryptography`

Override port: `DYMO_BRIDGE_PORT=41971` (default).

## Manage

**Linux**

```bash
systemctl --user status dymo-bridge
systemctl --user restart dymo-bridge
```

**macOS**

```bash
launchctl print "gui/$(id -u)/com.skykeeper.print-helper"
launchctl kickstart -k "gui/$(id -u)/com.skykeeper.print-helper"
# Remove autostart:
launchctl bootout "gui/$(id -u)/com.skykeeper.print-helper"
rm ~/Library/LaunchAgents/com.skykeeper.print-helper.plist
# Files: ~/Library/Application Support/SkyKeeper/dymo-bridge/
```

**Windows**

```powershell
Get-ScheduledTask -TaskName SkyKeeperPrintHelper
Unregister-ScheduledTask -TaskName SkyKeeperPrintHelper -Confirm:$false
```

## SkyKeeper UI

**Settings → Printers** — OS-highlighted install cards + status badge (Print Helper vs DYMO Connect).
