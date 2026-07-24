#!/usr/bin/env bash
# Install dymo-bridge for SkyKeeper on Linux (Pop!_OS / Ubuntu).
# Replaces DYMO Connect Web Service on https://127.0.0.1:41951
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/dymo-bridge"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Installing dependencies (needs sudo once)"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-pil python3-qrcode python3-cups cups cups-client openssl
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3-pillow python3-qrcode python3-cups cups openssl
else
  echo "Install python3-pil, python3-qrcode, python3-cups, cups, and openssl manually, then re-run."
  exit 1
fi

echo "==> Copying bridge to $DEST"
mkdir -p "$DEST"
install -m 0644 "$ROOT/dymo_bridge.py" "$DEST/dymo_bridge.py"
if [[ -f "$ROOT/test-print.py" ]]; then
  install -m 0644 "$ROOT/test-print.py" "$DEST/test-print.py"
fi

echo "==> Installing systemd --user service"
mkdir -p "$UNIT_DIR"
install -m 0644 "$ROOT/packaging/dymo-bridge.service" "$UNIT_DIR/dymo-bridge.service"
systemctl --user daemon-reload
systemctl --user enable --now dymo-bridge.service

# Prefer Large Address (36x89mm) for LabelWriter 450 DUO Label queues if present
if lpstat -a 2>/dev/null | grep -q 'LabelWriter-450-DUO-Label'; then
  echo "==> Setting CUPS media=w102h252 on LabelWriter-450-DUO-Label"
  lpoptions -p LabelWriter-450-DUO-Label -o media=w102h252 || true
fi

echo
echo "Installed. Next steps:"
echo "  1. Open https://127.0.0.1:41951/ in your browser and trust the certificate"
echo "  2. SkyKeeper → Settings → Printers → Refresh"
echo "  3. Status: systemctl --user status dymo-bridge"
echo "  4. Log:    $DEST/dymo-bridge.log"
echo
systemctl --user --no-pager status dymo-bridge.service | head -12 || true
