#!/bin/bash
# ── Memory Test Suite Runner ─────────────────────────────────────────────────
# Runs both Python (pytest) and PowerShell (Pester) memory tests.
#
# Usage:
#   bash .agents/tests/memory/run-tests.sh          # Run all tests
#   bash .agents/tests/memory/run-tests.sh python    # Python only
#   bash .agents/tests/memory/run-tests.sh pester    # Pester only
#
# Uses the existing venv at ~/.ostwin/.venv
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_ROOT="$(cd "$AGENTS_DIR/.." && pwd)"
VENV_DIR="$HOME/.ostwin/.venv"
PYTHON="$VENV_DIR/bin/python3"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

MODE="${1:-all}"  # all, python, pester

echo ""
echo -e "${CYAN}╭──────────────────────────────────────────────────╮${NC}"
echo -e "${CYAN}│  Agent Memory Test Suite                         │${NC}"
echo -e "${CYAN}╰──────────────────────────────────────────────────╯${NC}"
echo ""

# ── Check prerequisites ──────────────────────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}❌  Python not found at $PYTHON${NC}"
    echo "    Expected venv at: $VENV_DIR"
    exit 1
fi

# Install pytest into the venv if not present
if ! "$PYTHON" -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}📦  Installing pytest into venv...${NC}"
    "$PYTHON" -m pip install --quiet pytest 2>/dev/null || {
        echo -e "${RED}❌  Failed to install pytest. Try: $PYTHON -m pip install pytest${NC}"
        exit 1
    }
fi

PASS=0
FAIL=0

# ── Python Tests (pytest) ────────────────────────────────────────────────────
if [ "$MODE" = "all" ] || [ "$MODE" = "python" ]; then
    echo -e "${CYAN}━━━ Python Tests (pytest) ━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if "$PYTHON" -m pytest "$SCRIPT_DIR" \
        -v \
        --tb=short \
        --no-header \
        -q \
        2>&1; then
        echo ""
        echo -e "${GREEN}✅  Python tests passed${NC}"
        PASS=$((PASS + 1))
    else
        echo ""
        echo -e "${RED}❌  Python tests failed${NC}"
        FAIL=$((FAIL + 1))
    fi
    echo ""
fi

# ── PowerShell Tests (Pester) ────────────────────────────────────────────────
if [ "$MODE" = "all" ] || [ "$MODE" = "pester" ]; then
    echo -e "${CYAN}━━━ PowerShell Tests (Pester) ━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    PESTER_FILES=(
        "$SCRIPT_DIR/Resolve-Memory.Tests.ps1"
        "$SCRIPT_DIR/Run-MemoryDecay.Tests.ps1"
        "$SCRIPT_DIR/Consolidate-Memory.Tests.ps1"
        "$SCRIPT_DIR/Build-SystemPrompt-Memory.Tests.ps1"
    )

    PESTER_PATHS=""
    for f in "${PESTER_FILES[@]}"; do
        if [ -f "$f" ]; then
            if [ -n "$PESTER_PATHS" ]; then
                PESTER_PATHS="$PESTER_PATHS, '$f'"
            else
                PESTER_PATHS="'$f'"
            fi
        fi
    done

    if [ -n "$PESTER_PATHS" ]; then
        if pwsh -NoProfile -Command "Invoke-Pester -Path $PESTER_PATHS -Output Detailed" 2>&1; then
            echo ""
            echo -e "${GREEN}✅  Pester tests passed${NC}"
            PASS=$((PASS + 1))
        else
            echo ""
            echo -e "${RED}❌  Pester tests failed${NC}"
            FAIL=$((FAIL + 1))
        fi
    else
        echo -e "${YELLOW}⚠  No Pester test files found${NC}"
    fi
    echo ""
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo -e "${CYAN}━━━ Summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Suites passed: ${GREEN}$PASS${NC}"
echo -e "  Suites failed: ${RED}$FAIL${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}❌  Some test suites failed!${NC}"
    exit 1
else
    echo -e "${GREEN}✅  All test suites passed!${NC}"
    exit 0
fi
