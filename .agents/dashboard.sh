#!/usr/bin/env bash
# Ostwin — Web Dashboard Launcher
#
# Starts the FastAPI web dashboard for monitoring war-rooms.
#
# Usage: dashboard.sh [--port PORT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
DASHBOARD_DIR="$AGENTS_DIR/../dashboard"
PORT=8000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: dashboard.sh [--port PORT]"
      echo "  Default port: 8000"
      exit 0
      ;;
    *) shift ;;
  esac
done

if [[ ! -f "$DASHBOARD_DIR/api.py" ]]; then
  echo "[ERROR] Web dashboard not found at $DASHBOARD_DIR/api.py" >&2
  echo "  The dashboard component is optional. Ensure dashboard/api.py exists." >&2
  exit 1
fi

# Check Python dependencies
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
  echo "[ERROR] Missing Python dependencies." >&2
  echo "  Install with: pip install fastapi uvicorn" >&2
  exit 1
}

echo "[DASHBOARD] Starting web dashboard on http://localhost:${PORT}"
echo "  Press Ctrl+C to stop."
echo ""

cd "$DASHBOARD_DIR"
exec python3 api.py --port "$PORT" 2>/dev/null || python3 -c "
import uvicorn
uvicorn.run('api:app', host='0.0.0.0', port=$PORT, log_level='info')
"
