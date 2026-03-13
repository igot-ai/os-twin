#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Agent OS (Ostwin) — Uninstaller
#
# Cleanly removes ostwin from the system.
#
# Usage:
#   ./uninstall.sh              # Interactive — confirm before removing
#   ./uninstall.sh --yes        # Non-interactive — remove without prompting
#   ./uninstall.sh --dir /path  # Remove from custom location
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

INSTALL_DIR="${HOME}/.ostwin"
AUTO_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) AUTO_YES=true; shift ;;
    --dir)    INSTALL_DIR="$2"; shift 2 ;;
    *)        shift ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

echo ""
echo -e "  ${BOLD}Ostwin — Uninstaller${NC}"
echo ""

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo -e "  ${YELLOW}Ostwin not found at $INSTALL_DIR${NC}"
  echo "  Nothing to remove."
  exit 0
fi

echo -e "  Will remove: ${RED}$INSTALL_DIR${NC}"
echo ""

if ! $AUTO_YES; then
  echo -en "  ${YELLOW}?${NC} Are you sure? ${DIM}[y/N]${NC} "
  read -r answer
  case "${answer:-n}" in
    [Yy]*) ;;
    *)     echo "  Cancelled."; exit 0 ;;
  esac
fi

# Remove deepagents-cli if installed via uv
if command -v uv &>/dev/null; then
  echo -e "  ${DIM}Removing deepagents-cli from uv tools...${NC}"
  uv tool uninstall deepagents-cli 2>/dev/null || true
fi

# Remove Pester module
if command -v pwsh &>/dev/null; then
  echo -e "  ${DIM}Note: Pester module left in place (shared PowerShell module)${NC}"
fi

# Remove installation directory
echo -e "  Removing $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"
echo -e "    ${GREEN}[OK]${NC} Files removed"

# Clean PATH from shell RC files
for rc_file in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile" "$HOME/.config/fish/config.fish"; do
  if [[ -f "$rc_file" ]] && grep -q "ostwin" "$rc_file" 2>/dev/null; then
    echo -e "  Cleaning $rc_file..."
    if [[ "$(uname -s)" == "Darwin" ]]; then
      sed -i '' '/# Ostwin CLI/d;/ostwin/d' "$rc_file"
    else
      sed -i '/# Ostwin CLI/d;/ostwin/d' "$rc_file"
    fi
    echo -e "    ${GREEN}[OK]${NC} PATH entry removed"
  fi
done

echo ""
echo -e "  ${GREEN}${BOLD}Uninstall complete.${NC}"
echo ""
echo -e "  ${DIM}Note: API keys (GOOGLE_API_KEY, etc.) are not removed.${NC}"
echo -e "  ${DIM}Note: Project .agents/ directories are not affected.${NC}"
echo ""
