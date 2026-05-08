#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]] || [[ -z "${2:-}" ]]; then
  echo "Usage: $0 <role_name> <agents_dir> [description] [model] [timeout]"
  exit 1
fi

ROLE_NAME="$1"
AGENTS_DIR="$2"
DESCRIPTION="${3:-}"
MODEL="${4:-google-vertex/gemini-3-flash-preview}"
TIMEOUT="${5:-600}"

SAFE_NAME=$(echo "$ROLE_NAME" | sed 's/[^a-zA-Z0-9-]/-/g; s/-\+/-/g; s/^-//; s/-$//')

echo "Creating missing role: $ROLE_NAME..."

NEW_DYNAMIC_ROLE="$AGENTS_DIR/roles/_base/New-DynamicRole.ps1"
ROLE_DIR=""

# ── Phase 1: Fast programmatic scaffolding via New-DynamicRole.ps1 ──
if [[ -x "$(command -v pwsh)" ]] && [[ -f "$NEW_DYNAMIC_ROLE" ]]; then
  echo "  [1/3] Scaffolding role structure..."

  SCAFFOLD_ARGS=(-RoleName "$ROLE_NAME" -AgentsDir "$AGENTS_DIR" -Model "$MODEL" -Timeout "$TIMEOUT")
  if [[ -n "$DESCRIPTION" ]]; then
    SCAFFOLD_ARGS+=(-Description "$DESCRIPTION")
  fi

  if ROLE_DIR=$(pwsh -NoProfile -File "$NEW_DYNAMIC_ROLE" "${SCAFFOLD_ARGS[@]}" 2>/dev/null); then
    if [[ -n "$ROLE_DIR" ]] && [[ -d "$ROLE_DIR" ]]; then
      echo "  Role directory created at $ROLE_DIR"
    fi
  else
    echo "  Warning: Fast scaffolding failed. Falling back to full LLM agent..."
    ROLE_DIR=""
  fi
else
  echo "  Warning: New-DynamicRole.ps1 or pwsh not found. Falling back to full LLM agent..."
fi

# ── Phase 2: Write dummy ROLE.md with proper frontmatter format ──
if [[ -n "$ROLE_DIR" ]] && [[ -d "$ROLE_DIR" ]]; then
  ROLE_MD_PATH="$ROLE_DIR/ROLE.md"
  NEEDS_ROLE_MD=false

  if [[ ! -f "$ROLE_MD_PATH" ]]; then
    NEEDS_ROLE_MD=true
  else
    if ! head -1 "$ROLE_MD_PATH" | grep -q '^---'; then
      NEEDS_ROLE_MD=true
    fi
  fi

  if [[ "$NEEDS_ROLE_MD" == true ]]; then
    echo "  [2/3] Writing ROLE.md stub..."

    ROLE_DESC="${DESCRIPTION:-You are a $SAFE_NAME specialist agent working within a war-room team.}"

    cat > "$ROLE_MD_PATH" << ROLEMD
---
name: $SAFE_NAME
description: $ROLE_DESC
tags: [$SAFE_NAME]
trust_level: dynamic
---

# $SAFE_NAME

$ROLE_DESC

## Your Responsibilities

When assigned an Epic (EPIC-XXX), you own the full planning and implementation cycle.
When assigned a Task (TASK-XXX), implement it directly.

### Phase 0 — Context (ALWAYS DO THIS FIRST)
Before writing any code, load context from both layers:
\`\`\`
search_memory(query="<terms from your brief>")
memory_tree()
knowledge_query("project-docs", "What are the conventions for <area>?", mode="summarized")
\`\`\`

### Phase 1 — Planning
1. Read the brief and understand the goal
2. Break into concrete, independently testable sub-tasks
3. Create TASKS.md with your plan (if Epic)
4. Save TASKS.md before proceeding

### Phase 2 — Implementation
1. Work through each sub-task sequentially
2. After completing each, check it off in TASKS.md
3. Write tests as you go

### Phase 3 — Reporting
1. Ensure all checkboxes in TASKS.md are checked
2. MANDATORY: Save to memory:
   \`\`\`
   save_memory(
     content="<key code, interfaces, decisions>",
     name="<descriptive name>",
     path="code/<module>",
     tags=["<relevant>", "<tags>"]
   )
   \`\`\`
3. Post a done message with:
   - Summary of changes made
   - Files modified/created
   - How to test

## When Fixing QA Feedback

1. Read the fix message carefully
2. Address every point raised by QA
3. Do not introduce new issues while fixing
4. Post a new done message explaining what was fixed

## Communication

Use the channel MCP tools to:
- Report progress: \`report_progress(percent, message)\`
- Post completion: \`post_message(type="done", body="...")\`

## Quality Standards

- Code must compile/parse without errors
- Include inline comments for non-obvious logic
- Follow existing project conventions and patterns
- Handle edge cases mentioned in the task description
- MANDATORY: Save key code and decisions to memory after every significant action
ROLEMD

    echo "  ROLE.md written to $ROLE_MD_PATH"
  else
    echo "  [2/3] ROLE.md already exists with proper format."
  fi

  # ── Phase 3: Register in registry.json ──
  echo "  [3/3] Registering in registry.json..."
  REGISTRY_PATH="$AGENTS_DIR/roles/registry.json"
  if [[ -f "$REGISTRY_PATH" ]]; then
    if ! python3 -c "
import json, sys
with open('$REGISTRY_PATH') as f:
    reg = json.load(f)
if not any(r['name'] == '$SAFE_NAME' for r in reg['roles']):
    rel_dir = 'contributes/roles/$SAFE_NAME' if 'contributes' in '$ROLE_DIR' else 'roles/$SAFE_NAME'
    pascal = ''.join(w.capitalize() for w in '$SAFE_NAME'.split('-'))
    entry = {
        'name': '$SAFE_NAME',
        'description': '$(if [[ -n "$DESCRIPTION" ]]; then echo "$DESCRIPTION"; else echo "$SAFE_NAME specialist agent"; fi)',
        'runner': f'{rel_dir}/Start-{pascal}.ps1',
        'definition': f'{rel_dir}/role.json',
        'prompt': f'{rel_dir}/ROLE.md',
        'default_assignment': False,
        'instance_support': True,
        'supported_task_types': ['task', 'epic'],
        'capabilities': ['code-generation', 'file-editing', 'shell-execution'],
        'quality_gates': [],
        'default_model': '$MODEL'
    }
    reg['roles'].append(entry)
    with open('$REGISTRY_PATH', 'w') as f:
        json.dump(reg, f, indent=2)
    print('  Registered $SAFE_NAME in registry.json')
else:
    print('  $SAFE_NAME already in registry.json')
" 2>/dev/null; then
      echo "  (registry.json update skipped — python3 not available)"
    fi
  fi

  echo "  Done."
  exit 0
fi

# ── Fallback: Full LLM agent (if Phase 1 failed entirely) ──
echo "  Falling back to full LLM agent for role creation..."

MANAGER_PROMPT="We need a new agent role called '$ROLE_NAME'. Please use the create-role skill to scaffold it. Create role.json and ROLE.md in the appropriate role directory. Ensure the role is registered in registry.json. Keep the role definition simple and functional."

OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
AGENT_BIN="${OSTWIN_AGENT_CMD:-$OSTWIN_HOME/.agents/bin/agent}"

if [ ! -x "$AGENT_BIN" ]; then
  echo "Agent binary not found at: $AGENT_BIN"
  echo "Run the installer or set \$OSTWIN_AGENT_CMD."
  exit 1
fi

MCP_CONFIG="$AGENTS_DIR/mcp/config.json"
"$AGENT_BIN" -a manager -n "$MANAGER_PROMPT" --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config "$MCP_CONFIG"
exit $?
