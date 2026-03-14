#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# mcp-extension.sh — MCP Extension Manager for Ostwin
#
# Install, list, remove, and sync MCP server extensions.
# Extensions can be installed by name (from mcp-catalog.json) or by git URL.
#
# Usage:
#   mcp-extension.sh install <name|git-url> [--name NAME] [--branch BRANCH]
#   mcp-extension.sh list
#   mcp-extension.sh catalog
#   mcp-extension.sh remove <name>
#   mcp-extension.sh sync
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Resolve paths ───────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find INSTALL_DIR: prefer ~/.ostwin if it exists, otherwise use SCRIPT_DIR parent
if [[ -d "$HOME/.ostwin/mcp" ]]; then
  INSTALL_DIR="$HOME/.ostwin"
else
  INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

MCP_DIR="$INSTALL_DIR/mcp"
EXTENSIONS_DIR="$MCP_DIR/extensions"
CATALOG_FILE="$MCP_DIR/mcp-catalog.json"
EXTENSIONS_FILE="$MCP_DIR/extensions.json"
BUILTIN_FILE="$MCP_DIR/mcp-builtin.json"
CONFIG_FILE="$MCP_DIR/mcp-config.json"

# Also check script-local catalog (dev mode: running from repo)
if [[ ! -f "$CATALOG_FILE" ]] && [[ -f "$SCRIPT_DIR/mcp-catalog.json" ]]; then
  CATALOG_FILE="$SCRIPT_DIR/mcp-catalog.json"
fi
if [[ ! -f "$EXTENSIONS_FILE" ]] && [[ -f "$SCRIPT_DIR/extensions.json" ]]; then
  EXTENSIONS_FILE="$SCRIPT_DIR/extensions.json"
fi
if [[ ! -f "$BUILTIN_FILE" ]] && [[ -f "$SCRIPT_DIR/mcp-builtin.json" ]]; then
  BUILTIN_FILE="$SCRIPT_DIR/mcp-builtin.json"
fi

# Python: prefer venv, fallback to system
PYTHON="$INSTALL_DIR/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
info() { echo -e "  ${DIM}$1${NC}"; }
step() { echo -e "  ${CYAN}→${NC} $1"; }

# ─── Helpers ─────────────────────────────────────────────────────────────────

ensure_dirs() {
  mkdir -p "$EXTENSIONS_DIR"
  if [[ ! -f "$EXTENSIONS_FILE" ]]; then
    echo '{"extensions":[]}' > "$EXTENSIONS_FILE"
  fi
}

# Read a field from catalog for a package name
catalog_field() {
  local pkg="$1" field="$2"
  "$PYTHON" -c "
import json, sys
with open('$CATALOG_FILE') as f:
    catalog = json.load(f)
pkg = catalog.get('packages', {}).get('$pkg')
if not pkg:
    sys.exit(1)
val = pkg.get('$field', '')
if isinstance(val, dict):
    print(json.dumps(val))
elif isinstance(val, list):
    print(json.dumps(val))
else:
    print(val)
" 2>/dev/null
}

# Check if a package name exists in the catalog
is_in_catalog() {
  local name="$1"
  "$PYTHON" -c "
import json, sys
with open('$CATALOG_FILE') as f:
    catalog = json.load(f)
if '$name' in catalog.get('packages', {}):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null
}

# Check if already installed
is_installed() {
  local name="$1"
  "$PYTHON" -c "
import json, sys
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
for ext in data.get('extensions', []):
    if ext.get('name') == '$name':
        sys.exit(0)
sys.exit(1)
" 2>/dev/null
}

# ─── INSTALL ─────────────────────────────────────────────────────────────────

cmd_install() {
  local target="${1:-}"
  shift || true

  if [[ -z "$target" ]]; then
    fail "Usage: ostwin mcp install <name|git-url> [--name NAME] [--branch BRANCH]"
    exit 1
  fi

  # Parse optional args
  local opt_name="" opt_branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name)   opt_name="$2"; shift 2 ;;
      --branch) opt_branch="$2"; shift 2 ;;
      *)        warn "Unknown option: $1"; shift ;;
    esac
  done

  ensure_dirs

  local name="" repo="" branch="" build_type="" config_json=""

  # Determine if target is a catalog name or a git URL
  if [[ "$target" == http* ]] || [[ "$target" == git@* ]] || [[ "$target" == *.git ]]; then
    # ── Git URL mode ──
    repo="$target"
    if [[ -n "$opt_name" ]]; then
      name="$opt_name"
    else
      # Derive name from URL: https://github.com/org/nanobanana.git → nanobanana
      name=$(basename "$repo" .git)
    fi
    branch="${opt_branch:-main}"
    build_type="auto"
    config_json=""
    info "Installing from git URL: $repo"
  else
    # ── Catalog name mode ──
    name="$target"
    if ! is_in_catalog "$name"; then
      fail "Package '$name' not found in catalog."
      echo ""
      info "Available packages:"
      cmd_catalog
      echo ""
      info "Or install from a git URL:"
      info "  ostwin mcp install https://github.com/org/repo.git --name my-mcp"
      exit 1
    fi

    repo=$(catalog_field "$name" "repo")
    branch="${opt_branch:-$(catalog_field "$name" "branch")}"
    build_type=$(catalog_field "$name" "build_type")
    config_json=$(catalog_field "$name" "config")
    info "Installing from catalog: $name"
  fi

  # Check if already installed
  if is_installed "$name"; then
    warn "'$name' is already installed."
    info "To reinstall: ostwin mcp remove $name && ostwin mcp install $name"
    exit 0
  fi

  local ext_path="$EXTENSIONS_DIR/$name"

  # ── Clone ──
  step "Cloning $repo (branch: $branch)..."
  if ! git clone --depth 1 --branch "$branch" "$repo" "$ext_path" 2>/dev/null; then
    # Retry without --branch for default branch
    if ! git clone --depth 1 "$repo" "$ext_path" 2>/dev/null; then
      fail "Failed to clone $repo"
      exit 1
    fi
  fi
  ok "Cloned to $ext_path"

  # ── Auto-detect build type if not from catalog ──
  if [[ "$build_type" == "auto" ]]; then
    if [[ -f "$ext_path/package.json" ]]; then
      build_type="node"
    elif [[ -f "$ext_path/requirements.txt" ]]; then
      build_type="python"
    elif [[ -f "$ext_path/setup.py" ]] || [[ -f "$ext_path/pyproject.toml" ]]; then
      build_type="python"
    else
      build_type="none"
    fi
    info "Auto-detected build type: $build_type"
  fi

  # ── Build ──
  case "$build_type" in
    node)
      if ! command -v node &>/dev/null; then
        fail "Node.js is required but not installed."
        info "Install: brew install node"
        rm -rf "$ext_path"
        exit 1
      fi
      step "Building (npm install && npm run build)..."
      (
        cd "$ext_path"
        npm install --silent 2>/dev/null || npm install
        if grep -q '"build"' package.json 2>/dev/null; then
          npm run build 2>/dev/null || npm run build
        fi
      ) && ok "Build complete" || {
        fail "Build failed"
        rm -rf "$ext_path"
        exit 1
      }
      ;;
    python)
      step "Installing Python dependencies..."
      if [[ -f "$ext_path/requirements.txt" ]]; then
        "$PYTHON" -m pip install --quiet -r "$ext_path/requirements.txt" 2>/dev/null || {
          warn "pip install failed — trying with --user"
          "$PYTHON" -m pip install --user -r "$ext_path/requirements.txt"
        }
      fi
      ok "Python deps installed"
      ;;
    none)
      info "No build step required"
      ;;
    *)
      warn "Unknown build type: $build_type — skipping build"
      ;;
  esac

  # ── Resolve config: scan repo JSON files for mcpServers declaration ──
  if [[ -z "$config_json" ]]; then
    step "Scanning for mcpServers declaration in repo..."
    config_json=$("$PYTHON" -c "
import json, os, glob, sys

ext_path = '$ext_path'
name = '$name'

# Priority order for JSON files containing mcpServers:
#   1. gemini-extension.json  (Gemini CLI extension standard)
#   2. mcp-config.json        (generic MCP config)
#   3. Any other *.json in root directory
#   4. Any *.json in subdirectories (max depth 2)

candidates = []

# Priority 1: gemini-extension.json
gemini_ext = os.path.join(ext_path, 'gemini-extension.json')
if os.path.isfile(gemini_ext):
    candidates.insert(0, gemini_ext)

# Priority 2: mcp-config.json
mcp_cfg = os.path.join(ext_path, 'mcp-config.json')
if os.path.isfile(mcp_cfg):
    candidates.append(mcp_cfg)

# Priority 3-4: all other JSON files (root first, then subdirs)
for json_file in sorted(glob.glob(os.path.join(ext_path, '*.json'))):
    if json_file not in candidates:
        candidates.append(json_file)
for json_file in sorted(glob.glob(os.path.join(ext_path, '*', '*.json'))):
    if json_file not in candidates:
        candidates.append(json_file)

# Scan each candidate for mcpServers
found_config = None
found_source = None
for filepath in candidates:
    try:
        with open(filepath) as f:
            data = json.load(f)
        servers = data.get('mcpServers', {})
        if servers:
            # Extract the server config for this extension
            # If the extension name matches a key, use that; otherwise take first
            if name in servers:
                found_config = servers[name]
            else:
                first_key = list(servers.keys())[0]
                found_config = servers[first_key]
            found_source = os.path.basename(filepath)
            break
    except (json.JSONDecodeError, KeyError, TypeError):
        continue

if found_config:
    # Include metadata about where we found the config
    print(json.dumps(found_config))
    print('SOURCE:' + found_source, file=sys.stderr)
else:
    print('{}')
    print('SOURCE:none', file=sys.stderr)
" 2>/tmp/mcp_detect_source)

    local detect_source
    detect_source=$(grep '^SOURCE:' /tmp/mcp_detect_source 2>/dev/null | sed 's/^SOURCE://' || echo "none")
    rm -f /tmp/mcp_detect_source

    if [[ "$config_json" != "{}" ]] && [[ -n "$config_json" ]]; then
      ok "Found mcpServers in $detect_source"
    else
      warn "No mcpServers declaration found in any JSON file"
      info "You may need to configure manually in extensions.json"
      config_json='{}'
    fi
  fi

  # Resolve ${extensionPath} and ${AGENT_DIR} → actual absolute paths
  config_json=$(echo "$config_json" | sed "s|\${extensionPath}|$ext_path|g; s|\${AGENT_DIR}|$INSTALL_DIR|g")

  # ── Register in extensions.json ──
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  "$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)

entry = {
    'name': '$name',
    'repo': '$repo',
    'branch': '$branch',
    'build_type': '$build_type',
    'installed_at': '$now',
    'path': '$ext_path',
    'config': $config_json
}
data['extensions'].append(entry)

with open('$EXTENSIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
  ok "Registered in extensions.json"

  # ── Sync mcp-config.json ──
  cmd_sync_quiet
  ok "mcp-config.json updated"

  echo ""
  echo -e "  ${GREEN}${BOLD}✅ '$name' installed successfully!${NC}"
  echo ""
  info "Extension path: $ext_path"
  info "Run 'ostwin mcp list' to see all installed extensions."
}

# ─── LIST ────────────────────────────────────────────────────────────────────

cmd_list() {
  if [[ ! -f "$EXTENSIONS_FILE" ]]; then
    info "No extensions installed."
    return
  fi

  "$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)

exts = data.get('extensions', [])
if not exts:
    print('  No extensions installed.')
    print('  Run: ostwin mcp catalog   to see available packages.')
    print('  Run: ostwin mcp install <name>  to install one.')
else:
    print(f'  Installed MCP extensions ({len(exts)}):')
    print()
    for ext in exts:
        name = ext.get('name', '?')
        repo = ext.get('repo', '?')
        btype = ext.get('build_type', '?')
        date = ext.get('installed_at', '?')
        print(f'    \033[1m{name}\033[0m')
        print(f'      repo:       {repo}')
        print(f'      build_type: {btype}')
        print(f'      installed:  {date}')
        cmd = ext.get('config', {}).get('command', '?')
        print(f'      command:    {cmd}')
        print()
"
}

# ─── CATALOG ─────────────────────────────────────────────────────────────────

cmd_catalog() {
  if [[ ! -f "$CATALOG_FILE" ]]; then
    fail "Catalog file not found: $CATALOG_FILE"
    exit 1
  fi

  "$PYTHON" -c "
import json
with open('$CATALOG_FILE') as f:
    catalog = json.load(f)

with open('$EXTENSIONS_FILE') as f:
    installed = json.load(f)
installed_names = {e['name'] for e in installed.get('extensions', [])}

pkgs = catalog.get('packages', {})
ver = catalog.get('catalog_version', '?')
print(f'  MCP Extension Catalog v{ver}')
print(f'  {len(pkgs)} package(s) available:')
print()

for name, spec in pkgs.items():
    status = '\033[32m[installed]\033[0m' if name in installed_names else ''
    desc = spec.get('description', '')
    btype = spec.get('build_type', '?')
    print(f'    \033[1m{name}\033[0m  {status}')
    print(f'      {desc}')
    print(f'      build: {btype}  |  repo: {spec.get(\"repo\", \"?\")}')
    print()

print('  Install with: ostwin mcp install <name>')
"
}

# ─── REMOVE ──────────────────────────────────────────────────────────────────

cmd_remove() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    fail "Usage: ostwin mcp remove <name>"
    exit 1
  fi

  if ! is_installed "$name"; then
    fail "'$name' is not installed."
    exit 1
  fi

  # Get path before removing from registry
  local ext_path
  ext_path=$("$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
for ext in data.get('extensions', []):
    if ext.get('name') == '$name':
        print(ext.get('path', ''))
        break
")

  # Remove from extensions.json
  "$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
data['extensions'] = [e for e in data.get('extensions', []) if e.get('name') != '$name']
with open('$EXTENSIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
  ok "Removed from extensions.json"

  # Delete files
  if [[ -n "$ext_path" ]] && [[ -d "$ext_path" ]]; then
    rm -rf "$ext_path"
    ok "Deleted $ext_path"
  fi

  # Sync config
  cmd_sync_quiet
  ok "mcp-config.json updated"

  echo ""
  echo -e "  ${GREEN}✅ '$name' removed.${NC}"
}

# ─── SYNC ────────────────────────────────────────────────────────────────────

cmd_sync_quiet() {
  "$PYTHON" -c "
import json

# Load builtin servers
builtin = {}
try:
    with open('$BUILTIN_FILE') as f:
        builtin = json.load(f).get('mcpServers', {})
except FileNotFoundError:
    pass

# Load installed extensions
extensions = {}
try:
    with open('$EXTENSIONS_FILE') as f:
        data = json.load(f)
    for ext in data.get('extensions', []):
        name = ext.get('name')
        config = ext.get('config', {})
        if name and config:
            extensions[name] = config
except FileNotFoundError:
    pass

# Merge: builtin + extensions
merged = {'mcpServers': {**builtin, **extensions}}

with open('$CONFIG_FILE', 'w') as f:
    json.dump(merged, f, indent=2)
    f.write('\n')
"

  # Post-process: resolve ${AGENT_DIR} → real INSTALL_DIR path so server
  # paths in mcp-config.json are always absolute.
  "$PYTHON" - <<PYEOF
with open('$CONFIG_FILE') as _f:
    _raw = _f.read()
_raw = _raw.replace('\${AGENT_DIR}', '$INSTALL_DIR')
with open('$CONFIG_FILE', 'w') as _f:
    _f.write(_raw)
PYEOF
}

cmd_sync() {
  step "Syncing mcp-config.json (builtin + extensions)..."
  cmd_sync_quiet
  ok "mcp-config.json rebuilt"

  # Show summary
  "$PYTHON" -c "
import json
with open('$CONFIG_FILE') as f:
    data = json.load(f)
servers = data.get('mcpServers', {})
print(f'  {len(servers)} server(s) in mcp-config.json:')
for name in servers:
    cmd = servers[name].get('command', '?')
    print(f'    • {name} ({cmd})')
"
}

# ─── HELP ────────────────────────────────────────────────────────────────────

cmd_help() {
  cat <<HELP
ostwin mcp — MCP Extension Manager

Usage:
  ostwin mcp install <name>              Install from catalog by name
  ostwin mcp install <git-url> --name X  Install custom repo (not in catalog)
  ostwin mcp list                        Show installed extensions
  ostwin mcp catalog                     Show available packages from catalog
  ostwin mcp remove <name>              Uninstall an extension
  ostwin mcp sync                       Rebuild mcp-config.json from registry

Options (install):
  --name NAME      Override extension name (required for git URLs)
  --branch BRANCH  Git branch to clone (default: main)

Examples:
  ostwin mcp catalog
  ostwin mcp install nanobanana
  ostwin mcp install https://github.com/org/my-mcp.git --name my-mcp
  ostwin mcp list
  ostwin mcp remove nanobanana
HELP
}

# ─── MAIN ────────────────────────────────────────────────────────────────────

case "${1:-}" in
  install)  shift; cmd_install "$@" ;;
  list)     cmd_list ;;
  catalog)  cmd_catalog ;;
  remove)   shift; cmd_remove "$@" ;;
  sync)     cmd_sync ;;
  -h|--help|help|"")  cmd_help ;;
  *)
    fail "Unknown subcommand: $1"
    echo "  Run 'ostwin mcp --help' for usage."
    exit 1
    ;;
esac
