---
name: register-run-bash
description: Use this skill to autonomously create the execution wrapper (run.sh) for a new agent role and register its state transitions in the Manager's bash loop so it can be spawned.
---

# register-run-bash

## Overview

Use this skill immediately after defining a new role via `register-role`. 
An agent is not spawned until it has a `run.sh` execution script bridging the `deepagents` CLI to the war-room JSONL channels, AND the Manager's `loop.sh` is updated to spawn it during the correct state.

## Instructions

### 1. Analyze the New Role's Communication Needs
Read the newly created `.agents/.cache/roles/<role-name>/ROLE.md`.
- What message types trigger this agent? (e.g., `task`, `done`, `review`).
- What does it output? (e.g., `pass`, `fail`, `report`).

### 2. Create the run.sh Execution Wrapper
Create `.agents/.cache/roles/<role-name>/run.sh`. This script is how the agent is spawned in a war-room.
1. Read the template at `.agents/roles/general-agents/run.sh`.
2. Copy its structure to `.agents/.cache/roles/<role-name>/run.sh`.
3. **Customize the Configuration**: Set the correct config keys and environment variable overrides (e.g., `[ROLE_NAME]_CMD`).
4. **Customize the Input Gathering**: Update the python JSONL parser block to read the correct `target_types` from the channel for this specific role.
5. **Customize the Prompt Building**: Inject the fetched context, `ROLE.md`, and any role-specific Epic vs. Task instructions into the `$PROMPT`.
6. **Make Executable**: Run `chmod +x .agents/.cache/roles/<role-name>/run.sh`.

### 3. Update the Orchestrator's Implementation (loop.sh)
Modify `.agents/roles/manager/loop.sh` so the Manager knows WHEN to spawn this new `run.sh`:
1. **Status Checks**: Add the new state to the `active_count()` helper if it counts toward the active room limit.
2. **State Handlers**: Add a new case in the `case "$STATUS" in` block. When the status is `<new-state>`, spawn `.agents/.cache/roles/<role-name>/run.sh`.
3. **Transition Logic**: Update the message parsing logic that transitions war-room statuses. (e.g., if the new agent emits `pass`, transition to `passed`).

### 4. Update the Orchestrator's Prompt (ROLE.md)
Modify `.agents/roles/manager/ROLE.md` to document the new loop cycle:
1. Update the **State Machine** ASCII diagram to include the new step (e.g., `engineering → qa-review → security-review`).
2. Update the **Communication Protocol** list to define what triggers the new state.

### 5. Validate the Integration
- Check bash syntax: `bash -n .agents/.cache/roles/<role-name>/run.sh` and `bash -n .agents/roles/manager/loop.sh`.
- Ensure the newly spawned process will be captured properly by the Manager's `cleanup()` trap.
ger's `cleanup()` trap.
