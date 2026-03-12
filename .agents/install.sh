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
#   - uv (https://github.com/astral-sh/uv)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${1:-$HOME/.ostwin}"
VENV_DIR="$INSTALL_DIR/.venv"

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

if ! command -v uv &>/dev/null; then
  echo "    [FAIL] uv not found — required"
  echo "           Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "           Or via Homebrew: brew install uv"
  DEPS_OK=false
else
  UV_VER=$(uv --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  echo "    [OK] uv $UV_VER"
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

# Set up uv venv and install Python dependencies
echo "  Setting up Python environment with uv..."
[ -d "$VENV_DIR" ] || uv venv "$VENV_DIR" --quiet
echo "    [OK] venv created at $VENV_DIR"

REQUIREMENTS="$INSTALL_DIR/mcp/requirements.txt"
if [ -f "$REQUIREMENTS" ]; then
  uv pip install --quiet --python "$VENV_DIR/bin/python" -r "$REQUIREMENTS"
  echo "    [OK] Python dependencies installed from mcp/requirements.txt"
else
  echo "    [WARN] No mcp/requirements.txt found — skipping pip install"
fi

# Patch mcp-config.json with actual venv python path
MCP_CONFIG="$INSTALL_DIR/mcp/mcp-config.json"
if [ -f "$MCP_CONFIG" ]; then
  sed -i '' "s|OSTWIN_VENV_PYTHON|$VENV_DIR/bin/python|g" "$MCP_CONFIG"
  echo "    [OK] mcp-config.json patched with venv python path"
fi

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
