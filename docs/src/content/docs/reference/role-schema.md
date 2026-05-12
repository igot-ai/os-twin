---
title: Role Schema
description: Reference for role.json, ROLE.md, and the role registry.
sidebar:
  order: 4
---

Roles define the agent personas that work inside war-rooms. Each role is a directory under `.agents/roles/` containing a `role.json` definition and an optional `ROLE.md` prompt.

## Directory Structure

```
.agents/roles/
├── engineer/
│   ├── role.json
│   ├── ROLE.md
│   └── Start-Engineer.ps1
├── qa/
│   ├── role.json
│   ├── ROLE.md
│   └── Start-QA.ps1
├── manager/
│   ├── role.json
│   ├── ROLE.md
│   └── Start-ManagerLoop.ps1
├── _base/
│   └── Start-DynamicRole.ps1
└── registry.json
```

## role.json Schema

```json
{
  "name": "engineer",
  "description": "Software engineer — implements features, writes tests, fixes bugs",
  "capabilities": [
    "code-generation",
    "file-editing",
    "shell-execution",
    "testing",
    "refactoring"
  ],
  "prompt_file": "ROLE.md",
  "quality_gates": [
    "unit-tests",
    "lint-clean",
    "no-hardcoded-secrets"
  ],
  "skill_refs": [],
  "cli": "agent",
  "model": "google-vertex-anthropic/claude-opus-4-6@default",
  "timeout": 900
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Unique role identifier (lowercase, hyphenated) |
| `description` | `string` | Yes | Human-readable role description |
| `capabilities` | `string[]` | Yes | List of capability tags for matching |
| `prompt_file` | `string` | No | Path to the prompt file (default: `ROLE.md`) |
| `quality_gates` | `string[]` | No | Gates that must pass before `done` |
| `skill_refs` | `string[]` | No | Default skills injected into this role |
| `cli` | `string` | No | CLI tool name (default: `"agent"`) |
| `model` | `string` | No | Default model for this role |
| `timeout` | `int` | No | Default timeout in seconds |

## Capabilities

Capabilities are freeform tags used by the capability matching system. The registry defines aliases that normalize common variations:

```json
{
  "capability_aliases": {
    "db": "database",
    "sql": "database",
    "react": "frontend",
    "vue": "frontend",
    "css": "frontend",
    "devops": "infrastructure",
    "ci-cd": "infrastructure"
  }
}
```

When `capability_matching` is enabled in config, the manager scores candidate roles against epic requirements using these tags.

## ROLE.md Prompt

The `ROLE.md` file contains the system prompt injected into the agent. It defines:

- Role identity and responsibilities
- Communication protocol
- Tool usage guidelines
- Quality standards
- Output format requirements

This file supports standard markdown. It is read verbatim and injected as the system context for the agent.

## registry.json

The registry catalogs all available roles. It is located at `.agents/roles/registry.json`.

### Role Entry Schema

```json
{
  "name": "engineer",
  "description": "Software engineer — implements features",
  "runner": "roles/engineer/Start-Engineer.ps1",
  "runner_legacy": "roles/engineer/run.sh",
  "definition": "roles/engineer/role.json",
  "prompt": "roles/engineer/ROLE.md",
  "default_assignment": true,
  "instance_support": true,
  "supported_task_types": ["task", "epic"],
  "capabilities": ["code-generation", "file-editing"],
  "quality_gates": ["unit-tests", "lint-clean"],
  "default_model": "google-vertex-anthropic/claude-opus-4-6@default"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `runner` | `string` | PowerShell script to start this role |
| `runner_legacy` | `string` | Bash fallback script |
| `default_assignment` | `bool` | Whether this is the default role for unmatched tasks |
| `instance_support` | `bool` | Whether named instances are allowed |
| `supported_task_types` | `string[]` | Task types this role can handle |
| `platform` | `string[]` | Platform restrictions (e.g., `["macos"]`) |

### Assignment Rules

```json
{
  "assignment_rules": {
    "default_role": "engineer",
    "review_role": "qa",
    "design_role": "architect",
    "orchestration_role": "manager",
    "audit_role": "audit"
  }
}
```

## Model Resolution Order

1. War-room `config.json` override
2. `.agents/config.json` role section `default_model`
3. `role.json` `model` field
4. `registry.json` `default_model`
5. Manager's `default_model` as ultimate fallback

## Dynamic Roles

Roles without a dedicated PowerShell runner use `_base/Start-DynamicRole.ps1`. These are created at runtime by the `auto_create_role.sh` script or the `create-role` skill.

```json
{
  "name": "database-architect",
  "runner": "roles/_base/Start-DynamicRole.ps1",
  "definition": "roles/database-architect/role.json"
}
```

## Community Roles

Community-contributed roles live under `contributes/roles/` and follow the same schema. They are registered in `registry.json` with paths prefixed by `contributes/`:

```json
{
  "name": "game-engineer",
  "definition": "contributes/roles/game-engineer/role.json"
}
```

:::note
Role names must be unique across both built-in and community registrations. Duplicate names cause a startup error.
:::

:::tip
Use `ostwin skills search` to find skills that complement a role's capabilities.
:::
