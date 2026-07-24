#!/usr/bin/env bash
# Install dymo-bridge for SkyKeeper on Linux (Pop!_OS / Cosmic / Ubuntu).
# SkyKeeper Print Helper on https://127.0.0.1:41971 (DYMO Connect may use 41951)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/dymo-bridge"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
PORT="${DYMO_BRIDGE_PORT:-41971}"
PY="$(command -v python3 || true)"

if [[ -z "$PY" ]]; then
  echo "python3 not found. Install python3, then re-run."
  exit 1
fi

echo "==> Installing dependencies (password prompt is normal — once)"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-pil python3-qrcode python3-cups cups cups-client openssl
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3-pillow python3-qrcode python3-cups cups openssl
else
  echo "Could not detect apt or dnf."
  echo "Please install manually: python3-pil (or pillow), python3-qrcode, python3-cups, cups, openssl"
  echo "Then re-run this installer."
  exit 1
fi

echo "==> Installing bridge files → $DEST"
mkdir -p "$DEST"
install -m 0644 "$ROOT/dymo_bridge.py" "$DEST/dymo_bridge.py"
if [[ -f "$ROOT/test-print.py" ]]; then
  install -m 0644 "$ROOT/test-print.py" "$DEST/test-print.py"
fi

echo "==> Starting background service (systemd --user)"
mkdir -p "$UNIT_DIR"
# Embed absolute paths so XDG_DATA_HOME / non-default python still work
cat > "$UNIT_DIR/dymo-bridge.service" <<EOF
[Unit]
Description=SkyKeeper Print Helper (dymo-bridge)
After=cups.service network-online.target

[Service]
Type=simple
Environment=DYMO_BRIDGE_PORT=${PORT}
WorkingDirectory=${DEST}
ExecStart=${PY} ${DEST}/dymo_bridge.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now dymo-bridge.service

# Prefer Large Address (36x89mm) for LabelWriter 450 DUO Label queues if present
if lpstat -a 2>/dev/null | grep -q 'LabelWriter-450-DUO-Label'; then
  echo "==> Setting correct label size on LabelWriter-450-DUO-Label"
  lpoptions -p LabelWriter-450-DUO-Label -o media=w102h252 || true
fi

echo
echo "Bridge installed and started."
echo "  Status: systemctl --user status dymo-bridge"
echo "  Log:    $DEST/dymo-bridge.log"
echo "  Trust:  https://127.0.0.1:${PORT}/"
echo
systemctl --user --no-pager status dymo-bridge.service | head -12 || true
