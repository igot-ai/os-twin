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

# ─── Ensure .agents/mcp exists ────────────────────────────────────────────────

step "Scaffolding MCP directory..."

mkdir -p "$TARGET_AGENTS/mcp"

# Seed extensions.json if not present
if [[ ! -f "$TARGET_AGENTS/mcp/extensions.json" ]]; then
  echo '{"extensions":[]}' > "$TARGET_AGENTS/mcp/extensions.json"
fi

# Copy catalog from source if not present or outdated
if [[ -f "$SCRIPT_DIR/mcp/mcp-catalog.json" ]]; then
  cp "$SCRIPT_DIR/mcp/mcp-catalog.json" "$TARGET_AGENTS/mcp/mcp-catalog.json"
fi

# Copy builtin config from source
if [[ -f "$SCRIPT_DIR/mcp/mcp-builtin.json" ]]; then
  cp "$SCRIPT_DIR/mcp/mcp-builtin.json" "$TARGET_AGENTS/mcp/mcp-builtin.json"
fi

# Copy extension manager script
if [[ -f "$SCRIPT_DIR/mcp/mcp-extension.sh" ]]; then
  local_src="$(realpath "$SCRIPT_DIR/mcp/mcp-extension.sh" 2>/dev/null || echo "$SCRIPT_DIR/mcp/mcp-extension.sh")"
  local_dst="$(realpath "$TARGET_AGENTS/mcp/mcp-extension.sh" 2>/dev/null || echo "$TARGET_AGENTS/mcp/mcp-extension.sh")"
  if [[ "$local_src" != "$local_dst" ]]; then
    cp "$SCRIPT_DIR/mcp/mcp-extension.sh" "$TARGET_AGENTS/mcp/mcp-extension.sh"
  fi
  chmod +x "$TARGET_AGENTS/mcp/mcp-extension.sh"
fi

# Generate initial mcp-config.json from builtins (if not already present)
if [[ ! -f "$TARGET_AGENTS/mcp/mcp-config.json" ]]; then
  if [[ -f "$TARGET_AGENTS/mcp/mcp-builtin.json" ]]; then
    cp "$TARGET_AGENTS/mcp/mcp-builtin.json" "$TARGET_AGENTS/mcp/mcp-config.json"
  else
    echo '{"mcpServers":{}}' > "$TARGET_AGENTS/mcp/mcp-config.json"
  fi

  # Resolve ${AGENT_DIR} and ${PROJECT_DIR} → absolute paths
  AGENT_DIR_ABS=""
  if [[ -d "$HOME/.ostwin" ]]; then
    AGENT_DIR_ABS="$HOME/.ostwin"
  else
    AGENT_DIR_ABS="$SCRIPT_DIR"
  fi
  PROJECT_DIR_ABS="$(cd "$TARGET_DIR" 2>/dev/null && pwd || echo "$TARGET_DIR")"

  "$PYTHON" - <<PYEOF
with open('$TARGET_AGENTS/mcp/mcp-config.json') as _f:
    _raw = _f.read()
_raw = _raw.replace('\${AGENT_DIR}', '$AGENT_DIR_ABS')
_raw = _raw.replace('\${PROJECT_DIR}', '$PROJECT_DIR_ABS')
with open('$TARGET_AGENTS/mcp/mcp-config.json', 'w') as _f:
    _f.write(_raw)
PYEOF

  ok "MCP config created"
else
  ok "MCP config exists (preserved)"
fi

echo -e "    ${DIM}Config: $TARGET_AGENTS/mcp/mcp-config.json${NC}"

# ─── Interactive MCP install ──────────────────────────────────────────────────

PYTHON="python3"
CATALOG_FILE="$TARGET_AGENTS/mcp/mcp-catalog.json"
MCP_EXTENSION_SCRIPT="$TARGET_AGENTS/mcp/mcp-extension.sh"

if [[ -f "$CATALOG_FILE" ]] && ! $AUTO_YES; then
  echo ""
  echo -e "  ${BLUE}${BOLD}── Available MCP Extensions ──${NC}"
  echo ""

  # Read catalog packages into arrays
  PACKAGE_NAMES=()
  PACKAGE_DESCS=()
  while IFS='|' read -r pname pdesc; do
    PACKAGE_NAMES+=("$pname")
    PACKAGE_DESCS+=("$pdesc")
  done < <("$PYTHON" -c "
import json
with open('$CATALOG_FILE') as f:
    catalog = json.load(f)
for name, spec in catalog.get('packages', {}).items():
    desc = spec.get('description', '')
    print(f'{name}|{desc}')
" 2>/dev/null || true)

  if [[ ${#PACKAGE_NAMES[@]} -gt 0 ]]; then
    # Display packages
    for i in "${!PACKAGE_NAMES[@]}"; do
      local_num=$((i + 1))
      echo -e "    ${BOLD}[$local_num]${NC} ${PACKAGE_NAMES[$i]}"
      echo -e "        ${DIM}${PACKAGE_DESCS[$i]}${NC}"
    done
    echo ""

    if ask "Would you like to install any MCP extensions now?"; then
      echo ""
      echo -en "    ${YELLOW}?${NC} Enter numbers separated by spaces (e.g. ${BOLD}1 2${NC}), or ${BOLD}all${NC}: "
      read -r selection

      SELECTED=()
      if [[ "$selection" == "all" ]]; then
        SELECTED=("${PACKAGE_NAMES[@]}")
      else
        for num in $selection; do
          idx=$((num - 1))
          if [[ $idx -ge 0 && $idx -lt ${#PACKAGE_NAMES[@]} ]]; then
            SELECTED+=("${PACKAGE_NAMES[$idx]}")
          else
            warn "Invalid selection: $num — skipping"
          fi
        done
      fi

      echo ""
      if [[ ${#SELECTED[@]} -gt 0 ]]; then
        for pkg in "${SELECTED[@]}"; do
          step "Installing ${BOLD}$pkg${NC}..."
          if bash "$MCP_EXTENSION_SCRIPT" install "$pkg" --project-dir "$TARGET_DIR" 2>&1; then
            ok "$pkg installed"
          else
            warn "$pkg installation failed — you can retry later with: ostwin mcp install $pkg"
          fi
          echo ""
        done
      else
        info "No packages selected — you can install later with: ostwin mcp install <name>"
      fi
    else
      echo ""
      info "Skipped — install later with: ostwin mcp install <name>"
    fi
  fi
else
  if $AUTO_YES; then
    info "Non-interactive mode — skipping MCP extension install"
    info "Install later with: ostwin mcp install <name>"
  fi
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${GREEN}${BOLD}✓ MCP configured at:${NC} $TARGET_AGENTS/mcp/mcp-config.json"
echo ""
echo -e "  ${BOLD}Manage extensions:${NC}"
echo "    ostwin mcp catalog              Show available packages"
echo "    ostwin mcp install <name>       Install an extension"
echo "    ostwin mcp list                 Show installed extensions"
echo "    ostwin mcp sync                 Rebuild mcp-config.json"
echo ""
