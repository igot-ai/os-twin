#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Agent OS — MCP Initialization
#
# Sets up the per-project MCP configuration and optionally installs
# MCP extensions from the catalog.
#
# Usage:
#   ostwin init [target-directory]        # Interactive mode
#   ostwin init [target-directory] --yes  # Non-interactive
#
# If no directory is specified, initializes in the current directory.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Argument parsing ────────────────────────────────────────────────────────

TARGET_DIR=""
AUTO_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)  AUTO_YES=true; shift ;;
    --help|-h)
      head -14 "$0" | tail -12
      exit 0
      ;;
    *)
      if [[ -z "$TARGET_DIR" ]]; then
        TARGET_DIR="$1"
      fi
      shift
      ;;
  esac
done

TARGET_DIR="${TARGET_DIR:-.}"
TARGET_AGENTS="$TARGET_DIR/.agents"

# ─── Colors & formatting ─────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ok()      { echo -e "    ${GREEN}✓${NC} $1"; }
warn()    { echo -e "    ${YELLOW}⚠${NC} $1"; }
fail()    { echo -e "    ${RED}✗${NC} $1"; }
info()    { echo -e "    ${DIM}$1${NC}"; }
step()    { echo -e "  ${CYAN}→${NC} $1"; }

ask() {
  local prompt="$1"
  if $AUTO_YES; then
    return 1  # Skip interactive prompts in --yes mode
  fi
  echo -en "    ${YELLOW}?${NC} $prompt ${DIM}[y/N]${NC} "
  read -r answer
  case "${answer:-n}" in
    [Yy]*) return 0 ;;
    *)     return 1 ;;
  esac
}

# ─── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BLUE}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "  ${BLUE}${BOLD}║          Ostwin — MCP Configuration              ║${NC}"
echo -e "  ${BLUE}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${DIM}Project:${NC} $TARGET_DIR"
echo ""

# ─── MCP configuration ────────────────────────────────────────────────────────
# MCP config lives globally at ~/.ostwin/.agents/mcp/ and is compiled into
# .opencode/opencode.json by `ostwin mcp compile`. No .agents/mcp folder is
# created in the project directory.

PYTHON="python3"
MCP_EXTENSION_SCRIPT="$SCRIPT_DIR/mcp/mcp-extension.sh"

# Ensure global MCP dir and config exist
GLOBAL_MCP_DIR="$HOME/.ostwin/.agents/mcp"
GLOBAL_MCP_CONFIG="$GLOBAL_MCP_DIR/config.json"
mkdir -p "$GLOBAL_MCP_DIR"
if [[ ! -f "$GLOBAL_MCP_CONFIG" ]]; then
  if [[ -f "$GLOBAL_MCP_DIR/mcp-builtin.json" ]]; then
    cp "$GLOBAL_MCP_DIR/mcp-builtin.json" "$GLOBAL_MCP_CONFIG"
  else
    echo '{"mcp":{}}' > "$GLOBAL_MCP_CONFIG"
  fi
  ok "Global MCP config created at $GLOBAL_MCP_CONFIG"
else
  ok "Global MCP config exists (preserved)"
fi

# Compile .opencode/opencode.json from global config
if [[ -f "$MCP_EXTENSION_SCRIPT" ]]; then
  step "Compiling project-level MCP config..."
  bash "$MCP_EXTENSION_SCRIPT" --project-dir "$TARGET_DIR" compile
fi

# ─── Update .gitignore ────────────────────────────────────────────────────────

GITIGNORE="$TARGET_DIR/.gitignore"
GITIGNORE_ENTRIES=(".opencode/opencode.json")
if [[ -f "$GITIGNORE" ]]; then
  for entry in "${GITIGNORE_ENTRIES[@]}"; do
    if ! grep -q "$entry" "$GITIGNORE"; then
      echo "" >> "$GITIGNORE"
      echo "# Ostwin generated" >> "$GITIGNORE"
      echo "$entry" >> "$GITIGNORE"
      ok "Added $entry to .gitignore"
    else
      ok "$entry already in .gitignore"
    fi
  done
else
  {
    echo "# Ostwin generated"
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
      echo "$entry"
    done
  } > "$GITIGNORE"
  ok "Created .gitignore with Ostwin entries"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

OPENCODE_CONFIG="$TARGET_DIR/.opencode/opencode.json"
echo ""
echo -e "  ${GREEN}${BOLD}✓ MCP configured at:${NC} $OPENCODE_CONFIG"
echo ""
echo -e "  ${BOLD}Manage extensions:${NC}"
echo "    ostwin mcp catalog              Show available packages"
echo "    ostwin mcp install <name>       Install an extension"
echo "    ostwin mcp list                 Show installed extensions"
echo "    ostwin mcp sync                 Rebuild config.json"
echo ""
