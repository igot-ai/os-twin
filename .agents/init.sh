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
    return 0  # Auto-approve in --yes mode
  fi
  echo -en "    ${YELLOW}?${NC} $prompt ${DIM}[Y/n]${NC} "
  read -r answer
  case "${answer:-y}" in
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

# ─── Ensure .agents/mcp exists ────────────────────────────────────────────────

step "Scaffolding MCP directory..."

mkdir -p "$TARGET_AGENTS/mcp"

# Seed extensions.json if not present
if [[ ! -f "$TARGET_AGENTS/mcp/extensions.json" ]]; then
  echo '{"extensions":[]}' > "$TARGET_AGENTS/mcp/extensions.json"
fi

# Copy catalog from source if not present or outdated
if [[ -f "$SCRIPT_DIR/mcp/mcp-catalog.json" ]]; then
  cp "$SCRIPT_DIR/mcp/mcp-catalog.json" "$TARGET_AGENTS/mcp/mcp-catalog.json" 2>/dev/null || true
fi

# Copy builtin config from source
if [[ -f "$SCRIPT_DIR/mcp/mcp-builtin.json" ]]; then
  cp "$SCRIPT_DIR/mcp/mcp-builtin.json" "$TARGET_AGENTS/mcp/mcp-builtin.json" 2>/dev/null || true
fi

# Note: mcp-config.json is the deploy template — it's read by the compile step
# from the source repo, but we don't copy it into the project (only config.json
# is the canonical compiled output). Avoid leaving unresolved {env:VAR} files.

# Copy extension manager script
if [[ -f "$SCRIPT_DIR/mcp/mcp-extension.sh" ]]; then
  local_src="$(realpath "$SCRIPT_DIR/mcp/mcp-extension.sh" 2>/dev/null || echo "$SCRIPT_DIR/mcp/mcp-extension.sh")"
  local_dst="$(realpath "$TARGET_AGENTS/mcp/mcp-extension.sh" 2>/dev/null || echo "$TARGET_AGENTS/mcp/mcp-extension.sh")"
  if [[ "$local_src" != "$local_dst" ]]; then
    cp "$SCRIPT_DIR/mcp/mcp-extension.sh" "$TARGET_AGENTS/mcp/mcp-extension.sh"
  fi
  chmod +x "$TARGET_AGENTS/mcp/mcp-extension.sh"
fi

# Copy vault.py and config_resolver.py (required by mcp-extension.sh)
for _py_file in vault.py config_resolver.py; do
  if [[ -f "$SCRIPT_DIR/mcp/$_py_file" ]]; then
    cp "$SCRIPT_DIR/mcp/$_py_file" "$TARGET_AGENTS/mcp/$_py_file" 2>/dev/null || true
  fi
done

PROJECT_MCP_CONFIG="$TARGET_AGENTS/mcp/config.json"
LEGACY_PROJECT_MCP_CONFIG="$TARGET_AGENTS/mcp/mcp-config.json"

if [[ ! -f "$PROJECT_MCP_CONFIG" ]]; then
  # Priority: mcp-config.json (deployed format with {env:OSTWIN_PYTHON}/{env:HOME})
  #         > legacy mcp-config.json
  #         > mcp-builtin.json (dev format with {env:AGENT_DIR})
  if [[ -f "$SCRIPT_DIR/mcp/mcp-config.json" ]]; then
    cp "$SCRIPT_DIR/mcp/mcp-config.json" "$PROJECT_MCP_CONFIG"
  elif [[ -f "$LEGACY_PROJECT_MCP_CONFIG" ]]; then
    cp "$LEGACY_PROJECT_MCP_CONFIG" "$PROJECT_MCP_CONFIG"
  elif [[ -f "$TARGET_AGENTS/mcp/mcp-builtin.json" ]]; then
    cp "$TARGET_AGENTS/mcp/mcp-builtin.json" "$PROJECT_MCP_CONFIG"
  else
    echo '{"mcp":{}}' > "$PROJECT_MCP_CONFIG"
  fi
  ok "MCP config seeded"
else
  ok "MCP config exists (will recompile)"
fi

echo -e "    ${DIM}Config: $PROJECT_MCP_CONFIG${NC}"

# ─── Interactive MCP install ──────────────────────────────────────────────────
# Note: MCP config also lives globally at ~/.ostwin/.agents/mcp/ and is compiled
# into .opencode/opencode.json by `ostwin mcp compile`.

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
