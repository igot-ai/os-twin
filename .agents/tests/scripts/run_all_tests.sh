#!/bin/bash
set -e
# Get the absolute path to the .agents directory
AGENTS_DIR=$(cd "$(dirname "$0")/../.." && pwd)
echo "Running all Pester tests in $AGENTS_DIR..."
pwsh -NoProfile -Command "Invoke-Pester -Path '$AGENTS_DIR/tests/plan/Start-Plan.Tests.ps1', '$AGENTS_DIR/tests/plan/Expand-Plan.Tests.ps1', '$AGENTS_DIR/tests/plan/Multi-Room-DAG.Tests.ps1'"
