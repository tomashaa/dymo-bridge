# dymo-bridge

Linux replacement for **DYMO Connect Web Service** so [SkyKeeper](https://skykeeper.aero) can print labels on Pop!_OS / Ubuntu.

Listens on `https://127.0.0.1:41951` (same API surface SkyKeeper already uses on Windows/macOS).

## Install

```bash
git clone https://github.com/tomashaa/dymo-bridge.git
cd dymo-bridge
bash packaging/install.sh
```

Then open https://127.0.0.1:41951/ once and trust the self-signed certificate.

## Requirements

- CUPS with DYMO LabelWriter queues (e.g. `LabelWriter-450-DUO-Label`, `LabelWriter-4XL`)
- `python3-pil`, `python3-qrcode`, `python3-cups`

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

**Settings → Printers** (not Files). Files is for document sync (`sk-sync`); label printing belongs with printer setup.
