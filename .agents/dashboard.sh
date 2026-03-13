#!/usr/bin/env bash
# Ostwin — Web Dashboard Launcher
#
# Starts the FastAPI web dashboard for monitoring war-rooms.
#
# Usage: dashboard.sh [--port PORT] [--project-dir PATH] [--background]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

# Resolve dashboard directory:
#   1. Inside .agents/dashboard/ (installed via ostwin init)
#   2. Sibling to .agents/ (source repo layout)
if [[ -d "$AGENTS_DIR/dashboard" ]]; then
  DASHBOARD_DIR="$AGENTS_DIR/dashboard"
elif [[ -d "$AGENTS_DIR/../dashboard" ]]; then
  DASHBOARD_DIR="$AGENTS_DIR/../dashboard"
else
  DASHBOARD_DIR=""
fi
PORT=9000
PROJECT_DIR="$(pwd)"
BACKGROUND=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)        PORT="$2"; shift 2 ;;
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    --background)  BACKGROUND=true; shift ;;
    -h|--help)
      echo "Usage: dashboard.sh [--port PORT] [--project-dir PATH] [--background]"
      echo "  --port PORT         Server port (default: 9000)"
      echo "  --project-dir PATH  Project to monitor (default: current directory)"
      echo "  --background        Run in background (write PID to dashboard.pid)"
      exit 0
      ;;
    *) shift ;;
  esac
done

if [[ -z "$DASHBOARD_DIR" ]] || [[ ! -f "$DASHBOARD_DIR/api.py" ]]; then
  echo "[ERROR] Web dashboard not found." >&2
  echo "  Looked in:" >&2
  echo "    $AGENTS_DIR/dashboard/api.py" >&2
  echo "    $AGENTS_DIR/../dashboard/api.py" >&2
  echo "" >&2
  echo "  If installed via 'ostwin init', re-run init to copy the dashboard." >&2
  echo "  If running from source, ensure dashboard/api.py exists alongside .agents/." >&2
  exit 1
fi

# Check Python dependencies
"$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null || {
  echo "[ERROR] Missing Python dependencies." >&2
  echo "  Install with: pip install fastapi uvicorn" >&2
  exit 1
}

# Resolve project dir to absolute path
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

PID_FILE="$AGENTS_DIR/dashboard.pid"

if $BACKGROUND; then
  echo "[DASHBOARD] Starting in background on http://localhost:${PORT}"
  echo "  Project: $PROJECT_DIR"
  cd "$DASHBOARD_DIR"
  nohup "$PYTHON" api.py --port "$PORT" --project-dir "$PROJECT_DIR" > "$AGENTS_DIR/logs/dashboard.log" 2>&1 &
  DASH_PID=$!
  echo "$DASH_PID" > "$PID_FILE"
  echo "  PID: $DASH_PID (log: $AGENTS_DIR/logs/dashboard.log)"
else
  echo "[DASHBOARD] Starting web dashboard on http://localhost:${PORT}"
  echo "  Project: $PROJECT_DIR"
  echo "  War-rooms: $PROJECT_DIR/.war-rooms"
  echo "  Press Ctrl+C to stop."
  echo ""
  echo "$$" > "$PID_FILE"
  cd "$DASHBOARD_DIR"
  exec "$PYTHON" api.py --port "$PORT" --project-dir "$PROJECT_DIR"
fi

