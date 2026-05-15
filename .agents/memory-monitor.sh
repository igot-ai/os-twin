#!/bin/bash
# Memory Monitor — check status and watch ledger in real-time
#
# Usage:
#   ./memory-monitor.sh status    # Check if memory is ON or OFF
#   ./memory-monitor.sh watch     # Live monitor ledger
#   ./memory-monitor.sh on        # Enable memory (restore .venv)
#   ./memory-monitor.sh off       # Disable memory (move .venv)

AGENTS_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$AGENTS_DIR/.venv"
VENV_BAK="$AGENTS_DIR/.venv.bak"
# Legacy ledger location (kept for backward compat)
LEDGER="$AGENTS_DIR/memory/ledger.jsonl"
# Centralized memory is at ~/.ostwin/memory/ — ledger may not exist here

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

case "${1:-status}" in
  status)
    echo ""
    # Check .venv
    if [[ -f "$VENV/bin/python" ]]; then
      if "$VENV/bin/python" -c "import mcp" 2>/dev/null; then
        echo -e "  MCP venv:  ${GREEN}ON${NC}  ($VENV)"
      else
        echo -e "  MCP venv:  ${YELLOW}EXISTS but missing mcp module${NC}"
      fi
    else
      echo -e "  MCP venv:  ${RED}OFF${NC}  (.venv not found)"
    fi

    # Check ledger
    if [[ -f "$LEDGER" ]]; then
      LINES=$(wc -l < "$LEDGER")
      LAST_TS=$(tail -1 "$LEDGER" 2>/dev/null | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('ts','?'))" 2>/dev/null || echo "?")
      echo -e "  Ledger:    ${GREEN}$LINES entries${NC}  (last: $LAST_TS)"
    else
      echo -e "  Ledger:    ${YELLOW}empty${NC}  (no file)"
    fi
    echo ""
    ;;

  watch)
    echo -e "${GREEN}Watching memory ledger...${NC} (Ctrl+C to stop)"
    echo ""
    INITIAL=$(wc -l < "$LEDGER" 2>/dev/null || echo 0)
    echo "Starting at $INITIAL entries"
    echo "---"
    tail -n 0 -f "$LEDGER" 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
        kind = e.get('kind','?')
        room = e.get('room_id','?')
        ref = e.get('ref','?')
        summary = e.get('summary','')[:80]
        print(f'  [{e.get(\"ts\",\"?\")}] {kind:12s} {room:12s} {ref:10s} {summary}')
    except:
        pass
"
    ;;

  on)
    if [[ -f "$VENV/bin/python" ]]; then
      echo -e "${GREEN}Memory already ON${NC}"
    elif [[ -d "$VENV_BAK" ]]; then
      mv "$VENV_BAK" "$VENV"
      echo -e "${GREEN}Memory ON${NC} (restored .venv)"
    else
      echo -e "${RED}No .venv or .venv.bak found. Create with:${NC}"
      echo "  cd $AGENTS_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install 'mcp[cli]' fastmcp"
    fi
    ;;

  off)
    if [[ -d "$VENV" ]]; then
      mv "$VENV" "$VENV_BAK"
      echo -e "${RED}Memory OFF${NC} (moved .venv → .venv.bak)"
    else
      echo -e "${YELLOW}Memory already OFF${NC}"
    fi
    ;;

  *)
    echo "Usage: $0 {status|watch|on|off}"
    ;;
esac
