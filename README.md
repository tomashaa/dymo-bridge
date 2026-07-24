# dymo-bridge (SkyKeeper Print Helper)

Local label-print helper for [SkyKeeper](https://skykeeper.aero). Speaks the same API as DYMO Connect, on a **dedicated port** so both can coexist:

| Service | Port | Role |
|---------|------|------|
| **SkyKeeper Print Helper** (this repo) | `41971` | Preferred by SkyKeeper |
| Official DYMO Connect | `41951`–`41960` | Automatic fallback |

| OS | Status | Backend |
|----|--------|---------|
| **Linux** (Pop!_OS / Cosmic / Ubuntu) | Supported | CUPS |
| **Windows** | Prototype | win32print / GDI (`pywin32`) |
| **macOS** | Planned | CUPS / `lp` |

---

## Linux — easy install

```bash
curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
```

Then open https://127.0.0.1:41971/ and trust the certificate → SkyKeeper **Settings → Printers → Refresh**.

---

## Windows — prototype install

1. Install [Python 3](https://www.python.org/downloads/) (tick **Add python.exe to PATH**)
2. Install DYMO printer drivers (Windows printer list must show your LabelWriter)
3. Open **PowerShell** and run:

```powershell
irm https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.ps1 | iex
```

4. Open https://127.0.0.1:41971/ and trust the certificate  
5. SkyKeeper → **Settings → Printers → Refresh** → status **SkyKeeper Print Helper**

### Manual (from a clone)

```powershell
cd dymo-bridge
powershell -ExecutionPolicy Bypass -File packaging\install.ps1
```

The installer copies files to `%LOCALAPPDATA%\SkyKeeper\dymo-bridge`, registers a logon scheduled task, and starts the helper.

---

## Requirements

- DYMO LabelWriter visible to the OS (CUPS on Linux, Windows printer queue on Windows)
- Linux: `python3-pil`, `python3-qrcode`, `python3-cups`
- Windows: `pillow`, `qrcode`, `pywin32` (installed by the script)

Override port: `DYMO_BRIDGE_PORT=41971` (default).

## Manage

**Linux**

```bash
systemctl --user status dymo-bridge
systemctl --user restart dymo-bridge
```

**Windows**

```powershell
Get-ScheduledTask -TaskName SkyKeeperPrintHelper
Unregister-ScheduledTask -TaskName SkyKeeperPrintHelper -Confirm:$false   # uninstall autostart
# Log: %LOCALAPPDATA%\SkyKeeper\dymo-bridge\dymo-bridge.log
```

## SkyKeeper UI

**Settings → Printers** — platform-specific install card + status badge (Print Helper vs DYMO Connect).
