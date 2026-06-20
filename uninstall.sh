#!/usr/bin/env bash
# Uninstall script for supergh (sgh)
# Usage: curl -fsSL https://raw.githubusercontent.com/<org>/supergh/main/uninstall.sh | bash

set -euo pipefail

BINARY="sgh"
LOCATIONS=(
  "/usr/local/bin/$BINARY"
  "$HOME/.local/bin/$BINARY"
  "$HOME/bin/$BINARY"
)

echo "Uninstalling sgh..."

removed=false
for loc in "${LOCATIONS[@]}"; do
  if [ -f "$loc" ]; then
    if [ -w "$(dirname "$loc")" ]; then
      rm -f "$loc"
    else
      sudo rm -f "$loc"
    fi
    echo "  Removed: $loc"
    removed=true
  fi
done

# Remove config and logs (optional)
if [ -d "$HOME/.supergh" ]; then
  read -p "  Remove config and logs (~/.supergh)? [y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.supergh"
    echo "  Removed: ~/.supergh"
  fi
fi

# Remove keychain entries
if command -v security &>/dev/null; then
  security delete-generic-password -s "supergh" 2>/dev/null && echo "  Removed keychain entries" || true
fi

if [ "$removed" = true ]; then
  echo "sgh uninstalled."
else
  echo "sgh binary not found in standard locations."
  echo "If installed via pip: pip3 uninstall supergh"
fi
