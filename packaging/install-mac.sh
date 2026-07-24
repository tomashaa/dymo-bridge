#!/usr/bin/env bash
# SkyKeeper Print Helper — macOS installer
# Listens on https://127.0.0.1:41971 ; LaunchAgent autostart at login.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/Library/Application Support/SkyKeeper/dymo-bridge"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_LABEL="com.skykeeper.print-helper"
PLIST="${PLIST_DIR}/${PLIST_LABEL}.plist"
PORT="${DYMO_BRIDGE_PORT:-41971}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS. On Linux use packaging/install.sh"
  exit 1
fi

echo ""
echo "============================================"
echo "  SkyKeeper Print Helper — macOS install"
echo "============================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install from https://www.python.org/downloads/ or: brew install python"
  exit 1
fi

PY="$(command -v python3)"
echo "==> Using Python: $PY"

echo "==> Installing Python packages (pillow, qrcode, cryptography)…"
"$PY" -m pip install --user --upgrade pip >/dev/null 2>&1 || true
"$PY" -m pip install --user "pillow" "qrcode[pil]" "cryptography"

echo "==> Installing bridge files → $DEST"
mkdir -p "$DEST"
install -m 0644 "$ROOT/dymo_bridge.py" "$DEST/dymo_bridge.py"
if [[ -f "$ROOT/test-print.py" ]]; then
  install -m 0644 "$ROOT/test-print.py" "$DEST/test-print.py"
fi

echo "==> Writing LaunchAgent $PLIST_LABEL (login autostart)…"
mkdir -p "$PLIST_DIR"
# Unload previous if present
launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${DEST}/dymo_bridge.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${DEST}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DYMO_BRIDGE_PORT</key>
    <string>${PORT}</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${DEST}/dymo-bridge.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${DEST}/dymo-bridge.launchd.err.log</string>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null \
  || launchctl load -w "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true

sleep 1
echo
echo "Installed and started."
echo "  1. Open https://127.0.0.1:${PORT}/ and trust the certificate"
echo "  2. SkyKeeper → Settings → Printers → Refresh"
echo "  3. Log:    ${DEST}/dymo-bridge.log"
echo "  4. Stop:   launchctl bootout gui/\$(id -u)/${PLIST_LABEL}"
echo "  5. Remove: rm \"$PLIST\" && rm -rf \"$DEST\""
echo
