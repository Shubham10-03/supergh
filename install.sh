#!/usr/bin/env bash
# Install script for supergh (sgh)
# Usage: curl -fsSL https://raw.githubusercontent.com/Shubham10-03/supergh/main/install.sh | bash

set -euo pipefail

REPO="Shubham10-03/supergh"  
INSTALL_DIR="/usr/local/bin"
BINARY="sgh"

# Detect platform
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux)  PLATFORM="linux" ;;
  Darwin) PLATFORM="macos" ;;
  *) echo "Unsupported OS: $OS"; exit 1 ;;
esac

case "$ARCH" in
  x86_64|amd64) ARCH="x86_64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

ARTIFACT="sgh-${PLATFORM}-${ARCH}"

# Get latest release tag
LATEST=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)

if [ -z "$LATEST" ]; then
  echo "Failed to fetch latest release."
  exit 1
fi

URL="https://github.com/${REPO}/releases/download/${LATEST}/${ARTIFACT}"

echo "Installing sgh ${LATEST} (${PLATFORM}/${ARCH})..."

# Download
curl -fsSL "$URL" -o "/tmp/${BINARY}"
chmod +x "/tmp/${BINARY}"

# Install (may need sudo)
if [ -w "$INSTALL_DIR" ]; then
  mv "/tmp/${BINARY}" "${INSTALL_DIR}/${BINARY}"
else
  echo "Need sudo to install to ${INSTALL_DIR}"
  sudo mv "/tmp/${BINARY}" "${INSTALL_DIR}/${BINARY}"
fi

echo "Installed: $(which sgh)"
echo "Version:   $(sgh --version)"
echo ""
echo "Run 'sgh setup' to configure your organization, logging, and authentication."
