#!/usr/bin/env bash
# Draft RELEASE.md from all completed war-rooms
#
# Usage: draft.sh <agents-dir>
#
# Reads all "pass" messages across war-rooms and compiles release notes.

set -euo pipefail

AGENTS_DIR="${1:-.agents}"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="${HOME}/.ostwin/.venv/bin/python" # fallback to global ostwin venv
[[ -x "$PYTHON" ]] || PYTHON="python3"
CHANNEL="$AGENTS_DIR/channel"
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
TEMPLATE="$AGENTS_DIR/release/RELEASE.template.md"
OUTPUT="$AGENTS_DIR/RELEASE.md"

VERSION="v0.1.0-$(date +%Y%m%d)"
DATE=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

echo "[RELEASE] Drafting release notes..."

# Collect task sections
TASK_SECTIONS=""
TASK_COUNT=0
QA_REQUIRED_COUNT=0
QA_PASS_COUNT=0
QA_NOT_REQUIRED_COUNT=0
QA_MISSING_COUNT=0

for room_dir in "$WARROOMS"/room-*/; do
  [[ -d "$room_dir" ]] || continue

  status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")
  task_ref=$(cat "$room_dir/task-ref" 2>/dev/null || echo "UNKNOWN")
  room_id=$(basename "$room_dir")

  # Skip control rooms and anything that is not actually completed.
  if [[ "$task_ref" == "PLAN-REVIEW" ]]; then
    continue
  fi
  if [[ "$status" != "passed" ]]; then
    continue
  fi

  # Read brief description (first line header)
  task_title=$(head -1 "$room_dir/brief.md" 2>/dev/null | sed 's/^# //' || echo "$task_ref")

  # Build an accurate QA summary from lifecycle + channel history.
  qa_meta=$("$PYTHON" -c "
import json, re
from pathlib import Path

room_dir = Path(r'''$room_dir''')

def clean_body(body: str, max_lines: int = 10) -> str:
    noise_patterns = [
        r'^\U0001f527',
        r'[Cc]alling tool:',
        r'^\s*\w{0,5}\s*tool:',
        r'^Loading MCP',
        r'^Running task non-interactively',
        r'^Agent active',
        r'^Usage Stats',
        r'^\s*gemini-',
        r'^. Task completed',
        r'^System\.Management\.Automation',
        r'^\s*Reqs\s+InputTok',
    ]
    clean_lines = []
    for ln in body.split('\n'):
        stripped = ln.strip()
        if not stripped:
            continue
        if len(stripped) < 4:
            continue
        if any(re.search(p, stripped) for p in noise_patterns):
            continue
        clean_lines.append(ln)
    if clean_lines:
        return '\n'.join(clean_lines[:max_lines])
    return ''

requires_qa = False
try:
    lifecycle = json.loads((room_dir / 'lifecycle.json').read_text(encoding='utf-8'))
    for state in (lifecycle.get('states') or {}).values():
        if not isinstance(state, dict):
            continue
        if state.get('role') == 'qa' or state.get('type') == 'review':
            requires_qa = True
            break
except Exception:
    requires_qa = False

qa_msgs = []
try:
    with (room_dir / 'channel.jsonl').open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if msg.get('from') == 'qa' and msg.get('type') in {'pass', 'fail', 'error', 'done', 'escalate'}:
                qa_msgs.append(msg)
except Exception:
    pass

qa_status = 'missing'
qa_verdict = 'QA required but no QA message was recorded.'
if not requires_qa:
    qa_status = 'not_required'
    qa_verdict = 'Not required for this lifecycle.'
elif qa_msgs:
    latest_pass = next((m for m in reversed(qa_msgs) if m.get('type') == 'pass'), None)
    if latest_pass:
        qa_status = 'pass'
        qa_verdict = clean_body(latest_pass.get('body', 'Approved')) or 'VERDICT: PASS'
    else:
        latest = qa_msgs[-1]
        latest_type = (latest.get('type') or 'unknown').lower()
        latest_body = clean_body(latest.get('body', ''))
        prefix_map = {
            'fail': 'Latest QA verdict: FAIL. No final QA PASS was recorded.',
            'error': 'Latest QA outcome: ERROR/TIMEOUT. No final QA PASS was recorded.',
            'done': 'Latest QA completion message recorded, but no explicit QA PASS was recorded.',
            'escalate': 'Latest QA verdict: ESCALATE. No final QA PASS was recorded.',
        }
        qa_verdict = prefix_map.get(latest_type, 'QA activity was recorded, but no final QA PASS was recorded.')
        if latest_body:
            qa_verdict = qa_verdict + '\n' + latest_body

print(json.dumps({
    'requires_qa': requires_qa,
    'qa_status': qa_status,
    'qa_verdict': qa_verdict,
}))
" 2>/dev/null || echo '{"requires_qa": false, "qa_status": "missing", "qa_verdict": "Unavailable"}')

  qa_requires=$(
    printf '%s' "$qa_meta" | "$PYTHON" -c "import json,sys; print('true' if json.load(sys.stdin).get('requires_qa') else 'false')"
  )
  qa_status=$(
    printf '%s' "$qa_meta" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('qa_status', 'missing'))"
  )
  qa_verdict=$(
    printf '%s' "$qa_meta" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('qa_verdict', 'Unavailable'))"
  )

  if [[ "$qa_requires" == "true" ]]; then
    QA_REQUIRED_COUNT=$((QA_REQUIRED_COUNT + 1))
  else
    QA_NOT_REQUIRED_COUNT=$((QA_NOT_REQUIRED_COUNT + 1))
  fi

  if [[ "$qa_status" == "pass" ]]; then
    QA_PASS_COUNT=$((QA_PASS_COUNT + 1))
  elif [[ "$qa_requires" == "true" ]]; then
    QA_MISSING_COUNT=$((QA_MISSING_COUNT + 1))
  fi

  TASK_SECTIONS="${TASK_SECTIONS}
### $task_ref — $task_title

- **Room**: $room_id
- **Status**: $status
- **QA Verdict**: $qa_verdict
"
  TASK_COUNT=$((TASK_COUNT + 1))
done

SUMMARY="$TASK_COUNT deliverable room(s) completed. Final QA PASS recorded for $QA_PASS_COUNT/$QA_REQUIRED_COUNT QA-gated room(s); $QA_NOT_REQUIRED_COUNT room(s) did not require QA."
if [[ "$QA_MISSING_COUNT" -gt 0 ]]; then
  SUMMARY="$SUMMARY $QA_MISSING_COUNT QA-gated room(s) have no final QA PASS and require manual review."
fi

# Build release notes from template
if [[ -f "$TEMPLATE" ]]; then
  sed -e "s|{{VERSION}}|$VERSION|g" \
      -e "s|{{DATE}}|$DATE|g" \
      -e "s|{{STATUS}}|Draft|g" \
      -e "s|{{SUMMARY}}|$SUMMARY|g" \
      "$TEMPLATE" | \
    "$PYTHON" -c "
import sys
content = sys.stdin.read()
task_sections = '''$TASK_SECTIONS'''
content = content.replace('{{TASK_SECTIONS}}', task_sections)
content = content.replace('{{SIGNOFF_ROWS}}', '| Manager | Pending | - |\n| Engineer | Pending | - |\n| QA | Pending | - |')
print(content)
" > "$OUTPUT"
else
  # Fallback: generate without template
  cat > "$OUTPUT" << EOF
# Release: $VERSION

**Date**: $DATE
**Status**: Draft

## Summary

$SUMMARY

## Tasks Completed

$TASK_SECTIONS

## Sign-offs

| Role     | Status  | Timestamp |
|----------|---------|-----------|
| Manager  | Pending | -         |
| Engineer | Pending | -         |
| QA       | Pending | -         |

---

*Generated by Agent OS*
EOF
fi

echo "[RELEASE] Draft written to: $OUTPUT"
echo "[RELEASE] $TASK_COUNT tasks included."
