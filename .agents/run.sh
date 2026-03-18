#!/bin/bash
# Agent OS — Master entry point for launching plans.
#
# Usage: ./run.sh <plan_file>
#
# Replaces old test-running behavior (moved to tests/run_pester.sh).

set -e

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

# Execute Start-Plan.ps1
AGENTS_DIR=$(dirname "$0")
pwsh -NoProfile -File "$AGENTS_DIR/plan/Start-Plan.ps1" -PlanFile "$PLAN_FILE" -ProjectDir "$PROJECT_DIR" "${@:2}"
exit $?

