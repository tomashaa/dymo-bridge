#!/usr/bin/env bash
# SkyKeeper Print Helper — one-command installer for Linux and macOS.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/tomashaa/dymo-bridge/main/packaging/bootstrap.sh | bash
# Windows: use packaging/bootstrap.ps1 instead.
set -euo pipefail

REPO_TAR="https://github.com/tomashaa/dymo-bridge/archive/refs/heads/main.tar.gz"
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

OS="$(uname -s)"
case "$OS" in
  Linux)  TITLE="Linux"; INSTALLER="install.sh" ;;
  Darwin) TITLE="macOS"; INSTALLER="install-mac.sh" ;;
  *)
    echo "Unsupported OS: $OS"
    echo "  Linux/macOS: this script"
    echo "  Windows:     irm …/bootstrap.ps1 | iex"
    exit 1
    ;;
esac

echo ""
echo "============================================"
echo "  SkyKeeper Print Helper — ${TITLE} installer"
echo "============================================"
echo ""
echo "Installs a local service on https://127.0.0.1:41971"
echo "so SkyKeeper can print labels (DYMO Connect remains fallback)."
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
if [[ -z "$SRC" || ! -f "$SRC/packaging/${INSTALLER}" ]]; then
  echo "Download failed — could not find packaging/${INSTALLER} in the archive."
  exit 1
fi

echo "==> Running ${INSTALLER}…"
bash "$SRC/packaging/${INSTALLER}"

echo ""
echo "============================================"
echo "  Done. Two clicks left:"
echo "============================================"
echo "  1. Open https://127.0.0.1:41971/ and accept/trust the certificate"
echo "  2. In SkyKeeper: Settings → Printers → Refresh"
echo ""
