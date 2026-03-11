#!/usr/bin/env bash
# Post a message to a war-room channel
#
# Usage: post.sh <war-room-dir> <from> <to> <type> <ref> <body>
#
# Features:
#   - File locking (fcntl.LOCK_EX) for concurrent write safety
#   - Message validation (from/to/type/body size)
#   - Message versioning (v:1)
#
# Example:
#   post.sh .agents/war-rooms/room-001 manager engineer task TASK-001 "Implement auth"

set -euo pipefail

ROOM_DIR="$1"
FROM="$2"
TO="$3"
TYPE="$4"
REF="$5"
BODY="$6"

CHANNEL_FILE="${ROOM_DIR}/channel.jsonl"

# Ensure channel directory and file exist
mkdir -p "$ROOM_DIR"
touch "$CHANNEL_FILE"

# Read max message size from config (if available)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"

# Build, validate, and write JSON message with file locking — all in one Python call
# Uses fcntl.LOCK_EX for atomic writes, matching MCP channel-server.py semantics
python3 -c "
import json, sys, os, fcntl, time

from_val = sys.argv[1]
to_val = sys.argv[2]
type_val = sys.argv[3]
ref_val = sys.argv[4]
body_val = sys.argv[5]
channel_file = sys.argv[6]
config_file = sys.argv[7]

# --- Validation ---
VALID_ROLES = {'manager', 'engineer', 'qa'}
VALID_TYPES = {'task', 'done', 'review', 'pass', 'fail', 'fix', 'error', 'signoff', 'release'}

if from_val not in VALID_ROLES:
    print(f'[WARN] Invalid from: {from_val}', file=sys.stderr)
if type_val not in VALID_TYPES:
    print(f'[WARN] Invalid type: {type_val}', file=sys.stderr)

# Body size enforcement
max_size = 65536
try:
    config = json.load(open(config_file))
    max_size = config.get('channel', {}).get('max_message_size_bytes', 65536)
except Exception:
    pass

if len(body_val) > max_size:
    body_val = body_val[:max_size] + f'\n[TRUNCATED: original {len(body_val)} bytes, max {max_size}]'

# --- Build message ---
ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
try:
    ns = str(time.time_ns())
except AttributeError:
    ns = str(int(time.time() * 1e9))
msg_id = f'{from_val}-{type_val}-{ns}-{os.getpid()}'

msg = {
    'v': 1,
    'id': msg_id,
    'ts': ts,
    'from': from_val,
    'to': to_val,
    'type': type_val,
    'ref': ref_val,
    'body': body_val,
}

line = json.dumps(msg) + '\n'

# --- Atomic write with file locking ---
with open(channel_file, 'a') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        f.write(line)
        f.flush()
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

print(msg_id)
" "$FROM" "$TO" "$TYPE" "$REF" "$BODY" "$CHANNEL_FILE" "$CONFIG"
