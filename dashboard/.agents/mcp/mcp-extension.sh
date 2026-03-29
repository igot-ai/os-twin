#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# mcp-extension.sh — MCP Extension Manager for Ostwin
#
# Install, list, remove, and sync MCP server extensions.
# Extensions can be installed by name (from mcp-catalog.json) or by git URL.
#
# MCP config is per-project only: $PROJECT/.agents/mcp/mcp-config.json
# Catalog + builtins come from global ~/.ostwin/mcp/
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

# Catalog + builtins always come from global install
CATALOG_FILE="$INSTALL_DIR/mcp/mcp-catalog.json"
BUILTIN_FILE="$INSTALL_DIR/mcp/mcp-builtin.json"

# Dev mode fallbacks
[[ ! -f "$CATALOG_FILE" ]] && [[ -f "$SCRIPT_DIR/mcp-catalog.json" ]] && CATALOG_FILE="$SCRIPT_DIR/mcp-catalog.json"
[[ ! -f "$BUILTIN_FILE" ]] && [[ -f "$SCRIPT_DIR/mcp-builtin.json" ]] && BUILTIN_FILE="$SCRIPT_DIR/mcp-builtin.json"

# Project-local paths — set after --project-dir is parsed (see MAIN)
MCP_DIR=""
EXTENSIONS_DIR=""
EXTENSIONS_FILE=""
CONFIG_FILE=""
PROJECT_DIR=""

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

# Resolve project dir → set all project-local paths
apply_project_dir() {
  PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"
  MCP_DIR="$PROJECT_DIR/.agents/mcp"
  EXTENSIONS_DIR="$MCP_DIR/extensions"
  EXTENSIONS_FILE="$MCP_DIR/extensions.json"
  CONFIG_FILE="$MCP_DIR/mcp-config.json"
}

ensure_dirs() {
  mkdir -p "$EXTENSIONS_DIR"
  if [[ ! -f "$EXTENSIONS_FILE" ]]; then
    echo '{"extensions":[]}' > "$EXTENSIONS_FILE"
  fi
}

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

is_installed() {
  local name="$1"
  [[ -f "$EXTENSIONS_FILE" ]] || return 1
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

  local opt_name="" opt_branch="" opt_env=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name)        opt_name="$2"; shift 2 ;;
      --branch)      opt_branch="$2"; shift 2 ;;
      --env)         opt_env="$2"; shift 2 ;;
      --project-dir) shift 2 ;;  # already handled globally
      *)             warn "Unknown option: $1"; shift ;;
    esac
  done

  ensure_dirs

  local name="" repo="" branch="" build_type="" config_json=""

  if [[ "$target" == http* ]] || [[ "$target" == git@* ]] || [[ "$target" == *.git ]]; then
    repo="$target"
    name="${opt_name:-$(basename "$repo" .git)}"
    branch="${opt_branch:-main}"
    build_type="auto"
    config_json=""
    info "Installing from git URL: $repo"
  else
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

  if is_installed "$name"; then
    warn "'$name' is already installed."
    info "To reinstall: ostwin mcp remove $name && ostwin mcp install $name"
    exit 0
  fi

  local ext_path="$EXTENSIONS_DIR/$name"

  # ── Clone (skip for npx-based extensions) ──
  if [[ "$build_type" != "npx" ]]; then
    step "Cloning $repo (branch: $branch)..."
    if ! git clone --depth 1 --branch "$branch" "$repo" "$ext_path" 2>/dev/null; then
      if ! git clone --depth 1 "$repo" "$ext_path" 2>/dev/null; then
        fail "Failed to clone $repo"
        exit 1
      fi
    fi
    ok "Cloned to $ext_path"
  fi

  # ── Auto-detect build type ──
  if [[ "$build_type" == "auto" ]]; then
    if [[ -f "$ext_path/package.json" ]]; then
      build_type="node"
    elif [[ -f "$ext_path/requirements.txt" ]] || [[ -f "$ext_path/setup.py" ]] || [[ -f "$ext_path/pyproject.toml" ]]; then
      build_type="python"
    else
      build_type="none"
    fi
    info "Auto-detected build type: $build_type"
  fi

  # ── Build ──
  case "$build_type" in
    npx)
      [[ -d "$ext_path" ]] && rm -rf "$ext_path"
      info "npx-based extension — no build required (fetched on demand)"
      ;;
    node)
      if ! command -v node &>/dev/null; then
        fail "Node.js is required but not installed."
        rm -rf "$ext_path"
        exit 1
      fi
      step "Building (npm install && npm run build)..."
      (
        cd "$ext_path"
        npm install --silent 2>/dev/null || npm install
        grep -q '"build"' package.json 2>/dev/null && { npm run build 2>/dev/null || npm run build; }
      ) && ok "Build complete" || { fail "Build failed"; rm -rf "$ext_path"; exit 1; }
      ;;
    python)
      step "Installing Python dependencies..."
      [[ -f "$ext_path/requirements.txt" ]] && {
        "$PYTHON" -m pip install --quiet -r "$ext_path/requirements.txt" 2>/dev/null || \
        "$PYTHON" -m pip install --user -r "$ext_path/requirements.txt"
      }
      ok "Python deps installed"
      ;;
    none) info "No build step required" ;;
    *)    warn "Unknown build type: $build_type — skipping build" ;;
  esac

  # ── Resolve config from repo JSON if not from catalog ──
  if [[ -z "$config_json" ]]; then
    step "Scanning for mcpServers declaration in repo..."
    config_json=$("$PYTHON" -c "
import json, os, glob, sys
ext_path = '$ext_path'
name = '$name'
candidates = []
for f in ['gemini-extension.json', 'mcp-config.json']:
    p = os.path.join(ext_path, f)
    if os.path.isfile(p): candidates.append(p)
for p in sorted(glob.glob(os.path.join(ext_path, '*.json'))):
    if p not in candidates: candidates.append(p)
for p in sorted(glob.glob(os.path.join(ext_path, '*', '*.json'))):
    if p not in candidates: candidates.append(p)
for filepath in candidates:
    try:
        with open(filepath) as f:
            data = json.load(f)
        servers = data.get('mcpServers', {})
        if servers:
            cfg = servers.get(name, list(servers.values())[0])
            print(json.dumps(cfg))
            sys.exit(0)
    except: continue
print('{}')
" 2>/dev/null)

    if [[ "$config_json" != "{}" ]] && [[ -n "$config_json" ]]; then
      ok "Found mcpServers declaration"
    else
      warn "No mcpServers declaration found"
      config_json='{}'
    fi
  fi

  # Resolve placeholders → absolute paths
  local abs_ext_path abs_project_dir
  abs_ext_path="$(cd "$ext_path" 2>/dev/null && pwd || echo "$ext_path")"
  abs_project_dir="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"
  config_json=$(echo "$config_json" | sed "s|\${extensionPath}|$abs_ext_path|g; s|\${AGENT_DIR}|$INSTALL_DIR|g; s|\${PROJECT_DIR}|$abs_project_dir|g")

  # ── Merge --env file if provided ──
  if [[ -n "$opt_env" ]] && [[ -f "$opt_env" ]]; then
    step "Merging environment variables from $opt_env..."
    config_json=$(echo "$config_json" | "$PYTHON" -c "
import json, sys
config = json.load(sys.stdin) if True else {}
env_dict = config.get('env', {})
with open('$opt_env') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, v = line.split('=', 1)
        env_dict[k.strip()] = v.strip().strip('\"').strip(\"'\")
if env_dict: config['env'] = env_dict
print(json.dumps(config))
" 2>/dev/null || echo "$config_json")
    ok "Environment variables merged"
  fi

  # ── Register in extensions.json ──
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  "$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
data['extensions'].append({
    'name': '$name', 'repo': '$repo', 'branch': '$branch',
    'build_type': '$build_type', 'installed_at': '$now',
    'path': '$abs_ext_path', 'config': $config_json
})
with open('$EXTENSIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
  ok "Registered in extensions.json"

  cmd_sync_quiet
  ok "mcp-config.json updated"

  echo ""
  echo -e "  ${GREEN}${BOLD}✅ '$name' installed successfully!${NC}"
  echo ""
  info "Extension path: $abs_ext_path"
  info "Run 'ostwin mcp list' to see all installed extensions."
}

# ─── LIST ────────────────────────────────────────────────────────────────────

cmd_list() {
  "$PYTHON" -c "
import json, os, sys

# Show builtin servers
builtin_file = '$BUILTIN_FILE'
if os.path.isfile(builtin_file):
    with open(builtin_file) as f:
        builtins = json.load(f).get('mcpServers', {})
    if builtins:
        print(f'  Builtin servers ({len(builtins)}):')
        print()
        for name, cfg in builtins.items():
            cmd = cfg.get('command', '?')
            print(f'    \033[1m{name}\033[0m  \033[2m(builtin)\033[0m')
            print(f'      command: {cmd}')
            print()

# Show installed extensions
ext_file = '$EXTENSIONS_FILE'
if not os.path.isfile(ext_file):
    print('  No extensions installed.')
    sys.exit(0)

with open(ext_file) as f:
    exts = json.load(f).get('extensions', [])

if not exts:
    print('  No extensions installed.')
    print('  Run: ostwin mcp install <name>')
else:
    print(f'  Installed extensions ({len(exts)}):')
    print()
    for ext in exts:
        print(f'    \033[1m{ext.get(\"name\",\"?\")}\033[0m')
        print(f'      repo:       {ext.get(\"repo\",\"?\")}')
        print(f'      build_type: {ext.get(\"build_type\",\"?\")}')
        print(f'      installed:  {ext.get(\"installed_at\",\"?\")}')
        print(f'      command:    {ext.get(\"config\",{}).get(\"command\",\"?\")}')
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
import json, os
with open('$CATALOG_FILE') as f:
    catalog = json.load(f)
installed_names = set()
if os.path.isfile('$EXTENSIONS_FILE'):
    with open('$EXTENSIONS_FILE') as f:
        installed_names = {e['name'] for e in json.load(f).get('extensions', [])}
pkgs = catalog.get('packages', {})
print(f'  MCP Extension Catalog v{catalog.get(\"catalog_version\", \"?\")}')
print(f'  {len(pkgs)} package(s) available:')
print()
for name, spec in pkgs.items():
    status = '\033[32m[installed]\033[0m' if name in installed_names else ''
    print(f'    \033[1m{name}\033[0m  {status}')
    print(f'      {spec.get(\"description\",\"\")}')
    print(f'      build: {spec.get(\"build_type\",\"?\")}  |  repo: {spec.get(\"repo\",\"?\")}')
    print()
print('  Install with: ostwin mcp install <name>')
"
}

# ─── REMOVE ──────────────────────────────────────────────────────────────────

cmd_remove() {
  local name="${1:-}"
  [[ -z "$name" ]] && { fail "Usage: ostwin mcp remove <name>"; exit 1; }
  is_installed "$name" || { fail "'$name' is not installed."; exit 1; }

  local ext_path
  ext_path=$("$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
for ext in data.get('extensions', []):
    if ext.get('name') == '$name': print(ext.get('path', '')); break
")

  "$PYTHON" -c "
import json
with open('$EXTENSIONS_FILE') as f:
    data = json.load(f)
data['extensions'] = [e for e in data['extensions'] if e.get('name') != '$name']
with open('$EXTENSIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
  ok "Removed from extensions.json"

  [[ -n "$ext_path" ]] && [[ -d "$ext_path" ]] && { rm -rf "$ext_path"; ok "Deleted $ext_path"; }

  cmd_sync_quiet
  ok "mcp-config.json updated"
  echo ""
  echo -e "  ${GREEN}✅ '$name' removed.${NC}"
}

# ─── SYNC ────────────────────────────────────────────────────────────────────

cmd_sync_quiet() {
  "$PYTHON" -c "
import json
builtin = {}
try:
    with open('$BUILTIN_FILE') as f:
        builtin = json.load(f).get('mcpServers', {})
except FileNotFoundError: pass
extensions = {}
try:
    with open('$EXTENSIONS_FILE') as f:
        data = json.load(f)
    for ext in data.get('extensions', []):
        name = ext.get('name')
        config = ext.get('config', {})
        if name and config: extensions[name] = config
except FileNotFoundError: pass
merged = {'mcpServers': {**builtin, **extensions}}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(merged, f, indent=2)
    f.write('\n')
"
  # Resolve ${AGENT_DIR} and ${PROJECT_DIR} → absolute paths
  local abs_project_dir
  abs_project_dir="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"
  "$PYTHON" - <<PYEOF
with open('$CONFIG_FILE') as _f:
    _raw = _f.read()
_raw = _raw.replace('\${AGENT_DIR}', '$INSTALL_DIR')
_raw = _raw.replace('\${PROJECT_DIR}', '$abs_project_dir')
with open('$CONFIG_FILE', 'w') as _f:
    _f.write(_raw)
PYEOF
}

cmd_sync() {
  step "Syncing mcp-config.json (builtin + extensions)..."
  cmd_sync_quiet
  ok "mcp-config.json rebuilt"
  "$PYTHON" -c "
import json
with open('$CONFIG_FILE') as f:
    servers = json.load(f).get('mcpServers', {})
print(f'  {len(servers)} server(s) in mcp-config.json:')
for name in servers:
    print(f'    • {name} ({servers[name].get(\"command\",\"?\")})')
"
}

# ─── INIT PROJECT ────────────────────────────────────────────────────────────

cmd_init_project() {
  local project_dir="${1:-}"
  [[ -z "$project_dir" ]] && { fail "Usage: mcp-extension.sh init-project <project-dir>"; exit 1; }

  local project_mcp="$project_dir/.agents/mcp"
  mkdir -p "$project_mcp"

  [[ ! -f "$project_mcp/extensions.json" ]] && echo '{"extensions":[]}' > "$project_mcp/extensions.json"
  [[ -f "$CATALOG_FILE" ]] && cp "$CATALOG_FILE" "$project_mcp/mcp-catalog.json"
  [[ -f "$BUILTIN_FILE" ]] && cp "$BUILTIN_FILE" "$project_mcp/mcp-builtin.json"

  # Copy extension manager script (skip if same file)
  local self_script dest_script
  self_script="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  dest_script="$project_mcp/mcp-extension.sh"
  [[ "$(realpath "$self_script" 2>/dev/null)" != "$(realpath "$dest_script" 2>/dev/null)" ]] && cp "$self_script" "$dest_script"
  chmod +x "$dest_script"

  if [[ ! -f "$project_mcp/mcp-config.json" ]]; then
    [[ -f "$BUILTIN_FILE" ]] && cp "$BUILTIN_FILE" "$project_mcp/mcp-config.json" || echo '{"mcpServers":{}}' > "$project_mcp/mcp-config.json"
  fi

  ok "Project MCP scaffolded at $project_mcp"
}

# ─── HELP ────────────────────────────────────────────────────────────────────

cmd_help() {
  cat <<HELP
ostwin mcp — MCP Extension Manager (per-project)

Usage:
  ostwin mcp install <name>              Install from catalog by name
  ostwin mcp install <git-url> --name X  Install from git URL
  ostwin mcp list                        Show installed extensions
  ostwin mcp catalog                     Show available packages
  ostwin mcp remove <name>              Uninstall an extension
  ostwin mcp sync                       Rebuild mcp-config.json
  ostwin mcp init-project <dir>         Scaffold per-project MCP directory

Options:
  --name NAME        Override extension name
  --branch BRANCH    Git branch to clone (default: main)
  --env PATH         .env file to inject into MCP config
  --project-dir DIR  Target project (auto-detected from cwd)

Examples:
  ostwin mcp catalog
  ostwin mcp install chrome-devtools
  ostwin mcp install nanobanana
  ostwin mcp install https://github.com/org/my-mcp.git --name my-mcp
  ostwin mcp list
  ostwin mcp remove nanobanana
HELP
}

# ─── MAIN ────────────────────────────────────────────────────────────────────

# Pre-parse --project-dir from anywhere in args (global flag)
_ARGS=()
_SKIP_NEXT=false
for _a in "$@"; do
  if $_SKIP_NEXT; then
    PROJECT_DIR="$_a"
    _SKIP_NEXT=false
    continue
  fi
  if [[ "$_a" == "--project-dir" ]]; then
    _SKIP_NEXT=true
    continue
  fi
  _ARGS+=("$_a")
done
set -- "${_ARGS[@]+"${_ARGS[@]}"}"

# Auto-detect project dir from cwd
if [[ -z "$PROJECT_DIR" ]] && [[ -d "$(pwd)/.agents/mcp" ]]; then
  PROJECT_DIR="$(pwd)"
fi

# Apply project dir → set all project-local paths
if [[ -n "$PROJECT_DIR" ]]; then
  apply_project_dir
fi

case "${1:-}" in
  install)
    [[ -z "$MCP_DIR" ]] && { fail "No project MCP directory found. Run 'ostwin init' first."; exit 1; }
    shift; cmd_install "$@" ;;
  list)
    [[ -z "$MCP_DIR" ]] && { fail "No project MCP directory found. Run 'ostwin init' first."; exit 1; }
    cmd_list ;;
  catalog)       cmd_catalog ;;
  remove)
    [[ -z "$MCP_DIR" ]] && { fail "No project MCP directory found. Run 'ostwin init' first."; exit 1; }
    shift; cmd_remove "$@" ;;
  sync)
    [[ -z "$MCP_DIR" ]] && { fail "No project MCP directory found. Run 'ostwin init' first."; exit 1; }
    cmd_sync ;;
  init-project)  shift; cmd_init_project "$@" ;;
  -h|--help|help|"")  cmd_help ;;
  *)
    fail "Unknown subcommand: $1"
    echo "  Run 'ostwin mcp --help' for usage."
    exit 1
    ;;
esac
