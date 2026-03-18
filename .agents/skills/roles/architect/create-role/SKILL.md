---
name: create-role
description: Use this skill to scaffold a new agent role — generates role.json, ROLE.md, and registers the role in registry.json.
tags: [architect, manager, scaffolding]
trust_level: core
---

# create-role

## Overview

This skill walks you through creating a new agent role for the Ostwin war-room system. A role defines **who** the agent is, what it can do, and the prompt that shapes its behaviour.

## Install Location

All roles live under `~/.ostwin/roles/`. This is the global Ostwin runtime directory.

> **Important:** Always create new roles in `~/.ostwin/roles/<role-name>/` and register them in `~/.ostwin/roles/registry.json`.

## Role Anatomy

Every role folder contains:

| File | Required | Purpose |
|------|----------|---------|
| `role.json` | ✅ | Machine-readable definition (capabilities, skills, model, timeout) |
| `ROLE.md` | ✅ | System prompt — the agent reads this to understand its mission |
| `Start-<Role>.ps1` | Optional | PowerShell runner script for orchestration |

The role must also be registered in `~/.ostwin/roles/registry.json`.

## Instructions

### 1. Choose a Role Name

Pick a short, lowercase, hyphenated name that describes the specialist:

```
Examples: security-auditor, database-architect, performance-engineer,
          technical-writer, data-pipeline-engineer, devops-engineer
```

### 2. Create `role.json`

Create `~/.ostwin/roles/<role-name>/role.json` using this template:

```json
{
  "name": "<role-name>",
  "description": "<one-line description of the role>",
  "capabilities": [
    "<capability-1>",
    "<capability-2>"
  ],
  "prompt_file": "ROLE.md",
  "quality_gates": [
    "<gate-1>",
    "<gate-2>"
  ],
  "skills": [
    "<skill-1>",
    "<skill-2>"
  ],
  "cli": "deepagents",
  "model": "gemini-3-flash-preview",
  "timeout": 600
}
```

**Field guide:**

| Field | Description |
|-------|-------------|
| `name` | Must match the folder name |
| `description` | One line — shown in logs and the registry |
| `capabilities` | What the agent *can do* (e.g. `code-generation`, `security-review`, `documentation`) |
| `quality_gates` | Checks that must pass before work is accepted (e.g. `unit-tests`, `lint-clean`) |
| `skills` | Technologies / domains the agent is proficient in |
| `model` | LLM model to use. Use `gemini-3-flash-preview` for speed, `gemini-3.1-pro-preview` for complex reasoning |
| `timeout` | Max seconds the agent can run per invocation (default: 600) |

### 3. Create `ROLE.md`

Create `~/.ostwin/roles/<role-name>/ROLE.md` using this template:

```markdown
# <Role Display Name>

You are a <role description> working within a team of AI agents.

## Your Responsibilities

1. **<Responsibility 1>** — <brief explanation>
2. **<Responsibility 2>** — <brief explanation>
3. **<Responsibility 3>** — <brief explanation>

## Guidelines

- <Guideline 1>
- <Guideline 2>
- <Guideline 3>

## Output Format

When delivering work:
1. Summary of changes made
2. Files modified/created
3. How to test the changes

When reviewing:
1. <Review criterion 1>
2. <Review criterion 2>
3. Suggested improvements

## Quality Standards

- Code must compile/parse without errors
- Include inline comments for non-obvious logic
- Follow existing project conventions and patterns
- Handle edge cases mentioned in the task description
```

### 4. Register in `registry.json`

Add an entry to the `roles` array in `~/.ostwin/roles/registry.json`:

```json
{
  "name": "<role-name>",
  "description": "<same description as role.json>",
  "runner": "roles/<role-name>/Start-<RolePascalCase>.ps1",
  "definition": "roles/<role-name>/role.json",
  "prompt": "roles/<role-name>/ROLE.md",
  "default_assignment": false,
  "supported_task_types": ["task", "epic"],
  "capabilities": ["<cap-1>", "<cap-2>"],
  "quality_gates": ["<gate-1>", "<gate-2>"],
  "default_model": "gemini-3-flash-preview"
}
```

### 5. (Optional) Scaffold a Runner Script

If the role needs custom orchestration logic, create `Start-<RolePascalCase>.ps1`. For most roles, the base runner at `.agents/roles/_base/Invoke-Agent.ps1` is sufficient and no custom script is needed.

## Verification

After creating the role, verify:

1. `role.json` is valid JSON — run: `cat ~/.ostwin/roles/<role-name>/role.json | python3 -m json.tool`
2. `ROLE.md` exists and has a top-level `#` heading
3. `~/.ostwin/roles/registry.json` is still valid JSON after your edit
4. The role folder appears under `~/.ostwin/roles/`
