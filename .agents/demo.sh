#!/usr/bin/env bash
# Agent OS — Web Dashboard Launcher
#
# Starts the FastAPI web dashboard for monitoring war-rooms.
#
# Usage: demo.sh [--port PORT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
DEMO_DIR="$AGENTS_DIR/../demo"
PORT=8000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: demo.sh [--port PORT]"
      echo "  Default port: 8000"
      exit 0
      ;;
    *) shift ;;
  esac
done

if [[ ! -f "$DEMO_DIR/api.py" ]]; then
  echo "[ERROR] Web demo not found at $DEMO_DIR/api.py" >&2
  echo "  The demo component is optional. Ensure demo/api.py exists." >&2
  exit 1
fi

# Check Python dependencies
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
  echo "[ERROR] Missing Python dependencies." >&2
  echo "  Install with: pip install fastapi uvicorn" >&2
  exit 1
}

echo "[DEMO] Starting web dashboard on http://localhost:${PORT}"
echo "  Press Ctrl+C to stop."
echo ""

cd "$DEMO_DIR"
exec python3 api.py --port "$PORT" 2>/dev/null || python3 -c "
import uvicorn
uvicorn.run('api:app', host='0.0.0.0', port=$PORT, log_level='info')
"
