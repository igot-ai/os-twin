---
title: Lifecycle States
description: All lifecycle states, transitions, lifecycle.json schema, retry mechanics, and escalation.
sidebar:
  order: 8
---

Every war-room follows a state machine defined in `lifecycle.json`. This document covers all standard states, transitions, retry logic, and escalation paths.

## State Overview

OSTwin defines 14 states across 4 categories:

### Work States

| State | Role | Description |
|-------|------|-------------|
| `pending` | — | Room created, waiting for dependencies |
| `developing` | engineer | Primary implementation work |
| `optimize` | engineer | Fix/improve after QA feedback |

### Review States

| State | Role | Description |
|-------|------|-------------|
| `review` | qa | Code review and acceptance testing |
| `design-review` | architect | Architecture compliance review |

### Decision States

| State | Role | Description |
|-------|------|-------------|
| `triage` | manager | Decide next action after escalation |
| `failed` | manager | Auto-decision: retry or exhaust |

### Terminal States

| State | Type | Description |
|-------|------|-------------|
| `passed` | terminal | Epic completed and approved |
| `failed-final` | terminal | Epic exhausted retries or rejected |

### Orchestration States

| State | Role | Description |
|-------|------|-------------|
| `blocked` | — | Waiting on dependency resolution |
| `waiting` | — | Paused for external input |
| `plan-review` | architect | Initial plan validation |
| `signing-off` | manager | Collecting release signoffs |
| `released` | — | Release completed |

## lifecycle.json Schema

```json
{
  "version": 2,
  "initial_state": "developing",
  "max_retries": 3,
  "states": {
    "developing": {
      "role": "engineer",
      "type": "work",
      "signals": {
        "done": { "target": "review" },
        "error": {
          "target": "failed",
          "actions": ["increment_retries"]
        }
      }
    }
  }
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | `int` | Schema version (currently `2`) |
| `initial_state` | `string` | State when room first activates |
| `max_retries` | `int` | Maximum retries before exhaustion |

### State Definition

| Field | Type | Description |
|-------|------|-------------|
| `role` | `string` | Role responsible in this state |
| `type` | `string` | `"work"`, `"review"`, `"triage"`, `"decision"`, or `"terminal"` |
| `auto_transition` | `bool` | Auto-transition without agent invocation |
| `signals` | `object` | Signal-to-transition mapping |

### Signal Definition

| Field | Type | Description |
|-------|------|-------------|
| `target` | `string` | Target state name |
| `guard` | `string` | Condition expression (e.g., `"retries < max_retries"`) |
| `actions` | `string[]` | Actions to execute on transition |

## Standard Lifecycle Flow

```
pending → developing → review ─┬─► passed
              ▲                 │
              └── optimize ◄────┘ (on fail)
                    │
                    ▼
                  failed ──► failed-final (if retries exhausted)
                    │
                    └──► developing (if retries remain)
```

## Transition Signals

| Signal | Meaning | Typical Source |
|--------|---------|----------------|
| `done` | Work completed | engineer, architect |
| `pass` | Review approved | qa |
| `fail` | Review rejected | qa |
| `error` | Unrecoverable error | any role |
| `escalate` | Needs higher authority | qa |
| `fix` | Fix and retry | manager |
| `redesign` | Fundamental rework needed | manager |
| `reject` | Permanently reject | manager |
| `retry` | Auto-retry (guarded) | manager |
| `exhaust` | Retries exhausted (guarded) | manager |

## Retry Mechanics

### Increment

The `increment_retries` action increments the room's retry counter. This happens on `error` and `fail` signals.

### Guard Conditions

The `failed` state uses guard conditions for automatic routing:

```json
{
  "failed": {
    "auto_transition": true,
    "signals": {
      "retry": {
        "target": "developing",
        "guard": "retries < max_retries"
      },
      "exhaust": {
        "target": "failed-final",
        "guard": "retries >= max_retries"
      }
    }
  }
}
```

The `auto_transition: true` flag means the manager evaluates guards automatically without spawning an agent.

### Retry Flow

1. QA sends `fail` signal → state moves to `optimize`
2. Engineer fixes → sends `done` → state moves to `review`
3. If QA fails again → `optimize` with `increment_retries`
4. After `max_retries` failures → `failed` → auto-evaluates → `failed-final`

## Escalation

The `escalate` signal from QA triggers the `triage` state:

```json
{
  "triage": {
    "role": "manager",
    "type": "triage",
    "signals": {
      "fix": { "target": "optimize", "actions": ["increment_retries"] },
      "redesign": { "target": "developing", "actions": ["increment_retries", "revise_brief"] },
      "reject": { "target": "failed-final" }
    }
  }
}
```

The manager decides between:
- **fix** — Send back for optimization
- **redesign** — Restart with a revised brief
- **reject** — Permanently fail this epic

## Actions

| Action | Description |
|--------|-------------|
| `increment_retries` | Increment the retry counter |
| `post_fix` | Post a fix message to the channel |
| `revise_brief` | Update the room's brief.md |

## Terminal States

Terminal states have no signals and no role. Once entered, the room is complete:

```json
{
  "passed": { "type": "terminal" },
  "failed-final": { "type": "terminal" }
}
```

:::caution
Only the manager can set terminal states (`passed`, `failed-final`). Agent roles must not write these directly to the status file.
:::

:::note
Custom lifecycles can define additional states. The only requirement is at least one terminal state and a valid `initial_state`.
:::
