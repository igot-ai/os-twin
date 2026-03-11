#!/usr/bin/env bash
# Ostwin — Plan Management
#
# Create, list, and start execution plans using AI-assisted analysis.
#
# Usage:
#   plan.sh create               Interactive plan creation (AI-assisted)
#   plan.sh start [plan-file]    Start a plan (or create + start)
#   plan.sh list                 List available plans
#
# Options:
#   --working-dir PATH   Override project working directory
#   --model MODEL        Override AI model for plan generation
#   --no-ai              Skip AI analysis, use manual template

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
PLANS_DIR="$AGENTS_DIR/plans"
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"

# Source logging (optional)
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

# Read engineer config
ENGINEER_CLI=$(python3 -c "import json; print(json.load(open('$CONFIG'))['engineer']['cli'])" 2>/dev/null || echo "deepagents")
DEFAULT_MODEL=$(python3 -c "import json; print(json.load(open('$CONFIG'))['engineer']['default_model'])" 2>/dev/null || echo "gemini-2.5-pro")

# Module-level state (set by plan_create, read by plan_start)
LAST_PLAN_FILE=""

# ─── Help ────────────────────────────────────────────────────────────────────

show_plan_help() {
  cat << 'HELP'

  ╔══════════════════════════════════════╗
  ║       Ostwin — Plan Management       ║
  ╚══════════════════════════════════════╝

  Usage:
    ostwin plan create               AI-assisted plan creation
    ostwin plan start [plan-file]    Start a plan (or create + start)
    ostwin plan list                 List available plans

  Options (for create):
    --working-dir PATH   Project directory (default: current dir)
    --model MODEL        AI model (default: from config)
    --no-ai              Use manual template, skip AI analysis

  Examples:
    ostwin plan create
    ostwin plan create --working-dir /path/to/project
    ostwin plan create --no-ai
    ostwin plan start .agents/plans/my-feature.md
    ostwin plan start                # Interactive: create then run
    ostwin plan list

HELP
}

# ─── plan list ───────────────────────────────────────────────────────────────

plan_list() {
  echo ""
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║         Available Plans               ║"
  echo "  ╚══════════════════════════════════════╝"
  echo ""

  local found=0

  for plan_file in "$PLANS_DIR"/*.md; do
    [[ -f "$plan_file" ]] || continue
    local bname
    bname=$(basename "$plan_file")
    # Skip the template
    [[ "$bname" == "PLAN.template.md" ]] && continue

    found=$((found + 1))

    python3 -c "
import re, os, datetime
path = '$plan_file'
bname = '$bname'
with open(path) as f:
    content = f.read()
title_m = re.search(r'^# Plan:\s*(.+)', content, re.MULTILINE)
title = title_m.group(1).strip() if title_m else '(untitled)'
epics = len(re.findall(r'^## Epic:', content, re.MULTILINE))
tasks = len(re.findall(r'^## Task:', content, re.MULTILINE))
items = epics or tasks
label = 'epic(s)' if epics else 'task(s)'
mtime = os.path.getmtime(path)
date = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
# Truncate long titles
if len(title) > 28:
    title = title[:25] + '...'
print(f'  {bname:<38} {title:<30} {items} {label}  {date}')
" 2>/dev/null || echo "  $bname  (parse error)"
  done

  if [[ "$found" -eq 0 ]]; then
    echo "  No plans found in $PLANS_DIR/"
    echo ""
    echo "  Create one with: ostwin plan create"
  fi
  echo ""
}

# ─── plan create ─────────────────────────────────────────────────────────────

plan_create() {
  local WORKING_DIR=""
  local MODEL="$DEFAULT_MODEL"
  local NO_AI=false

  # Parse options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --working-dir) WORKING_DIR="$2"; shift 2 ;;
      --model)       MODEL="$2"; shift 2 ;;
      --no-ai)       NO_AI=true; shift ;;
      *)             shift ;;
    esac
  done

  echo ""
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║       Ostwin — Plan Creator           ║"
  echo "  ╚══════════════════════════════════════╝"
  echo ""

  # Ensure plans directory exists
  mkdir -p "$PLANS_DIR"

  # ── Interactive prompts (if tty) ──
  if [[ -t 0 ]]; then
    if [[ -z "$WORKING_DIR" ]]; then
      local default_dir
      default_dir=$(pwd)
      printf "  Project directory [%s]: " "$default_dir"
      read -r WORKING_DIR
      WORKING_DIR="${WORKING_DIR:-$default_dir}"
    fi

    local GOAL_DESC=""
    echo ""
    echo "  Describe your feature or goal:"
    printf "  > "
    read -r GOAL_DESC

    while [[ -z "$GOAL_DESC" ]]; do
      echo "  (description cannot be empty)"
      printf "  > "
      read -r GOAL_DESC
    done
  else
    # Non-interactive: require --working-dir
    if [[ -z "$WORKING_DIR" ]]; then
      echo "[ERROR] --working-dir required in non-interactive mode" >&2
      exit 1
    fi
    GOAL_DESC="Analyze the project and create a development plan"
  fi

  # Resolve to absolute path
  if [[ -d "$WORKING_DIR" ]]; then
    WORKING_DIR=$(cd "$WORKING_DIR" && pwd)
  else
    echo "[ERROR] Directory not found: $WORKING_DIR" >&2
    exit 1
  fi

  # ── Generate slug for filename ──
  local SLUG
  SLUG=$(echo "$GOAL_DESC" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-' | sed 's/^-//;s/-$//' | cut -c1-50)
  [[ -z "$SLUG" ]] && SLUG="plan"
  local PLAN_FILE="$PLANS_DIR/${SLUG}.md"

  # Handle collision
  if [[ -f "$PLAN_FILE" ]]; then
    local SUFFIX
    SUFFIX=$(date +%s | tail -c 6)
    PLAN_FILE="$PLANS_DIR/${SLUG}-${SUFFIX}.md"
  fi

  # ── Check for AI availability ──
  if [[ "$NO_AI" == "true" ]]; then
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    return 0
  fi

  if ! command -v "$ENGINEER_CLI" &>/dev/null; then
    echo ""
    echo "  [WARN] $ENGINEER_CLI not found. Using manual template."
    echo "    Install with: pip install deepagents-cli"
    echo ""
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    return 0
  fi

  # ── AI-assisted plan generation ──
  echo ""
  echo "  Analyzing project with $ENGINEER_CLI..."
  echo "  Model: $MODEL"
  echo "  Directory: $WORKING_DIR"
  echo ""

  local PLAN_PROMPT
  PLAN_PROMPT="You are a software architect planning work for an engineering team.

Analyze the project at: $WORKING_DIR

Goal: $GOAL_DESC

Instructions:
1. Examine the project structure, key files, and existing patterns
2. Break the goal into 2-6 cohesive EPICS (high-level features)
3. Each epic should represent a complete deliverable that an engineer can plan and implement
4. Do NOT break epics into atomic sub-tasks — the engineer will decompose them
5. Output ONLY valid markdown in this exact format — no explanation before or after:

# Plan: [Short descriptive title for the goal]

## Config
working_dir: $WORKING_DIR

## Epic: EPIC-001 — [Feature Title]
[High-level description of the feature to deliver — describe the goal, not the steps.
The engineer will create their own sub-task breakdown.]

Acceptance criteria:
- [Specific, testable criterion for the whole feature]
- [Another criterion]

## Epic: EPIC-002 — [Feature Title]
[Description]

Acceptance criteria:
- [Criterion]

(continue for all epics)

Rules:
- Epic IDs must be sequential: EPIC-001, EPIC-002, etc.
- Each epic is a cohesive feature, NOT an atomic task
- Acceptance criteria must be concrete and testable
- Use the em-dash character — between epic ID and title
- Do NOT wrap output in code fences
- Do NOT add any text before '# Plan:' or after the last epic"

  local PLAN_OUTPUT=""
  local AI_EXIT=0

  PLAN_OUTPUT=$(cd "$WORKING_DIR" && $ENGINEER_CLI -n "$PLAN_PROMPT" \
      --model "$MODEL" \
      --shell-allow-list "ls,find,cat,head,tree,wc,file" \
      --auto-approve \
      -q 2>/dev/null) || AI_EXIT=$?

  if [[ $AI_EXIT -ne 0 ]] || [[ -z "$PLAN_OUTPUT" ]]; then
    echo "  [WARN] AI analysis failed (exit $AI_EXIT). Using manual template."
    echo ""
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    return 0
  fi

  # ── Validate AI output (accept both Epic and Task formats) ──
  local HAS_HEADER=0
  local HAS_ITEMS=0
  HAS_HEADER=$(echo "$PLAN_OUTPUT" | grep -c "^# Plan:" || echo "0")
  HAS_ITEMS=$(echo "$PLAN_OUTPUT" | grep -c "^## \(Epic\|Task\):" || echo "0")

  if [[ "$HAS_HEADER" -eq 0 ]] || [[ "$HAS_ITEMS" -eq 0 ]]; then
    echo "  [WARN] AI output did not match expected plan format."
    echo "    Missing: $([ "$HAS_HEADER" -eq 0 ] && echo '# Plan: header ')$([ "$HAS_ITEMS" -eq 0 ] && echo '## Epic:/Task: sections')"
    echo "    Falling back to manual template."
    echo ""
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    return 0
  fi

  # ── Save the plan ──
  echo "$PLAN_OUTPUT" > "$PLAN_FILE"
  LAST_PLAN_FILE="$PLAN_FILE"

  # ── Display summary ──
  echo "  ✓ Plan generated: $PLAN_FILE"
  echo ""
  echo "  Items:"
  echo "$PLAN_OUTPUT" | grep "^## \(Epic\|Task\):" | while IFS= read -r line; do
    local item_info
    item_info=$(echo "$line" | sed 's/^## \(Epic\|Task\): //')
    echo "    [$( echo "$item_info" | sed 's/ —.*//' )] $(echo "$item_info" | sed 's/^[^ ]* — //')"
  done
  echo ""
  echo "  Next: ostwin plan start $PLAN_FILE"
  echo ""

  log INFO "Plan created: $PLAN_FILE ($HAS_ITEMS items)" 2>/dev/null || true
}

# ── Template fallback ──

_create_from_template() {
  local working_dir="$1"
  local plan_file="$2"
  local template="$PLANS_DIR/PLAN.template.md"

  if [[ -f "$template" ]]; then
    sed "s|working_dir: /path/to/your/project|working_dir: $working_dir|" \
      "$template" > "$plan_file"
  else
    # Inline minimal template
    cat > "$plan_file" << TMPL
# Plan: [Your Feature Title]

## Config
working_dir: $working_dir

## Epic: EPIC-001 — [First Feature Title]
[Describe the feature to deliver — the engineer will plan the sub-tasks]

Acceptance criteria:
- [Specific criterion]

## Epic: EPIC-002 — [Second Feature Title]
[Describe the feature to deliver]

Acceptance criteria:
- [Specific criterion]
TMPL
  fi

  LAST_PLAN_FILE="$plan_file"

  echo "  ✓ Template plan saved to: $plan_file"
  echo ""
  echo "  Edit this file to define your tasks, then run:"
  echo "    ostwin plan start $plan_file"
  echo ""
}

# ─── plan start ──────────────────────────────────────────────────────────────

plan_start() {
  local plan_file="${1:-}"

  if [[ -n "$plan_file" ]]; then
    # Direct start: resolve path and delegate to run.sh
    if [[ ! -f "$plan_file" ]]; then
      # Try relative to plans dir
      if [[ -f "$PLANS_DIR/$plan_file" ]]; then
        plan_file="$PLANS_DIR/$plan_file"
      else
        echo "[ERROR] Plan file not found: $plan_file" >&2
        echo "  Available plans: ostwin plan list" >&2
        exit 1
      fi
    fi
    # Pass remaining args (e.g. --dry-run) to run.sh
    shift 2>/dev/null || true
    exec "$AGENTS_DIR/run.sh" "$plan_file" "$@"
  else
    # Interactive mode: create then optionally start
    plan_create

    if [[ -n "$LAST_PLAN_FILE" ]] && [[ -f "$LAST_PLAN_FILE" ]]; then
      if [[ -t 0 ]]; then
        printf "  Start execution now? [Y/n]: "
        local START_NOW=""
        read -r START_NOW
        case "${START_NOW:-Y}" in
          [Nn]*)
            echo "  Plan saved. Run later with:"
            echo "    ostwin plan start $LAST_PLAN_FILE"
            ;;
          *)
            echo ""
            exec "$AGENTS_DIR/run.sh" "$LAST_PLAN_FILE"
            ;;
        esac
      else
        echo "  Non-interactive mode: plan saved. Run with:"
        echo "    ostwin plan start $LAST_PLAN_FILE"
      fi
    fi
  fi
}

# ─── Dispatch ────────────────────────────────────────────────────────────────

SUBCMD="${1:-}"
shift 2>/dev/null || true

case "$SUBCMD" in
  create)   plan_create "$@" ;;
  start)    plan_start "$@" ;;
  list)     plan_list ;;
  -h|--help|help|"")
    show_plan_help
    ;;
  *)
    echo "[ERROR] Unknown plan subcommand: $SUBCMD" >&2
    echo "  Run 'ostwin plan --help' for usage." >&2
    exit 1
    ;;
esac
