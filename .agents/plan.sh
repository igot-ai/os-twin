#!/usr/bin/env bash
# Ostwin — Plan Management
#
# AI-assisted plan creation with interactive consultant Q&A,
# professional TUI display, feedback loop, and auto-start.
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

# Read config
ENGINEER_CLI=$(python3 -c "import json; print(json.load(open('$CONFIG'))['engineer']['cli'])" 2>/dev/null || echo "deepagents")
IDEATION_MODEL="gemini-3.1-pro-preview"

# Module-level state (set by plan_create, read by plan_start)
LAST_PLAN_FILE=""

# ─── TUI Helpers ──────────────────────────────────────────────────────────────

_tui_header() {
  local title="$1"
  local width=52
  local pad=$(( (width - ${#title} - 2) / 2 ))
  local lpad="" rpad=""
  for ((i=0; i<pad; i++)); do lpad="${lpad} "; done
  rpad="$lpad"
  # Adjust if odd length
  if (( (width - ${#title} - 2) % 2 == 1 )); then
    rpad="${rpad} "
  fi
  echo ""
  echo "  ╔$(printf '═%.0s' $(seq 1 $width))╗"
  echo "  ║${lpad} ${title} ${rpad}║"
  echo "  ╚$(printf '═%.0s' $(seq 1 $width))╝"
  echo ""
}

_tui_section() {
  local title="$1"
  echo ""
  echo "  ┌─── $title ───"
  echo "  │"
}

_tui_end_section() {
  echo "  │"
  echo "  └───────────────────────────────────────────"
}

_tui_line() {
  echo "  │  $1"
}

_tui_prompt() {
  printf "  │  \033[36m❯\033[0m "
}

_tui_success() {
  echo "  \033[32m✓\033[0m $1"
}

_tui_dim() {
  echo "  \033[2m$1\033[0m"
}

# ─── Per-project port ────────────────────────────────────────────────────────

_project_port() {
  local dir="$1"
  # Deterministic port from project path hash (range 8100-8999)
  local hash
  hash=$(echo -n "$dir" | cksum | awk '{print $1}')
  echo $(( (hash % 900) + 8100 ))
}

# ─── Help ─────────────────────────────────────────────────────────────────────

show_plan_help() {
  cat << 'HELP'

  ╔════════════════════════════════════════════════════╗
  ║            Ostwin — Plan Management                ║
  ╚════════════════════════════════════════════════════╝

  Usage:
    ostwin plan create               AI-assisted plan creation
    ostwin plan start [plan-file]    Start a plan (or create + start)
    ostwin plan list                 List available plans

  Options (for create):
    --working-dir PATH   Project directory (default: current dir)
    --model MODEL        AI model (default: gemini-3.1-pro-preview)
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

# ─── plan list ────────────────────────────────────────────────────────────────

plan_list() {
  _tui_header "Available Plans"

  local found=0

  for plan_file in "$PLANS_DIR"/*.md; do
    [[ -f "$plan_file" ]] || continue
    local bname
    bname=$(basename "$plan_file")
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

# ─── plan create ──────────────────────────────────────────────────────────────

plan_create() {
  local WORKING_DIR=""
  local MODEL="$IDEATION_MODEL"
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

  _tui_header "Ostwin Plan Creator"

  mkdir -p "$PLANS_DIR"

  # ── Non-interactive mode ──
  if [[ ! -t 0 ]]; then
    if [[ -z "$WORKING_DIR" ]]; then
      echo "[ERROR] --working-dir required in non-interactive mode" >&2
      exit 1
    fi
    WORKING_DIR=$(cd "$WORKING_DIR" && pwd)
    local SLUG="plan-$(date +%s | tail -c 6)"
    local PLAN_FILE="$PLANS_DIR/${SLUG}.md"
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    return 0
  fi

  # ══════════════════════════════════════════════════════════════════════════
  # PHASE 1: Discovery — Consultant Q&A
  # ══════════════════════════════════════════════════════════════════════════

  _tui_section "Project Discovery"
  _tui_line "I'll ask a few questions to understand your project"
  _tui_line "and craft the right development plan."
  _tui_end_section
  echo ""

  # Q1: Project directory
  if [[ -z "$WORKING_DIR" ]]; then
    local default_dir
    default_dir=$(pwd)
    printf "  \033[1mProject directory\033[0m [%s]: " "$default_dir"
    read -r WORKING_DIR
    WORKING_DIR="${WORKING_DIR:-$default_dir}"
  fi

  if [[ ! -d "$WORKING_DIR" ]]; then
    echo "[ERROR] Directory not found: $WORKING_DIR" >&2
    exit 1
  fi
  WORKING_DIR=$(cd "$WORKING_DIR" && pwd)
  echo ""

  # Q2: Project name
  local PROJECT_NAME=""
  local dir_name
  dir_name=$(basename "$WORKING_DIR")
  printf "  \033[1mProject name\033[0m [%s]: " "$dir_name"
  read -r PROJECT_NAME
  PROJECT_NAME="${PROJECT_NAME:-$dir_name}"
  echo ""

  # Q3: What are you building?
  local GOAL_DESC=""
  echo "  \033[1mWhat are you building or trying to achieve?\033[0m"
  echo "  \033[2m(Describe the feature, product, or goal in a few sentences)\033[0m"
  _tui_prompt
  read -r GOAL_DESC
  while [[ -z "$GOAL_DESC" ]]; do
    echo "  \033[31m(cannot be empty)\033[0m"
    _tui_prompt
    read -r GOAL_DESC
  done
  echo ""

  # Q4: Target users / audience
  local TARGET_USERS=""
  echo "  \033[1mWho is the target user or audience?\033[0m"
  echo "  \033[2m(e.g., developers, students, internal team, end consumers)\033[0m"
  _tui_prompt
  read -r TARGET_USERS
  TARGET_USERS="${TARGET_USERS:-general users}"
  echo ""

  # Q5: Tech stack / constraints
  local TECH_STACK=""
  echo "  \033[1mAny tech stack preferences or constraints?\033[0m"
  echo "  \033[2m(e.g., Python/FastAPI, React, Unity, or press Enter to auto-detect)\033[0m"
  _tui_prompt
  read -r TECH_STACK
  TECH_STACK="${TECH_STACK:-auto-detect from project}"
  echo ""

  # Q6: Priority / timeline
  local PRIORITY=""
  echo "  \033[1mWhat matters most for this iteration?\033[0m"
  echo "  \033[2m(1) Speed — ship MVP fast\033[0m"
  echo "  \033[2m(2) Quality — production-ready with tests\033[0m"
  echo "  \033[2m(3) Learning — explore and prototype\033[0m"
  printf "  \033[36m❯\033[0m [1/2/3]: "
  read -r PRIORITY_CHOICE
  case "${PRIORITY_CHOICE:-1}" in
    1) PRIORITY="Speed — ship MVP fast, defer non-essentials" ;;
    2) PRIORITY="Quality — production-ready code with full test coverage" ;;
    3) PRIORITY="Learning — explore approaches, prototype freely" ;;
    *) PRIORITY="Balanced approach" ;;
  esac
  echo ""

  # ── Generate slug for filename ──
  local SLUG
  SLUG=$(echo "$GOAL_DESC" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-' | sed 's/^-//;s/-$//' | cut -c1-50)
  [[ -z "$SLUG" ]] && SLUG="plan"
  local PLAN_FILE="$PLANS_DIR/${SLUG}.md"
  if [[ -f "$PLAN_FILE" ]]; then
    PLAN_FILE="$PLANS_DIR/${SLUG}-$(date +%s | tail -c 6).md"
  fi

  # ── Check for AI availability ──
  if [[ "$NO_AI" == "true" ]]; then
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    _offer_start "$PLAN_FILE" "$WORKING_DIR"
    return 0
  fi

  if ! command -v "$ENGINEER_CLI" &>/dev/null; then
    echo ""
    echo "  [WARN] $ENGINEER_CLI not found. Using manual template."
    echo "    Install with: pip install deepagents-cli"
    echo ""
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    _offer_start "$PLAN_FILE" "$WORKING_DIR"
    return 0
  fi

  # ══════════════════════════════════════════════════════════════════════════
  # PHASE 2: AI Analysis — Generate Plan
  # ══════════════════════════════════════════════════════════════════════════

  _tui_section "Analyzing Project"
  _tui_line "Model:     $MODEL"
  _tui_line "Directory: $WORKING_DIR"
  _tui_line "Thinking..."
  _tui_end_section

  local PLAN_PROMPT
  PLAN_PROMPT="You are a senior business consultant and software architect.

A client has come to you with the following brief:

PROJECT: $PROJECT_NAME
DIRECTORY: $WORKING_DIR
GOAL: $GOAL_DESC
TARGET USERS: $TARGET_USERS
TECH STACK: $TECH_STACK
PRIORITY: $PRIORITY

Instructions:
1. Examine the project directory structure, key files, and existing patterns
2. Based on the client brief, create a strategic development plan
3. Break the goal into 2-6 cohesive EPICS (high-level features/deliverables)
4. Each epic should represent a complete deliverable that an engineer can plan and implement
5. Do NOT break epics into atomic sub-tasks — the engineer will decompose them
6. Consider the priority and target users when scoping each epic
7. Output ONLY valid markdown in this exact format — no explanation before or after:

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
    echo ""
    echo "  [WARN] AI analysis failed (exit $AI_EXIT). Using manual template."
    echo ""
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    _offer_start "$PLAN_FILE" "$WORKING_DIR"
    return 0
  fi

  # ── Validate ──
  local HAS_HEADER HAS_ITEMS
  HAS_HEADER=$(echo "$PLAN_OUTPUT" | grep -c "^# Plan:" || echo "0")
  HAS_ITEMS=$(echo "$PLAN_OUTPUT" | grep -c "^## \(Epic\|Task\):" || echo "0")

  if [[ "$HAS_HEADER" -eq 0 ]] || [[ "$HAS_ITEMS" -eq 0 ]]; then
    echo "  [WARN] AI output did not match expected plan format. Using template."
    _create_from_template "$WORKING_DIR" "$PLAN_FILE"
    _offer_start "$PLAN_FILE" "$WORKING_DIR"
    return 0
  fi

  # ── Normalize Task → Epic if AI ignored instructions ──
  PLAN_OUTPUT=$(echo "$PLAN_OUTPUT" | python3 -c "
import sys, re
content = sys.stdin.read()
content = re.sub(r'^## Task:\s*TASK-(\d+)', r'## Epic: EPIC-\1', content, flags=re.MULTILINE)
content = re.sub(r'TASK-(\d+)', r'EPIC-\1', content)
print(content, end='')
")

  # ══════════════════════════════════════════════════════════════════════════
  # PHASE 3: Present Plan — Professional TUI Display
  # ══════════════════════════════════════════════════════════════════════════

  _display_plan "$PLAN_OUTPUT"

  # ══════════════════════════════════════════════════════════════════════════
  # PHASE 4: Feedback Loop
  # ══════════════════════════════════════════════════════════════════════════

  while true; do
    echo ""
    echo "  \033[1mWhat would you like to do?\033[0m"
    echo "  \033[2m(a) Accept and save this plan\033[0m"
    echo "  \033[2m(f) Give feedback — refine the plan\033[0m"
    echo "  \033[2m(r) Regenerate from scratch\033[0m"
    echo "  \033[2m(q) Quit without saving\033[0m"
    printf "  \033[36m❯\033[0m [a/f/r/q]: "
    read -r FEEDBACK_CHOICE

    case "${FEEDBACK_CHOICE:-a}" in
      [Aa]*)
        # Accept
        break
        ;;
      [Ff]*)
        # Feedback — refine
        echo ""
        echo "  \033[1mWhat should change?\033[0m"
        echo "  \033[2m(e.g., 'merge epic 2 and 3', 'add a testing epic', 'too many epics')\033[0m"
        _tui_prompt
        local FEEDBACK=""
        read -r FEEDBACK
        if [[ -n "$FEEDBACK" ]]; then
          echo ""
          _tui_section "Refining Plan"
          _tui_line "Applying your feedback..."
          _tui_end_section

          local REFINE_PROMPT="You previously generated this development plan:

$PLAN_OUTPUT

The client gave this feedback:
$FEEDBACK

Revise the plan according to the feedback. Output ONLY the updated plan in the exact same markdown format.
Do NOT add any explanation before or after. Keep the same ## Config section.
Rules: Epic IDs sequential, em-dash between ID and title, no code fences."

          local REFINED=""
          REFINED=$(cd "$WORKING_DIR" && $ENGINEER_CLI -n "$REFINE_PROMPT" \
              --model "$MODEL" \
              --auto-approve \
              -q 2>/dev/null) || true

          if [[ -n "$REFINED" ]] && echo "$REFINED" | grep -q "^# Plan:"; then
            REFINED=$(echo "$REFINED" | python3 -c "
import sys, re
content = sys.stdin.read()
content = re.sub(r'^## Task:\s*TASK-(\d+)', r'## Epic: EPIC-\1', content, flags=re.MULTILINE)
content = re.sub(r'TASK-(\d+)', r'EPIC-\1', content)
print(content, end='')
")
            PLAN_OUTPUT="$REFINED"
            _display_plan "$PLAN_OUTPUT"
          else
            echo "  [WARN] Refinement failed. Keeping previous version."
          fi
        fi
        ;;
      [Rr]*)
        # Regenerate
        echo ""
        _tui_section "Regenerating"
        _tui_line "Starting fresh analysis..."
        _tui_end_section

        PLAN_OUTPUT=$(cd "$WORKING_DIR" && $ENGINEER_CLI -n "$PLAN_PROMPT" \
            --model "$MODEL" \
            --shell-allow-list "ls,find,cat,head,tree,wc,file" \
            --auto-approve \
            -q 2>/dev/null) || true

        if [[ -n "$PLAN_OUTPUT" ]] && echo "$PLAN_OUTPUT" | grep -q "^# Plan:"; then
          PLAN_OUTPUT=$(echo "$PLAN_OUTPUT" | python3 -c "
import sys, re
content = sys.stdin.read()
content = re.sub(r'^## Task:\s*TASK-(\d+)', r'## Epic: EPIC-\1', content, flags=re.MULTILINE)
content = re.sub(r'TASK-(\d+)', r'EPIC-\1', content)
print(content, end='')
")
          _display_plan "$PLAN_OUTPUT"
        else
          echo "  [WARN] Regeneration failed. Keeping previous version."
        fi
        ;;
      [Qq]*)
        echo ""
        echo "  Plan discarded."
        return 0
        ;;
      *)
        echo "  \033[31mInvalid choice. Use a/f/r/q.\033[0m"
        ;;
    esac
  done

  # ── Save the accepted plan ──
  echo "$PLAN_OUTPUT" > "$PLAN_FILE"
  LAST_PLAN_FILE="$PLAN_FILE"

  local EPIC_COUNT
  EPIC_COUNT=$(echo "$PLAN_OUTPUT" | grep -c "^## Epic:" || echo "0")

  echo ""
  printf "  \033[32m✓\033[0m Plan saved: %s\n" "$PLAN_FILE"
  printf "  \033[32m✓\033[0m %s epic(s) defined\n" "$EPIC_COUNT"
  echo ""

  log INFO "Plan created: $PLAN_FILE ($EPIC_COUNT epics)" 2>/dev/null || true

  # ── Offer to start ──
  _offer_start "$PLAN_FILE" "$WORKING_DIR"
}

# ─── Display plan in TUI ─────────────────────────────────────────────────────

_display_plan() {
  local plan_content="$1"

  local plan_title
  plan_title=$(echo "$plan_content" | grep "^# Plan:" | head -1 | sed 's/^# Plan: //')

  echo ""
  _tui_header "$plan_title"

  echo "$plan_content" | python3 -c "
import sys, re

content = sys.stdin.read()
epics = re.findall(r'^## Epic:\s*(.+?)$\n([\s\S]*?)(?=^## Epic:|\Z)', content, re.MULTILINE)

if not epics:
    print('  (no epics found)')
    sys.exit(0)

for i, (header, body) in enumerate(epics):
    ref = header.split('—')[0].strip() if '—' in header else header.split('-')[0].strip()
    title = header.split('—', 1)[1].strip() if '—' in header else header

    print(f'  \033[1m\033[36m{ref}\033[0m \033[1m{title}\033[0m')

    # Extract description (before 'Acceptance criteria:')
    parts = body.split('Acceptance criteria:')
    desc = parts[0].strip()
    if desc:
        for line in desc.split('\n'):
            line = line.strip()
            if line:
                print(f'  \033[2m  {line}\033[0m')

    # Extract acceptance criteria
    if len(parts) > 1:
        criteria = parts[1].strip()
        for line in criteria.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                print(f'    \033[33m●\033[0m {line[2:]}')

    print()
" 2>/dev/null || echo "$plan_content"
}

# ─── Offer to start execution + dashboard ────────────────────────────────────

_offer_start() {
  local plan_file="$1"
  local working_dir="$2"

  [[ -t 0 ]] || return 0

  echo "  ┌─── Next Steps ───"
  echo "  │"
  echo "  │  \033[1m(s)\033[0m Start plan now — launch execution + dashboard"
  echo "  │  \033[1m(d)\033[0m Dashboard only — monitor without running"
  echo "  │  \033[1m(l)\033[0m Later — save and exit"
  echo "  │"
  echo "  └───────────────────────────────────────────"
  printf "  \033[36m❯\033[0m [s/d/l]: "
  local NEXT=""
  read -r NEXT

  local PORT
  PORT=$(_project_port "$working_dir")

  case "${NEXT:-s}" in
    [Ss]*)
      echo ""
      printf "  \033[32m✓\033[0m Starting dashboard on port %s...\n" "$PORT"
      # Start dashboard in background
      "$AGENTS_DIR/dashboard.sh" --port "$PORT" --project-dir "$working_dir" > /dev/null 2>&1 &
      local DASH_PID=$!
      echo "  \033[2mDashboard: http://localhost:$PORT (PID $DASH_PID)\033[0m"
      echo ""
      printf "  \033[32m✓\033[0m Launching plan execution...\n"
      echo ""
      exec "$AGENTS_DIR/run.sh" "$plan_file"
      ;;
    [Dd]*)
      echo ""
      printf "  \033[32m✓\033[0m Starting dashboard on port %s...\n" "$PORT"
      "$AGENTS_DIR/dashboard.sh" --port "$PORT" --project-dir "$working_dir" > /dev/null 2>&1 &
      local DASH_PID=$!
      echo "  \033[2mDashboard: http://localhost:$PORT (PID $DASH_PID)\033[0m"
      echo ""
      echo "  Run the plan later with:"
      echo "    ostwin plan start $plan_file"
      ;;
    *)
      echo ""
      echo "  Plan saved. Run later with:"
      echo "    ostwin plan start $plan_file"
      echo "  Dashboard:"
      echo "    ostwin dashboard --port $PORT"
      ;;
  esac
}

# ─── Template fallback ────────────────────────────────────────────────────────

_create_from_template() {
  local working_dir="$1"
  local plan_file="$2"
  local template="$PLANS_DIR/PLAN.template.md"

  if [[ -f "$template" ]]; then
    sed "s|working_dir: /path/to/your/project|working_dir: $working_dir|" \
      "$template" > "$plan_file"
  else
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

  echo ""
  printf "  \033[32m✓\033[0m Template plan saved to: %s\n" "$plan_file"
  echo ""
  echo "  Edit this file to define your epics, then run:"
  echo "    ostwin plan start $plan_file"
  echo ""
}

# ─── plan start ──────────────────────────────────────────────────────────────

plan_start() {
  local plan_file="${1:-}"

  if [[ -n "$plan_file" ]]; then
    if [[ ! -f "$plan_file" ]]; then
      if [[ -f "$PLANS_DIR/$plan_file" ]]; then
        plan_file="$PLANS_DIR/$plan_file"
      else
        echo "[ERROR] Plan file not found: $plan_file" >&2
        echo "  Available plans: ostwin plan list" >&2
        exit 1
      fi
    fi
    shift 2>/dev/null || true

    # Resolve project dir from plan config
    local wd
    wd=$(python3 -c "
import re
with open('$plan_file') as f:
    m = re.search(r'working_dir:\s*(.+)', f.read())
    print(m.group(1).strip() if m else '.')
" 2>/dev/null || echo ".")
    local PORT
    PORT=$(_project_port "$wd")

    # Auto-start dashboard if interactive
    if [[ -t 0 ]]; then
      printf "  \033[32m✓\033[0m Starting dashboard on port %s...\n" "$PORT"
      "$AGENTS_DIR/dashboard.sh" --port "$PORT" --project-dir "$wd" > /dev/null 2>&1 &
      echo "  \033[2mDashboard: http://localhost:$PORT\033[0m"
      echo ""
    fi

    exec "$AGENTS_DIR/run.sh" "$plan_file" "$@"
  else
    # Interactive mode: create then optionally start
    plan_create

    if [[ -n "$LAST_PLAN_FILE" ]] && [[ -f "$LAST_PLAN_FILE" ]]; then
      # _offer_start already handled in plan_create
      :
    fi
  fi
}

# ─── Dispatch ─────────────────────────────────────────────────────────────────

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
