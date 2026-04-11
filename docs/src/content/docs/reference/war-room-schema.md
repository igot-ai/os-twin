---
title: War Room Schema
description: Full schema for war-room config.json and the files that make up a room directory.
sidebar:
  order: 6
---

A war-room is an isolated execution environment for a single epic or task. Each room is a directory under `.agents/war-rooms/` containing structured files that track state, communication, and artifacts.

## Directory Layout

```
.agents/war-rooms/room-001/
├── config.json          # Room configuration
├── lifecycle.json       # State machine definition
├── brief.md             # Assignment description
├── channel.jsonl        # Communication log
├── status               # Current state (single line)
├── state_changed_at     # ISO timestamp of last transition
├── retries              # Current retry count (integer)
├── task-ref             # Task reference (e.g., EPIC-001)
├── audit.log            # Audit trail
├── progress.json        # Progress snapshot
├── TASKS.md             # Sub-task checklist
├── artifacts/           # Output files
│   └── ...
├── skills/              # Room-local skill overrides
│   └── ...
└── memory/              # Room-local memory entries
    └── ...
```

## config.json Schema

```json
{
  "room_id": "room-001",
  "task_ref": "EPIC-001",
  "plan_id": "bc0a7c93bcbf",
  "depends_on": ["PLAN-REVIEW"],
  "created_at": "2026-04-03T11:04:01Z",
  "working_dir": "/path/to/project",
  "assignment": {
    "title": "Build the grid system",
    "description": "Full epic description...",
    "assigned_role": "game-engineer",
    "candidate_roles": ["game-engineer", "game-qa"],
    "type": "epic"
  },
  "goals": {
    "definition_of_done": [],
    "acceptance_criteria": [],
    "quality_requirements": {
      "test_coverage_min": 80,
      "lint_clean": true,
      "security_scan_pass": true
    }
  },
  "constraints": {
    "max_retries": 3,
    "timeout_seconds": 900,
    "budget_tokens_max": 500000
  },
  "status": {
    "current": "developing",
    "retries": 0,
    "started_at": "2026-04-03T11:04:01Z",
    "last_state_change": "2026-04-03T11:04:01Z"
  },
  "skill_refs": [
    "detect-ui",
    "unity-dev-principles",
    "create-lifecycle"
  ]
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `room_id` | `string` | Unique room identifier (`room-NNN`) |
| `task_ref` | `string` | Epic or task reference (`EPIC-NNN`) |
| `plan_id` | `string` | Hash linking to the source plan |
| `depends_on` | `string[]` | Task refs this room depends on |
| `created_at` | `string` | ISO 8601 creation timestamp |
| `working_dir` | `string` | Absolute path to working directory |

### Assignment Block

| Field | Type | Description |
|-------|------|-------------|
| `title` | `string` | Short assignment title |
| `description` | `string` | Full assignment description |
| `assigned_role` | `string` | Primary role for this room |
| `candidate_roles` | `string[]` | All roles involved in the lifecycle |
| `type` | `string` | `"epic"`, `"task"`, or `"review"` |

### Goals Block

| Field | Type | Description |
|-------|------|-------------|
| `definition_of_done` | `string[]` | Checklist items for completion |
| `acceptance_criteria` | `string[]` | Testable acceptance criteria |
| `quality_requirements` | `object` | Minimum quality thresholds |

### Constraints Block

| Field | Type | Description |
|-------|------|-------------|
| `max_retries` | `int` | Max retries before `failed-final` |
| `timeout_seconds` | `int` | Max time for any single agent run |
| `budget_tokens_max` | `int` | Token budget cap |

### Status Block

| Field | Type | Description |
|-------|------|-------------|
| `current` | `string` | Current lifecycle state |
| `retries` | `int` | Number of retries consumed |
| `started_at` | `string` | When work began |
| `last_state_change` | `string` | Last state transition timestamp |

## File-Level State

Some state is stored as plain files for easy shell access:

| File | Content | Example |
|------|---------|---------|
| `status` | Current state name | `developing` |
| `state_changed_at` | ISO timestamp | `2026-04-03T11:04:01Z` |
| `retries` | Integer count | `1` |
| `task-ref` | Task reference | `EPIC-001` |

## brief.md

Contains the assignment description in markdown. This is injected into the agent's prompt as the task context. It is generated from the plan's epic description.

## progress.json

Written by agents to report progress:

```json
{
  "percent": 75,
  "message": "Implemented 3 of 4 tasks",
  "updated_at": "2026-04-03T11:19:34Z"
}
```

## TASKS.md

A checklist of sub-tasks within the epic:

```markdown
- [x] TASK-001 — Grid dot rendering
- [x] TASK-002 — Coordinate mapping
- [ ] TASK-003 — Content rect calculation
```

## audit.log

Append-only log of all state transitions, agent invocations, and system events. Used for debugging and compliance.

:::tip
Use `ostwin status --room room-001` to quickly inspect room state without reading files directly.
:::

:::note
Room directories are never deleted during execution. Use `uninstall.sh --purge` to clean up after a completed plan.
:::
