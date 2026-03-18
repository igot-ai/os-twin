#!/bin/bash
# Old test-running behavior from run.sh
AGENTS_DIR=$(dirname "$0")/..
pwsh -NoProfile -Command "Invoke-Pester -Path '$AGENTS_DIR/plan/Start-Plan.Tests.ps1' -Output Detailed" > /tmp/pester_final.txt 2>&1
echo "Tests finished. Output in /tmp/pester_final.txt"
