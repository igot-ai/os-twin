#!/bin/bash
# `.agents/tests/run-all.sh`
# Run all test suites: channel, warroom, manager, and plan (e2e)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
declare -A RESULTS
TOTAL_FAILED=0

echo "=========================================="
echo "Running all test suites"
echo "=========================================="
echo ""

# Function to run a test suite
run_suite() {
    local name="$1"
    shift
    local tests=("$@")
    
    echo -e "${YELLOW}Running $name tests...${NC}"
    
    if pwsh -NoProfile -Command "Invoke-Pester -Path '${tests[@]}' -Output Minimal" 2>&1; then
        echo -e "${GREEN}✓ $name tests passed${NC}"
        RESULTS["$name"]="PASS"
        return 0
    else
        echo -e "${RED}✗ $name tests failed${NC}"
        RESULTS["$name"]="FAIL"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
        return 1
    fi
}

# Suite 1: Channel tests
CHANNEL_TESTS=(
    "$AGENTS_DIR/tests/channel/Channel-Negotiation.Tests.ps1"
    "$AGENTS_DIR/tests/channel/ChannelCLI.Tests.ps1"
    "$AGENTS_DIR/tests/channel/Post-Message.Tests.ps1"
    "$AGENTS_DIR/tests/channel/Read-Messages.Tests.ps1"
    "$AGENTS_DIR/tests/channel/RoleCommunication.Tests.ps1"
    "$AGENTS_DIR/tests/channel/Wait-ForMessage.Tests.ps1"
)
run_suite "channel" "${CHANNEL_TESTS[@]}" || true
echo ""

# Suite 2: War-room tests
WARROOM_TESTS=(
    "$AGENTS_DIR/tests/war-rooms/Get-WarRoomStatus.Tests.ps1"
    "$AGENTS_DIR/tests/war-rooms/New-GoalReport.Tests.ps1"
    "$AGENTS_DIR/tests/war-rooms/New-WarRoom.Lifecycle.Tests.ps1"
    "$AGENTS_DIR/tests/war-rooms/New-WarRoom.Tests.ps1"
    "$AGENTS_DIR/tests/war-rooms/Remove-WarRoom.Tests.ps1"
    "$AGENTS_DIR/tests/war-rooms/Test-GoalCompletion.Tests.ps1"
)
run_suite "warroom" "${WARROOM_TESTS[@]}" || true
echo ""

# Suite 3: Manager tests
MANAGER_TESTS=(
    "$AGENTS_DIR/tests/roles/manager/Deadlock.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/LifecycleRoleTransition.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/ManagerLoop-Helpers.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/Orchestration.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/Redesign.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/Resolve-RoomSkills.Tests.ps1"
    "$AGENTS_DIR/tests/roles/manager/Start-ManagerLoop.Tests.ps1"
)
run_suite "manager" "${MANAGER_TESTS[@]}" || true
echo ""

# Suite 4: Plan/E2E tests
PLAN_TESTS=(
    "$AGENTS_DIR/tests/plan/Multi-Room-DAG.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Test-DependenciesReady.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Build-DependencyGraph.Tests.ps1"
    "$AGENTS_DIR/tests/plan/New-Plan.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Update-Progress.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Unified-Negotiation.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Build-PlanningDAG.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Start-Plan.Tests.ps1"
    "$AGENTS_DIR/tests/plan/Expand-Plan.Tests.ps1"
)
run_suite "e2e" "${PLAN_TESTS[@]}" || true
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
for suite in channel warroom manager e2e; do
    status="${RESULTS[$suite]:-SKIPPED}"
    if [[ "$status" == "PASS" ]]; then
        echo -e "${GREEN}✓ $suite: $status${NC}"
    else
        echo -e "${RED}✗ $suite: $status${NC}"
    fi
done
echo ""

if [[ $TOTAL_FAILED -eq 0 ]]; then
    echo -e "${GREEN}All test suites passed!${NC}"
    exit 0
else
    echo -e "${RED}$TOTAL_FAILED test suite(s) failed${NC}"
    exit 1
fi
