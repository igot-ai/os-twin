---
title: "Pillar 1: The Zero-Agent Pattern"
description: "Adding a new role requires zero lines of code. Roles are config directories, not compiled agents."
sidebar:
  order: 1
  badge:
    text: Pillar
    variant: tip
---

OSTwin's first architectural pillar inverts the traditional approach to AI agents. Instead of coding each agent as a separate program, every role in the system is a **configuration directory** executed by a single, universal runner.

> "Adding a new role requires zero lines of code."

## Universal Agent Runner

The entire system runs through one script: **`Invoke-Agent.ps1`**. This PowerShell function accepts a role name, a war-room path, and a task reference, then assembles everything the agent needs at invocation time.

```powershell
Invoke-Agent -Role "engineer" -RoomDir ".agents/war-rooms/room-042" -Ref "TASK-003"
```

The runner handles:

- Loading the role's identity prompt from `ROLE.md`
- Resolving skills, MCP servers, and model preferences
- Injecting war-room context (brief, channel history, memory)
- Launching the underlying LLM session with the assembled prompt

Because every role flows through the same runner, improvements to `Invoke-Agent.ps1` benefit **all roles simultaneously**.

## Role as a Config Directory

Each role is a directory under `.agents/roles/` containing exactly two files:

```
.agents/roles/engineer/
  role.json       # Machine-readable config
  ROLE.md         # Identity prompt (personality + constraints)
```

No Python class. No TypeScript module. No compilation step. The role **is** its directory.

### role.json Schema

The `role.json` file declares everything the runner needs to configure the agent session.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Role identifier (e.g. `"engineer"`) |
| `display_name` | `string` | Human-readable label |
| `description` | `string` | One-line purpose statement |
| `model` | `string` | Preferred model ID (e.g. `"claude-sonnet-4-20250514"`) |
| `provider` | `string` | LLM provider (`"anthropic"`, `"openai"`, `"vertex"`) |
| `no_mcp` | `bool` | If `true`, launch without MCP servers (saves tokens) |
| `skill_refs` | `string[]` | Skills this role should always have access to |
| `temperature` | `float` | Sampling temperature override |
| `max_tokens` | `int` | Max output tokens per turn |

### ROLE.md Identity Prompt

The `ROLE.md` file is a markdown document injected as the system prompt. It defines:

- **Who the agent is** -- its expertise, personality, communication style
- **What it must do** -- responsibilities, deliverables, quality standards
- **What it must not do** -- boundaries, anti-patterns, escalation triggers

```markdown
# Engineer

You are a senior software engineer working inside a war-room.
Your job is to implement tasks assigned by the manager, write
production-quality code, and deliver structured done reports.

## Constraints
- Never modify files outside your war-room's scope
- Always run tests before reporting done
- Escalate architectural questions to the architect role
```

## 5-Tier Role Discovery

When `Invoke-Agent.ps1` resolves a role, it searches five locations in priority order:

| Priority | Location | Scope |
|----------|----------|-------|
| 1 | `.agents/war-rooms/{room}/roles/{role}/` | Room-local override |
| 2 | `.agents/roles/{role}/` | Project-level role |
| 3 | `~/.agents/roles/{role}/` | User-global role |
| 4 | Built-in defaults | Shipped with OSTwin |
| 5 | Registry lookup | Dynamic resolution |

This means you can override the `engineer` role for a single war-room without affecting any other room.

## Role Registry

The file `registry.json` (~700 lines) catalogs every known role with metadata for discovery and assignment. The manager agent reads this registry when deciding which roles to assign to a war-room.

```json
{
  "engineer": {
    "description": "Implements features, fixes bugs, writes tests",
    "skills": ["implement-epic", "fix-from-qa", "write-tests"],
    "model": "claude-sonnet-4-20250514"
  },
  "qa": {
    "description": "Reviews deliverables, runs test suites, posts verdicts",
    "skills": ["review-epic", "review-task", "build-verify"],
    "model": "claude-sonnet-4-20250514"
  }
}
```

## Model Resolution Priority

The model used for a given agent invocation is resolved through four levels:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | War-room `config.json` override | Room needs GPT-4o for vision tasks |
| 2 | `role.json` preference | Architect prefers Opus for deep reasoning |
| 3 | Plan-level default | Plan specifies Sonnet for cost control |
| 4 | System default | Falls back to `claude-sonnet-4-20250514` |

## Dynamic Role Creation

New roles can be created at runtime by the `create-role` skill:

1. The manager identifies a capability gap (e.g., "we need a database specialist")
2. It invokes the `create-role` skill with a description
3. The skill generates `role.json` + `ROLE.md` in the project's `.agents/roles/` directory
4. The new role is registered in `registry.json`
5. Future war-rooms can immediately assign the new role

No restart. No deployment. No code change.

## Current Roles

OSTwin ships with **8 core roles** and supports **50+ community-contributed roles**:

**Core roles:** `manager`, `engineer`, `qa`, `architect`, `game-engineer`, `game-designer`, `game-qa`, `reporter`

**Community roles include:** `narrative-designer`, `ux-researcher`, `macos-automation-engineer`, `game-ui-analyst`, `game-architect`, `audit`, and many more domain-specific specialists.

## Why This Matters

:::tip[Scalability Without Complexity]
Traditional multi-agent frameworks require you to subclass an `Agent` base, wire up message handlers, register tools, and deploy. OSTwin reduces all of that to two files in a directory. A team of 20 agents has the same operational complexity as a team of 2.
:::

:::note[Composability]
Because roles are pure configuration, they can be mixed, overridden, and versioned independently. A game studio and a web agency can share the same `engineer` runner but use completely different `ROLE.md` prompts.
:::

## Key Source Files

| File | Purpose |
|------|---------|
| `engine/Invoke-Agent.ps1` | Universal agent runner |
| `.agents/roles/*/role.json` | Role configuration |
| `.agents/roles/*/ROLE.md` | Identity prompt |
| `.agents/registry.json` | Role catalog (~700 lines, 20+ roles) |
| `engine/Resolve-Role.ps1` | 5-tier role discovery logic |
| `engine/New-Role.ps1` | Dynamic role scaffolding |
