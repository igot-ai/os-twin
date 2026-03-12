#!/usr/bin/env bash
# Agent OS — Installer
#
# Installs ostwin CLI to ~/.ostwin and adds to PATH.
#
# Usage:
#   ./install.sh               # Install to ~/.ostwin
#   ./install.sh /opt/ostwin # Install to custom location
#
# Requirements:
#   - bash 3.2+
#   - python3 3.8+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${1:-$HOME/.ostwin}"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        Ostwin — Installer             ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check dependencies
echo "  Checking dependencies..."
DEPS_OK=true

if ! command -v bash &>/dev/null; then
  echo "    [FAIL] bash not found"
  DEPS_OK=false
else
  BASH_VER=$(bash --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
  echo "    [OK] bash $BASH_VER"
fi

if ! command -v python3 &>/dev/null; then
  echo "    [FAIL] python3 not found — required"
  DEPS_OK=false
else
  PY_VER=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
  echo "    [OK] python3 $PY_VER"
fi

# Check for timeout (optional)
if command -v timeout &>/dev/null; then
  echo "    [OK] timeout (coreutils)"
elif command -v gtimeout &>/dev/null; then
  echo "    [OK] gtimeout (coreutils via Homebrew)"
else
  echo "    [WARN] timeout not found — will use perl fallback"
  echo "           Install coreutils for better timeout support:"
  echo "           brew install coreutils"
fi

echo ""

if ! $DEPS_OK; then
  echo "  [ERROR] Missing required dependencies. Install them and retry." >&2
  exit 1
fi

# Install
echo "  Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy the entire .agents directory
cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/".* "$INSTALL_DIR/" 2>/dev/null || true

# Make scripts executable
find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \;
chmod +x "$INSTALL_DIR/bin/ostwin" 2>/dev/null || true

echo "    [OK] Files installed"

# Add to PATH
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
  zsh)  SHELL_RC="$HOME/.zshrc" ;;
  bash) SHELL_RC="$HOME/.bashrc" ;;
  *)    SHELL_RC="$HOME/.profile" ;;
esac

PATH_LINE="export PATH=\"$INSTALL_DIR/bin:\$PATH\""

if grep -qF "ostwin" "$SHELL_RC" 2>/dev/null; then
  echo "    [OK] PATH already configured in $SHELL_RC"
else
  echo "" >> "$SHELL_RC"
  echo "# Ostwin CLI" >> "$SHELL_RC"
  echo "$PATH_LINE" >> "$SHELL_RC"
  echo "    [OK] Added to PATH in $SHELL_RC"
fi

echo ""
echo "  Installation complete!"
echo ""
echo "  To use now:   source $SHELL_RC"
echo "  Or new shell: ostwin --help"
echo ""
echo "  Quick start:"
echo "    ostwin init ~/my-project"
echo "    cd ~/my-project"
echo "    ostwin run .agents/plans/PLAN.template.md --dry-run"
echo ""
