#!/bin/bash
# Agent OS — Master entry point for launching plans.
#
# Usage: ./run.sh <plan_file>
#
# Replaces old test-running behavior (moved to tests/run_pester.sh).

set -e

# Raise open file descriptor limit to prevent FD exhaustion during
# plan execution (many rooms × frequent status file polling).
ulimit -n 4096 2>/dev/null || true

PLAN_FILE=$1
if [[ -z "$PLAN_FILE" ]]; then
  echo "Usage: $0 <plan_file>"
  exit 1
fi

# Resolve PROJECT_DIR from plan's working_dir if not explicitly set
if [[ -z "$PROJECT_DIR" ]]; then
  if [[ -f "$PLAN_FILE" ]]; then
    EXTRACTED_DIR=$(grep -E "^\s*working_dir:\s*" "$PLAN_FILE" | head -n 1 | awk -F': ' '{print $2}' | xargs)
    if [[ -n "$EXTRACTED_DIR" ]]; then
      PROJECT_DIR="$EXTRACTED_DIR"
    else
      PROJECT_DIR=$(pwd)
    fi
  else
    PROJECT_DIR=$(pwd)
  fi
fi

# Ensure PROJECT_DIR exists (create automatically for non-interactive use)
if [[ ! -d "$PROJECT_DIR" ]]; then
  mkdir -p "$PROJECT_DIR" && echo "Created $PROJECT_DIR"
fi

# Check for pwsh
if ! command -v pwsh &> /dev/null; then
  echo "Error: 'pwsh' (PowerShell) is not installed or not in PATH."
  echo "Please install PowerShell to use Agent OS."
  exit 127
fi

if [[ ! -f "$PLAN_FILE" ]]; then
  echo "Error: Plan file not found: $PLAN_FILE"
  exit 1
fi

# Register plan in the local .agents/plans registry so the dashboard can discover it
AGENTS_DIR=$(dirname "$0")
GLOBAL_PLANS_DIR="$AGENTS_DIR/plans"
mkdir -p "$GLOBAL_PLANS_DIR"

PLAN_BASENAME=$(basename "$PLAN_FILE")
# Derive a clean plan_id: strip .md then optional .refined suffix
PLAN_ID="${PLAN_BASENAME%.md}"
PLAN_ID="${PLAN_ID%.refined}"

REGISTERED_PLAN="$GLOBAL_PLANS_DIR/$PLAN_ID.md"
REGISTERED_META="$GLOBAL_PLANS_DIR/$PLAN_ID.meta.json"

# Copy plan file if not already registered (or source is newer)
if [[ ! -f "$REGISTERED_PLAN" ]] || [[ "$PLAN_FILE" -nt "$REGISTERED_PLAN" ]]; then
  cp "$PLAN_FILE" "$REGISTERED_PLAN"
fi

# Write meta.json with working_dir so dashboard can find war-rooms
WARROOMS_DIR="$PROJECT_DIR/.war-rooms"
cat > "$REGISTERED_META" <<METAEOF
{
  "plan_id": "$PLAN_ID",
  "working_dir": "$PROJECT_DIR",
  "warrooms_dir": "$WARROOMS_DIR",
  "launched_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "active",
  "source_plan_file": "$PLAN_FILE"
}
METAEOF

# Execute Start-Plan.ps1
pwsh -NoProfile -File "$AGENTS_DIR/plan/Start-Plan.ps1" -PlanFile "$PLAN_FILE" -ProjectDir "$PROJECT_DIR" "${@:2}"
exit $?
