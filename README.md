# dymo-bridge

Linux replacement for **DYMO Connect Web Service** so [SkyKeeper](https://skykeeper.aero) can print labels on Pop!_OS, Cosmic, Ubuntu, and similar.

Listens on `https://127.0.0.1:41951` (same API SkyKeeper already uses on Windows/macOS).

## Easy install (recommended)

1. Open **Terminal**
2. Paste this **one line** and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
```

3. Open https://127.0.0.1:41951/ once and **trust / accept** the certificate warning  
4. In SkyKeeper: **Settings → Printers → Refresh**

The installer asks for your password once (`sudo`) to install CUPS/Python packages.

### Alternative: download the script

1. Download [`packaging/bootstrap.sh`](https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh) (save as e.g. `install-skykeeper-dymo-bridge.sh`)
2. In Terminal:

```bash
bash ~/Downloads/install-skykeeper-dymo-bridge.sh
```

### Manual (developers)

```bash
git clone https://github.com/tomashaa/dymo-bridge.git
cd dymo-bridge
bash packaging/install.sh
```

## Requirements

- CUPS with DYMO LabelWriter queues (e.g. `LabelWriter-450-DUO-Label`, `LabelWriter-4XL`)
- `python3-pil`, `python3-qrcode`, `python3-cups` (installed automatically via apt/dnf)

## What it fixes

| Issue | Handling |
|-------|----------|
| No official DYMO Connect on Linux | Local HTTPS shim |
| Simple labels spanning two stickers | Sets CUPS `media=` from label `PaperName` (30321 → `w102h252`) |
| Wrong printer selected | Strict queue matching (no silent DUO→4XL fallback) |

## Manage

```bash
systemctl --user status dymo-bridge
systemctl --user restart dymo-bridge
journalctl --user -u dymo-bridge -f
# or: ~/.local/share/dymo-bridge/dymo-bridge.log
```

## SkyKeeper UI

**Settings → Printers** — copy the one-line install or download the script.  
(Not under Files: that installer is for document sync only.)
