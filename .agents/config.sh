#!/usr/bin/env bash
# Agent OS — Configuration Manager
#
# View and update Agent OS configuration.
#
# Usage:
#   config.sh                              # Print full config
#   config.sh --get manager.poll_interval  # Get a specific value
#   config.sh --set manager.max_concurrent_rooms 10  # Set a value

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"

MODE=""
KEY=""
VALUE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --get)  MODE="get"; KEY="$2"; shift 2 ;;
    --set)  MODE="set"; KEY="$2"; VALUE="$3"; shift 3 ;;
    -h|--help)
      echo "Usage: config.sh [--get KEY] [--set KEY VALUE]"
      echo ""
      echo "Examples:"
      echo "  config.sh                                    # Show full config"
      echo "  config.sh --get manager.poll_interval_seconds"
      echo "  config.sh --set manager.max_concurrent_rooms 10"
      echo ""
      echo "Keys use dot notation: manager.poll_interval_seconds"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  # Print full config with nice formatting
  python3 -c "import json; print(json.dumps(json.load(open('$CONFIG')), indent=2))"
  exit 0
fi

if [[ "$MODE" == "get" ]]; then
  python3 -c "
import json, functools
config = json.load(open('$CONFIG'))
keys = '${KEY}'.split('.')
val = functools.reduce(lambda d, k: d[k], keys, config)
if isinstance(val, dict):
    print(json.dumps(val, indent=2))
else:
    print(val)
" || { echo "[ERROR] Key not found: $KEY" >&2; exit 1; }
  exit 0
fi

if [[ "$MODE" == "set" ]]; then
  python3 -c "
import json

config = json.load(open('$CONFIG'))
keys = '${KEY}'.split('.')
value = '${VALUE}'

# Try to parse as number or boolean
try:
    value = int(value)
except ValueError:
    try:
        value = float(value)
    except ValueError:
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False

# Navigate to parent and set
obj = config
for k in keys[:-1]:
    obj = obj[k]
obj[keys[-1]] = value

json.dump(config, open('$CONFIG', 'w'), indent=2)
print(f'Set {\".\".join(keys)} = {value}')
" || { echo "[ERROR] Failed to set: $KEY = $VALUE" >&2; exit 1; }
  exit 0
fi
