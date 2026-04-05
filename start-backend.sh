#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/dashboard"
source .venv/bin/activate
exec python api.py "$@"
