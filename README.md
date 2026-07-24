# dymo-bridge (SkyKeeper Print Helper)

Linux label-print helper for [SkyKeeper](https://skykeeper.aero). Speaks the same local API as DYMO Connect, on a **dedicated port** so both can coexist:

| Service | Port | Role |
|---------|------|------|
| **SkyKeeper Print Helper** (this repo) | `41971` | Preferred by SkyKeeper |
| Official DYMO Connect | `41951`–`41960` | Automatic fallback |

## Easy install

```bash
curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
```

Then:

1. Open https://127.0.0.1:41971/ and **trust / accept** the certificate  
2. SkyKeeper → **Settings → Printers → Refresh** (status should say **SkyKeeper Print Helper**)

Override port if needed: `DYMO_BRIDGE_PORT=41971` (default).

## Manual

```bash
git clone https://github.com/tomashaa/dymo-bridge.git
cd dymo-bridge
bash packaging/install.sh
```

## Requirements

- CUPS with DYMO LabelWriter queues
- `python3-pil`, `python3-qrcode`, `python3-cups` (installed by the script on apt/dnf)

## Manage

```bash
systemctl --user status dymo-bridge
systemctl --user restart dymo-bridge
journalctl --user -u dymo-bridge -f
```

## SkyKeeper UI

**Settings → Printers** — copy one-line install or download the `.sh` installer.
