#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# clawhub-install.sh — Install skills from the ClawHub public registry
#
# Usage:
#   clawhub-install.sh install <slug>         Install a skill by slug
#   clawhub-install.sh search  <query>        Search the registry
#   clawhub-install.sh update  [--all|<slug>] Update installed skills
#   clawhub-install.sh remove  <slug>         Remove an installed skill
#
# Environment:
#   OSTWIN_HOME    Override install dir   (default: ~/.ostwin)
#   CLAWHUB_URL    Override registry URL  (default: https://clawhub.ai)
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
CLAWHUB_URL="${CLAWHUB_URL:-https://clawhub.ai}"
CLAWHUB_API="${CLAWHUB_URL}/api/v1"
SKILLS_DIR="$OSTWIN_HOME/skills/global"
LOCK_FILE="$OSTWIN_HOME/skills/.clawhub-lock.json"

PYTHON="${PYTHON:-python3}"

# ─── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${DIM}$1${NC}"; }
step() { echo -e "  ${CYAN}→${NC} $1"; }

# ─── Helpers ──────────────────────────────────────────────────────────────────

ensure_dirs() {
  mkdir -p "$SKILLS_DIR"
  mkdir -p "$(dirname "$LOCK_FILE")"
  if [[ ! -f "$LOCK_FILE" ]]; then
    echo '{"skills":{}}' > "$LOCK_FILE"
  fi
}

# Read a JSON field from the lockfile via python
lock_get() {
  local slug="$1"
  "$PYTHON" -c "
import json, sys
try:
    lock = json.load(open('$LOCK_FILE'))
    entry = lock.get('skills', {}).get('$slug')
    if entry:
        print(json.dumps(entry))
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

# Write/update a skill entry in the lockfile
lock_set() {
  local slug="$1"
  local version="$2"
  local source_url="$3"
  "$PYTHON" -c "
import json, datetime
lock_path = '$LOCK_FILE'
try:
    with open(lock_path) as f:
        lock = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    lock = {'skills': {}}

lock.setdefault('skills', {})['$slug'] = {
    'version': '$version',
    'source': '$source_url',
    'installed_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
}

with open(lock_path, 'w') as f:
    json.dump(lock, f, indent=2)
    f.write('\n')
" 2>/dev/null
}

# Remove a skill entry from the lockfile
lock_remove() {
  local slug="$1"
  "$PYTHON" -c "
import json
lock_path = '$LOCK_FILE'
try:
    with open(lock_path) as f:
        lock = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    lock = {'skills': {}}

lock.get('skills', {}).pop('$slug', None)

with open(lock_path, 'w') as f:
    json.dump(lock, f, indent=2)
    f.write('\n')
" 2>/dev/null
}

# Trigger dashboard sync if available
sync_dashboard() {
  local sync_script="$OSTWIN_HOME/sync-skills.sh"
  if [[ ! -x "$sync_script" ]]; then
    # Try project-local
    local agents_dir=""
    if [[ -d "$(pwd)/.agents" ]]; then
      agents_dir="$(pwd)/.agents"
    fi
    if [[ -n "$agents_dir" && -x "$agents_dir/sync-skills.sh" ]]; then
      sync_script="$agents_dir/sync-skills.sh"
    fi
  fi
  if [[ -x "$sync_script" ]]; then
    info "Syncing with dashboard..."
    OSTWIN_HOME="$OSTWIN_HOME" bash "$sync_script" 2>/dev/null || true
  fi
}

# ─── Commands ─────────────────────────────────────────────────────────────────

cmd_install() {
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    fail "Usage: ostwin skills install <slug>"
    echo "  Example: ostwin skills install steipete/web-search"
    exit 1
  fi

  ensure_dirs

  echo ""
  echo -e "  ${BOLD}ClawHub Install${NC}"
  echo ""

  # 1. Fetch skill metadata
  step "Fetching metadata for '$slug'..."
  local meta_response
  meta_response=$(curl -sf "${CLAWHUB_API}/skills/${slug}" 2>&1) || {
    fail "Skill '$slug' not found on ClawHub."
    info "Try: ostwin skills search <keyword>"
    exit 1
  }

  # Parse version and name
  local version name description
  version=$("$PYTHON" -c "
import json, sys
data = json.loads(sys.stdin.read())
skill = data if 'version' in data else data.get('skill', data)
v = skill.get('latestVersion', skill.get('version', 'unknown'))
if isinstance(v, dict):
    print(v.get('version', v.get('semver', 'unknown')))
else:
    print(v)
" <<< "$meta_response" 2>/dev/null || echo "unknown")

  name=$("$PYTHON" -c "
import json, sys
data = json.loads(sys.stdin.read())
skill = data if 'name' in data else data.get('skill', data)
print(skill.get('name', skill.get('slug', '$slug')))
" <<< "$meta_response" 2>/dev/null || echo "$slug")

  description=$("$PYTHON" -c "
import json, sys
data = json.loads(sys.stdin.read())
skill = data if 'description' in data else data.get('skill', data)
print(skill.get('description', '')[:80])
" <<< "$meta_response" 2>/dev/null || echo "")

  info "$name v$version"
  if [[ -n "$description" ]]; then
    info "$description"
  fi

  # Check if already installed at same version
  local existing
  existing=$(lock_get "$slug" 2>/dev/null || true)
  if [[ -n "$existing" ]]; then
    local existing_version
    existing_version=$("$PYTHON" -c "import json; print(json.loads('$existing').get('version',''))" 2>/dev/null || echo "")
    if [[ "$existing_version" == "$version" ]]; then
      ok "Already installed at v$version"
      exit 0
    fi
    warn "Upgrading from v$existing_version to v$version"
  fi

  # 2. Download the skill zip
  step "Downloading..."
  local tmp_dir
  tmp_dir=$(mktemp -d)
  local zip_file="$tmp_dir/skill.zip"

  # ClawHub download endpoint
  local download_url="${CLAWHUB_API}/download?slug=${slug}"
  if ! curl -sfL -o "$zip_file" "$download_url" 2>&1; then
    # Fallback: try version-specific download
    download_url="${CLAWHUB_API}/download?slug=${slug}&version=${version}"
    if ! curl -sfL -o "$zip_file" "$download_url" 2>&1; then
      fail "Failed to download skill '$slug'."
      rm -rf "$tmp_dir"
      exit 1
    fi
  fi

  # Verify we got something
  if [[ ! -s "$zip_file" ]]; then
    fail "Downloaded file is empty."
    rm -rf "$tmp_dir"
    exit 1
  fi

  # 3. Extract
  step "Extracting..."
  local extract_dir="$tmp_dir/extract"
  mkdir -p "$extract_dir"

  # Try unzip first, fallback to tar
  if file "$zip_file" | grep -qi "zip"; then
    unzip -qo "$zip_file" -d "$extract_dir" 2>/dev/null || {
      fail "Failed to extract zip file."
      rm -rf "$tmp_dir"
      exit 1
    }
  elif file "$zip_file" | grep -qi "gzip\|tar"; then
    tar -xzf "$zip_file" -C "$extract_dir" 2>/dev/null || tar -xf "$zip_file" -C "$extract_dir" 2>/dev/null || {
      fail "Failed to extract archive."
      rm -rf "$tmp_dir"
      exit 1
    }
  else
    # Maybe it's a raw SKILL.md text or a zip without proper magic bytes
    unzip -qo "$zip_file" -d "$extract_dir" 2>/dev/null || {
      fail "Unrecognized archive format."
      rm -rf "$tmp_dir"
      exit 1
    }
  fi

  # Find the SKILL.md — it might be nested in a subdirectory
  local skill_md
  skill_md=$(find "$extract_dir" -name "SKILL.md" -type f 2>/dev/null | head -1)
  if [[ -z "$skill_md" ]]; then
    fail "No SKILL.md found in the downloaded package."
    rm -rf "$tmp_dir"
    exit 1
  fi

  local skill_source_dir
  skill_source_dir=$(dirname "$skill_md")

  # 4. Install to global skills directory
  # Use the skill name (last part of slug) as the directory name
  local skill_dir_name
  skill_dir_name=$(basename "$slug")
  local dest_dir="$SKILLS_DIR/$skill_dir_name"

  if [[ -d "$dest_dir" ]]; then
    rm -rf "$dest_dir"
  fi
  mkdir -p "$dest_dir"
  cp -r "$skill_source_dir"/* "$dest_dir/" 2>/dev/null || cp -r "$skill_source_dir"/. "$dest_dir/"

  # 5. Write origin.json for provenance
  "$PYTHON" -c "
import json, datetime
origin = {
    'source': 'clawhub',
    'slug': '$slug',
    'version': '$version',
    'registry_url': '${CLAWHUB_URL}/skills/$slug',
    'installed_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
}
with open('$dest_dir/origin.json', 'w') as f:
    json.dump(origin, f, indent=2)
    f.write('\n')
" 2>/dev/null

  # 6. Update lockfile
  lock_set "$slug" "$version" "${CLAWHUB_URL}/skills/${slug}"

  # 7. Cleanup
  rm -rf "$tmp_dir"

  ok "Installed '$name' v$version → $dest_dir"
  echo ""

  # 8. Sync with dashboard
  sync_dashboard
}

cmd_search() {
  local query="${1:-}"
  if [[ -z "$query" ]]; then
    fail "Usage: ostwin skills search <query>"
    exit 1
  fi

  echo ""
  echo -e "  ${BOLD}ClawHub Search${NC}: $query"
  echo ""

  local encoded_query
  encoded_query=$(printf '%s' "$query" | "$PYTHON" -c "import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read()))" 2>/dev/null)

  local response
  response=$(curl -sf "${CLAWHUB_API}/search?q=${encoded_query}" 2>&1) || {
    fail "Search failed. ClawHub may be unreachable."
    exit 1
  }

  "$PYTHON" -c "
import json, sys

data = json.loads(sys.stdin.read())
results = data if isinstance(data, list) else data.get('results', data.get('skills', []))

if not results:
    print('  No results found.')
    sys.exit(0)

for r in results[:20]:
    slug = r.get('slug', r.get('name', '?'))
    desc = r.get('description', '')[:60]
    version = r.get('version', r.get('latestVersion', ''))
    if isinstance(version, dict):
        version = version.get('version', version.get('semver', ''))
    ver_str = f' v{version}' if version else ''
    print(f'  {slug:35s}{ver_str:10s}  {desc}')
" <<< "$response" 2>/dev/null || {
    fail "Failed to parse search results."
    exit 1
  }
  echo ""
}

cmd_list() {
  ensure_dirs

  echo ""
  echo -e "  ${BOLD}Installed ClawHub Skills${NC}"
  echo ""

  "$PYTHON" -c "
import json, sys, os

lock_path = '$LOCK_FILE'
try:
    with open(lock_path) as f:
        lock = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print('  No skills installed from ClawHub.')
    sys.exit(0)

skills = lock.get('skills', {})
if not skills:
    print('  No skills installed from ClawHub.')
    sys.exit(0)

for slug, info in sorted(skills.items()):
    version = info.get('version', '?')
    installed = info.get('installed_at', '?')
    dir_name = slug.split('/')[-1] if '/' in slug else slug
    exists = '✓' if os.path.isdir('$SKILLS_DIR/' + dir_name) else '✗'
    print(f'  {exists} {slug:35s}  v{version:10s}  {installed}')
" 2>/dev/null || {
    echo "  No skills installed from ClawHub."
  }
  echo ""
}

cmd_update() {
  local target="${1:-}"
  local update_all=false

  if [[ "$target" == "--all" ]]; then
    update_all=true
  fi

  ensure_dirs

  echo ""
  echo -e "  ${BOLD}ClawHub Update${NC}"
  echo ""

  local slugs_to_update=()

  if [[ "$update_all" == true ]]; then
    # Get all installed slugs
    while IFS= read -r slug; do
      [[ -n "$slug" ]] && slugs_to_update+=("$slug")
    done < <("$PYTHON" -c "
import json
try:
    lock = json.load(open('$LOCK_FILE'))
    for slug in lock.get('skills', {}):
        print(slug)
except Exception:
    pass
" 2>/dev/null)
  elif [[ -n "$target" ]]; then
    slugs_to_update+=("$target")
  else
    fail "Usage: ostwin skills update <slug> | --all"
    exit 1
  fi

  if [[ ${#slugs_to_update[@]} -eq 0 ]]; then
    info "No ClawHub skills installed."
    exit 0
  fi

  local updated=0
  for slug in "${slugs_to_update[@]}"; do
    step "Checking $slug..."

    # Fetch latest version
    local meta
    meta=$(curl -sf "${CLAWHUB_API}/skills/${slug}" 2>&1) || {
      warn "Could not fetch metadata for '$slug'. Skipping."
      continue
    }

    local remote_version
    remote_version=$("$PYTHON" -c "
import json, sys
data = json.loads(sys.stdin.read())
skill = data if 'version' in data else data.get('skill', data)
v = skill.get('latestVersion', skill.get('version', 'unknown'))
if isinstance(v, dict):
    print(v.get('version', v.get('semver', 'unknown')))
else:
    print(v)
" <<< "$meta" 2>/dev/null || echo "unknown")

    local local_version
    local_version=$("$PYTHON" -c "
import json
lock = json.load(open('$LOCK_FILE'))
print(lock.get('skills', {}).get('$slug', {}).get('version', 'unknown'))
" 2>/dev/null || echo "unknown")

    if [[ "$remote_version" == "$local_version" ]]; then
      info "$slug is up to date (v$local_version)"
      continue
    fi

    info "$slug: v$local_version → v$remote_version"
    cmd_install "$slug"
    ((updated++))
  done

  if [[ $updated -eq 0 ]]; then
    ok "All skills are up to date."
  else
    ok "Updated $updated skill(s)."
  fi
  echo ""
}

cmd_remove() {
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    fail "Usage: ostwin skills remove <slug>"
    exit 1
  fi

  ensure_dirs

  echo ""
  echo -e "  ${BOLD}ClawHub Remove${NC}"
  echo ""

  local skill_dir_name
  skill_dir_name=$(basename "$slug")
  local dest_dir="$SKILLS_DIR/$skill_dir_name"

  if [[ -d "$dest_dir" ]]; then
    rm -rf "$dest_dir"
    ok "Removed directory: $dest_dir"
  else
    warn "Skill directory not found: $dest_dir"
  fi

  lock_remove "$slug"
  ok "Removed '$slug' from lockfile."
  echo ""

  sync_dashboard
}

# ─── Show help ────────────────────────────────────────────────────────────────

show_help() {
  cat <<HELP
ClawHub Skill Installer — Install skills from the ClawHub public registry

Usage:
  clawhub-install.sh <command> [args]

Commands:
  install <slug>           Install a skill by its ClawHub slug (e.g. steipete/web-search)
  search  <query>          Search the ClawHub registry
  update  [--all|<slug>]   Update installed skills to latest versions
  remove  <slug>           Remove an installed skill
  list                     Show installed ClawHub skills

Environment:
  OSTWIN_HOME    Override install dir   (default: ~/.ostwin)
  CLAWHUB_URL    Override registry URL  (default: https://clawhub.ai)
HELP
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

ACTION="${1:-}"
shift 2>/dev/null || true

case "$ACTION" in
  install)  cmd_install "$@" ;;
  search)   cmd_search "$@" ;;
  update)   cmd_update "$@" ;;
  remove)   cmd_remove "$@" ;;
  list)     cmd_list ;;
  -h|--help|help)
    show_help
    ;;
  "")
    show_help
    exit 1
    ;;
  *)
    fail "Unknown command: $ACTION"
    show_help
    exit 1
    ;;
esac
