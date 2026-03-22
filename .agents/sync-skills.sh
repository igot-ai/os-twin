#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# sync-skills.sh — Scan OSTWIN_HOME for SKILL.md files and register them
#                  with the dashboard vector store.
#
# Usage:
#   sync-skills.sh                          # Scan ~/.ostwin for skills
#   sync-skills.sh --install-from /path     # Copy skills from a project dir
#                                           # into ~/.ostwin/skills/roles/...
#                                           # then sync
#
# Environment:
#   OSTWIN_HOME        Override install dir (default: ~/.ostwin)
#   DASHBOARD_PORT     Dashboard port (default: 9000)
#   OSTWIN_API_KEY     Dashboard authentication key
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
DASHBOARD_PORT="${DASHBOARD_PORT:-9000}"
DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"
OSTWIN_API_KEY="${OSTWIN_API_KEY:-}"
INSTALL_FROM=""

# ─── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "    ${GREEN}[OK]${NC} $1"; }
warn() { echo -e "    ${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "    ${RED}[FAIL]${NC} $1"; }
info() { echo -e "    ${DIM}$1${NC}"; }
step() { echo -e "  ${CYAN}→${NC} $1"; }

# ─── Load .env ────────────────────────────────────────────────────────────────

if [[ -f "$OSTWIN_HOME/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$OSTWIN_HOME/.env"
  set +a
  OSTWIN_API_KEY="${OSTWIN_API_KEY:-}"
fi

# ─── Argument Parsing ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-from)
      INSTALL_FROM="$2"
      shift 2
      ;;
    --port)
      DASHBOARD_PORT="$2"
      DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"
      shift 2
      ;;
    --home)
      OSTWIN_HOME="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: sync-skills.sh [--install-from DIR] [--port PORT] [--home DIR]"
      echo ""
      echo "  --install-from DIR   Copy skills from DIR into ~/.ostwin/skills/ first"
      echo "  --port PORT          Dashboard port (default: 9000)"
      echo "  --home DIR           Override OSTWIN_HOME (default: ~/.ostwin)"
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# ─── Build curl auth args ────────────────────────────────────────────────────

CURL_AUTH=()
if [[ -n "$OSTWIN_API_KEY" ]]; then
  CURL_AUTH=(-H "X-API-Key: ${OSTWIN_API_KEY}")
fi

# ─── Part 2: Install skills from a project directory ─────────────────────────

install_from_dir() {
  local source_dir="$1"
  local dest_base="$OSTWIN_HOME/skills"
  local copied=0

  step "Scanning $source_dir for SKILL.md files..."

  # Walk source for SKILL.md files
  while IFS= read -r skill_md; do
    local skill_dir
    skill_dir="$(dirname "$skill_md")"
    local skill_name
    skill_name="$(basename "$skill_dir")"

    # Determine role and category from path structure
    # Expected: */roles/{role}/{skill_name}/SKILL.md
    # or:       */global/{skill_name}/SKILL.md
    local rel_from_source
    rel_from_source="${skill_dir#"$source_dir"/}"

    local dest_dir=""
    if [[ "$rel_from_source" =~ roles/([^/]+)/([^/]+)$ ]]; then
      local role="${BASH_REMATCH[1]}"
      local name="${BASH_REMATCH[2]}"
      dest_dir="$dest_base/roles/$role/$name"
    elif [[ "$rel_from_source" =~ global/([^/]+)$ ]]; then
      local name="${BASH_REMATCH[1]}"
      dest_dir="$dest_base/global/$name"
    else
      # Fallback: try to infer role from YAML frontmatter tags
      local first_tag=""
      first_tag=$(grep -A5 '^tags:' "$skill_md" 2>/dev/null | head -2 | grep -oE '\- [a-zA-Z0-9_-]+' | head -1 | sed 's/^- //' || true)
      if [[ -z "$first_tag" ]]; then
        first_tag=$(grep '^tags:' "$skill_md" 2>/dev/null | head -1 | grep -oE '\[[^]]*\]' | tr -d '[]' | cut -d',' -f1 | tr -d ' ' || true)
      fi
      if [[ -n "$first_tag" ]]; then
        dest_dir="$dest_base/roles/$first_tag/$skill_name"
      else
        dest_dir="$dest_base/global/$skill_name"
      fi
    fi

    if [[ -z "$dest_dir" ]]; then
      warn "Could not determine destination for $skill_md — skipping"
      continue
    fi

    # Skip if source and destination are the same directory
    local resolved_src resolved_dst
    resolved_src="$(cd "$skill_dir" 2>/dev/null && pwd)"
    resolved_dst="$(mkdir -p "$dest_dir" && cd "$dest_dir" 2>/dev/null && pwd)"
    if [[ "$resolved_src" == "$resolved_dst" ]]; then
      info "  $skill_name (already in place)"
      ((copied++))
      continue
    fi

    # Copy the entire skill directory (overwrite)
    mkdir -p "$dest_dir"
    cp -r "$skill_dir"/* "$dest_dir/" 2>/dev/null || cp -r "$skill_dir"/. "$dest_dir/"
    info "  $skill_name → ${dest_dir#"$OSTWIN_HOME"/}"
    ((copied++))
  done < <(find "$source_dir" -name "SKILL.md" -type f 2>/dev/null)

  if [[ $copied -gt 0 ]]; then
    ok "$copied skill(s) copied to $dest_base"
  else
    warn "No SKILL.md files found in $source_dir"
  fi
}

# ─── Part 1: Scan OSTWIN_HOME and register via API ──────────────────────────

sync_home_skills() {
  step "Scanning $OSTWIN_HOME for SKILL.md files..."

  local total=0
  local installed=0
  local failed=0

  while IFS= read -r skill_md; do
    local skill_dir
    skill_dir="$(dirname "$skill_md")"
    local skill_name
    skill_name="$(basename "$skill_dir")"
    ((total++))

    # Install via API
    local json_payload="{\"path\": \"$skill_dir\"}"
    local result=""
    result=$(curl -sf -X POST "${CURL_AUTH[@]}" \
      -H "Content-Type: application/json" \
      -d "$json_payload" \
      "${DASHBOARD_URL}/api/skills/install" 2>&1) || true

    if echo "$result" | grep -q '"status"' 2>/dev/null; then
      ((installed++))
    else
      ((failed++))
      info "  ✗ $skill_name"
    fi
  done < <(find "$OSTWIN_HOME" -name "SKILL.md" -type f 2>/dev/null)

  if [[ $total -eq 0 ]]; then
    warn "No SKILL.md files found in $OSTWIN_HOME"
    return
  fi

  ok "$installed/$total skill(s) registered via API"
  if [[ $failed -gt 0 ]]; then
    warn "$failed skill(s) failed — dashboard may not be reachable"
  fi

  # Final sync to ensure vector store is consistent
  step "Finalizing vector store sync..."
  local sync_result=""
  sync_result=$(curl -sf -X POST "${CURL_AUTH[@]}" \
    "${DASHBOARD_URL}/api/skills/sync" 2>&1) || true

  if [[ -n "$sync_result" ]]; then
    local synced_count
    synced_count=$(echo "$sync_result" | grep -o '"synced_count":[0-9]*' | grep -o '[0-9]*' || echo "0")
    ok "Vector store synced ($synced_count updated)"
  else
    warn "Vector store sync returned empty — store may be unavailable"
  fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Skills Sync${NC}"
echo ""

# If --install-from was specified, copy skills first
if [[ -n "$INSTALL_FROM" ]]; then
  # Resolve to absolute path
  if [[ ! "$INSTALL_FROM" = /* ]]; then
    INSTALL_FROM="$(cd "$INSTALL_FROM" 2>/dev/null && pwd)"
  fi

  if [[ ! -d "$INSTALL_FROM" ]]; then
    fail "Source directory not found: $INSTALL_FROM"
    exit 1
  fi

  install_from_dir "$INSTALL_FROM"
  echo ""
fi

# Always sync home skills with the dashboard
sync_home_skills
echo ""
