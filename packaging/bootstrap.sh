#!/usr/bin/env bash
# SkyKeeper DYMO Bridge — one-command installer for Linux (Pop!_OS / Ubuntu / Cosmic).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
# Or download this file, then:  bash install-skykeeper-dymo-bridge.sh
set -euo pipefail

REPO_TAR="https://github.com/tomashaa/dymo-bridge/archive/refs/heads/main.tar.gz"
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo ""
echo "============================================"
echo "  SkyKeeper DYMO Bridge — Linux installer"
echo "============================================"
echo ""
echo "This installs a small local service so SkyKeeper"
echo "can print labels (same as DYMO Connect on Windows)."
echo ""

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required tool: $1"
    echo "Install it, then run this installer again."
    exit 1
  fi
}

need_cmd curl
need_cmd tar
need_cmd bash

echo "==> Downloading dymo-bridge…"
curl -fsSL "$REPO_TAR" -o "$TMP/dymo-bridge.tar.gz"
tar -xzf "$TMP/dymo-bridge.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'dymo-bridge-*' | head -1)"
if [[ -z "$SRC" || ! -f "$SRC/packaging/install.sh" ]]; then
  echo "Download failed — could not find install.sh in the archive."
  exit 1
fi

echo "==> Running install…"
bash "$SRC/packaging/install.sh"

echo ""
echo "============================================"
echo "  Done. Two clicks left:"
echo "============================================"
echo "  1. Open https://127.0.0.1:41951/ and accept/trust the certificate"
echo "  2. In SkyKeeper: Settings → Printers → Refresh"
echo ""
