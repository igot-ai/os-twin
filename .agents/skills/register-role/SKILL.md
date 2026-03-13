---
name: register-role
description: Use this skill to autonomously design and define the prompt, identity, and responsibilities for a new agent role in the OS-Twin multi-agent platform.
---

# register-role

## Overview

Use this skill when the Manager reasons and requests a new specialized agent role (e.g., Designer, Data Analyst, Security Auditor) to handle specific tasks. 
A complete role definition starts with a highly structured prompt (`ROLE.md`) defining its persona, responsibilities, and expected JSONL communication format.

**CRITICAL**: This skill ONLY defines the `ROLE.md`. Once the role definition is complete, you MUST use the `register-run-bash` skill to create the bash execution wrapper (`run.sh`) so the agent can actually be spawned and used in the war-room.

## Instructions

### 1. Analyze the Context
Before generating a new role, you MUST understand what tasks the Manager wants this agent to handle.
- Read an existing role (e.g., `.agents/roles/engineer/ROLE.md` or `.agents/roles/qa/ROLE.md`) for prompting inspiration.
- Identify what JSONL message types the new role will ingest (e.g., `task`, `done`, `review`) and emit (e.g., `pass`, `fail`, `done`, `report`).

### 2. Create the Role Directory
1. Create a new directory for the role: `mkdir -p .agents/roles/<role-name>`

### 3. Draft the ROLE.md
Create `.agents/roles/<role-name>/ROLE.md`. This is the core LLM system prompt for the role. It MUST include:
- **Role Title & Context**: `# Role: [Name]`. Describe the persona and objective.
- **Responsibilities**: A numbered list of core duties.
- **Workflows (Epic vs. Task)**: Step-by-step instructions on how to handle assignments. Explain exactly how to use the filesystem and tools.
- **Output / Communication Format**: Specify exactly what MCP tools to use (e.g., `post_message()`) and the JSONL channel message structure to emit when finished.
- **Quality Gates**: A checklist of requirements the agent must fulfill before declaring work complete.

### 4. Proceed to Execution Wrapper
Once `.agents/.cache/roles/<role-name>/ROLE.md` is written and verified:
- You MUST immediately use the `register-run-bash` skill to create the `.agents/.cache/roles/<role-name>/run.sh` script and integrate the new agent into the Manager's `loop.sh` state machine.
anager's `loop.sh` state machine.
.sh` state machine.
