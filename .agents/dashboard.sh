#!/usr/bin/env bash
# Ostwin — Web Dashboard Launcher
#
# Starts the FastAPI web dashboard for monitoring war-rooms.
#
# Usage: dashboard.sh [--port PORT] [--project-dir PATH]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"

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
PORT=8000
PROJECT_DIR="$(pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)        PORT="$2"; shift 2 ;;
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: dashboard.sh [--port PORT] [--project-dir PATH]"
      echo "  --port PORT         Server port (default: 8000)"
      echo "  --project-dir PATH  Project to monitor (default: current directory)"
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
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
  echo "[ERROR] Missing Python dependencies." >&2
  echo "  Install with: pip install fastapi uvicorn" >&2
  exit 1
}

# Resolve project dir to absolute path
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

echo "[DASHBOARD] Starting web dashboard on http://localhost:${PORT}"
echo "  Project: $PROJECT_DIR"
echo "  War-rooms: $PROJECT_DIR/.war-rooms"
echo "  Press Ctrl+C to stop."
echo ""

cd "$DASHBOARD_DIR"
exec python3 api.py --port "$PORT" --project-dir "$PROJECT_DIR"
