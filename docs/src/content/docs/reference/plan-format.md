---
title: Plan Format
description: Specification for PLAN.md files that drive OSTwin execution.
sidebar:
  order: 3
---

A `PLAN.md` file is the input document that tells OSTwin what to build. It follows a strict markdown structure that the manager parses into a DAG of epics.

## Document Structure

Every plan has three sections: **Config**, **Goal**, and **Epics**.

```markdown
# Plan Title

## Config
- max_concurrent_rooms: 8
- model: google-vertex-anthropic/claude-opus-4-6@default

## Goal
Build a mobile puzzle game with 100 levels...

## Epics

### EPIC-001: Grid System
Roles: game-engineer, game-qa
depends_on: [PLAN-REVIEW]

Description of the epic...

### EPIC-002: Snake Rendering
Roles: game-engineer, game-qa
depends_on: [EPIC-001]

Description of the epic...
```

## Config Section

The `## Config` block sets plan-level overrides. All fields are optional.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_concurrent_rooms` | `int` | from config.json | Override concurrency limit |
| `model` | `string` | from config.json | Default model for all roles |
| `timeout` | `int` | `2400` | Global timeout in seconds |
| `auto_expand` | `bool` | `false` | Auto-generate tasks from epic descriptions |

## Goal Section

The `## Goal` block is a free-text description of the project objective. The architect uses this during `PLAN-REVIEW` to validate the plan structure.

## Epic Format

Each epic is an `### EPIC-NNN: Title` heading followed by structured content.

### Required Fields

| Field | Format | Description |
|-------|--------|-------------|
| `Roles` | Comma-separated list | Roles involved in this epic |
| `depends_on` | `[REF, REF]` | Dependency references |

### Optional Fields

| Field | Format | Description |
|-------|--------|-------------|
| `Objective` | Free text | One-line summary |
| `Description` | Free text | Detailed description |
| `Key files` | Comma-separated | Files this epic will create or modify |
| `Lifecycle` | Code block | Custom lifecycle diagram |

### Epic Directives

Directives are inline annotations that control behavior:

```markdown
### EPIC-003: Camera System
Roles: game-engineer
depends_on: [EPIC-001]
priority: high
timeout: 1800

Camera framing and zoom logic...
```

| Directive | Type | Description |
|-----------|------|-------------|
| `priority` | `high\|normal\|low` | Affects scheduling order within a wave |
| `timeout` | `int` | Per-epic timeout override |
| `skip_review` | `bool` | Skip QA review (not recommended) |
| `working_dir` | `string` | Override working directory |

## Dependency Syntax

Dependencies use bracket notation referencing other epic IDs or the special `PLAN-REVIEW` sentinel:

```markdown
depends_on: [PLAN-REVIEW]           # depends on architecture review
depends_on: [EPIC-001]              # depends on one epic
depends_on: [EPIC-001, EPIC-003]    # depends on multiple epics
```

The `PLAN-REVIEW` node is always `room-000` and runs the architect role before any epics begin.

## Task Blocks

Epics can contain inline task definitions:

```markdown
### Tasks
- [ ] TASK-001 — [game-engineer] **Grid rendering.** Description... | requires: none | unlocks: TASK-002
- [ ] TASK-002 — [game-engineer] **Coordinate mapping.** Description... | requires: TASK-001 | unlocks: TASK-003
```

Task format: `TASK-NNN — [role] **Title.** Description | requires: REF | unlocks: REF`

## Definition of Done

Each epic can include acceptance criteria:

```markdown
### Definition of Done
- [ ] Grid renders dots for all positions
- [ ] Board size is validated to 3x3 - 40x40
- [ ] Unit tests pass
```

## Sidecar Files

Plans can reference sidecar files for large content:

| Sidecar | Purpose |
|---------|---------|
| `PLAN-assets/` | Images, diagrams referenced by the plan |
| `PLAN-config.json` | Machine-readable config overrides |
| `PLAN-context.md` | Additional context for the architect |

## PLAN-REVIEW

Every plan implicitly creates a `PLAN-REVIEW` node assigned to `room-000`. This node:

1. Runs the architect role
2. Validates epic structure and dependencies
3. Checks for circular dependencies
4. Verifies role availability
5. Produces the initial DAG

All epics depend on `PLAN-REVIEW` either directly or transitively.

:::tip
Keep epic descriptions focused on *what* and *why*. The engineer role decides *how* during implementation.
:::

:::note
The parser is line-oriented. Do not nest epics or use heading levels below `###` for epic titles.
:::
