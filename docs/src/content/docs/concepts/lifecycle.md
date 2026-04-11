---
title: "Epic Lifecycle"
description: "The 14-state machine that governs every epic from planning through completion, with retry logic and timeout enforcement."
sidebar:
  order: 7
---

Every epic in OSTwin follows a deterministic state machine. The lifecycle defines which states are valid, what transitions are allowed, and what happens when things go wrong. This ensures that no epic gets stuck in an undefined state and every failure is handled systematically.

## State Diagram

```
                    ┌─────────────┐
                    │  planning   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   planned   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   ready     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────│ developing  │◄────────────┐
              │     └──────┬──────┘              │
              │            │                     │
              │     ┌──────▼──────┐              │
              │     │   review    │              │
              │     └──────┬──────┘              │
              │            │                     │
              │      ┌─────┴─────┐               │
              │      │           │               │
              │ ┌────▼───┐ ┌────▼────┐           │
              │ │ passed │ │ failed  ├───────────┘
              │ └────────┘ └────┬────┘   (retry)
              │                 │
              │          ┌──────▼──────┐
              │          │fixing       │──► review
              │          └─────────────┘
              │
              │     ┌──────────────┐
              └────►│   blocked    │
                    └──────┬───────┘
                           │
                    ┌──────▼──────┐
                    │failed-final │
                    └─────────────┘
```

## All 14 States

| State | Terminal | Description |
|-------|----------|-------------|
| `planning` | No | Epic is being decomposed into tasks by the manager |
| `planned` | No | Tasks are defined, waiting for dependency gates to clear |
| `ready` | No | All dependencies satisfied, room can be created |
| `developing` | No | Engineer is actively implementing tasks |
| `review` | No | QA is reviewing the engineer's deliverables |
| `fixing` | No | Engineer is addressing QA feedback |
| `passed` | Yes | QA approved, all acceptance criteria met |
| `failed` | No | QA rejected, retry is possible |
| `failed-final` | Yes | Max retries exhausted, escalation required |
| `blocked` | No | Waiting on external dependency or human input |
| `timeout` | No | Execution exceeded the configured time limit |
| `escalated` | No | Sent to architect for design review |
| `redesign` | No | Architect determined a design change is needed |
| `cancelled` | Yes | Manually cancelled by the manager or user |

:::note[Terminal States]
Only three states are terminal: `passed`, `failed-final`, and `cancelled`. The manager agent is the only role authorized to set terminal states. Regular agents can transition between non-terminal states.
:::

## Transition Mechanisms

State transitions are triggered by four mechanisms:

### 1. Agent Messages

The most common trigger. When an agent posts a `done` message, the room transitions from `developing` to `review`. When QA posts `pass`, it transitions to `passed`.

```jsonl
{"type":"done","from":"engineer"} → developing → review
{"type":"pass","from":"qa"}      → review → passed
{"type":"fail","from":"qa"}      → review → failed
```

### 2. Manager Orchestration

The manager controls lifecycle states that require cross-room awareness:

- `planning` -> `planned` (after task decomposition)
- `planned` -> `ready` (after dependency check)
- `failed` -> `developing` (after retry decision)
- `failed` -> `failed-final` (after max retries)

### 3. Timeout Enforcement

The system monitors execution time and forces transitions when limits are exceeded:

- `developing` for > `timeout_seconds` -> `timeout`
- `timeout` -> `escalated` (automatic)

### 4. Manual Override

Users can force state transitions through the dashboard or CLI:

```powershell
Set-RoomStatus -RoomDir ".agents/war-rooms/room-042" -Status "cancelled"
```

## lifecycle.json Format

Each war-room contains a `lifecycle.json` that defines its state machine:

```json
{
  "states": [
    "planning", "planned", "ready", "developing",
    "review", "fixing", "passed", "failed",
    "failed-final", "blocked", "timeout",
    "escalated", "redesign", "cancelled"
  ],
  "initial": "planning",
  "terminal": ["passed", "failed-final", "cancelled"],
  "transitions": {
    "planning":   ["planned", "cancelled"],
    "planned":    ["ready", "blocked", "cancelled"],
    "ready":      ["developing", "blocked", "cancelled"],
    "developing": ["review", "blocked", "timeout", "cancelled"],
    "review":     ["passed", "failed", "blocked", "cancelled"],
    "failed":     ["fixing", "failed-final", "escalated"],
    "fixing":     ["review", "blocked", "timeout"],
    "timeout":    ["escalated", "developing", "cancelled"],
    "escalated":  ["redesign", "developing", "failed-final"],
    "redesign":   ["developing", "cancelled"],
    "blocked":    ["developing", "cancelled"]
  },
  "manager_only": ["passed", "failed-final", "cancelled"]
}
```

:::caution[Transition Validation]
Every status update is validated against `lifecycle.json`. If an agent attempts an invalid transition (e.g., `planning` -> `passed`), the update is rejected and an error is logged. This prevents agents from bypassing the quality gates.
:::

## Retry Logic

Failed epics are retried up to a configurable maximum:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 3 | Maximum QA rejection cycles |
| `timeout_seconds` | 900 | Max execution time per attempt (15 minutes) |
| `retry_delay_seconds` | 0 | Delay between retry attempts |

### Escalation Flow

```
Attempt 1: develop → review → FAIL
Attempt 2: fix → review → FAIL
Attempt 3: fix → review → FAIL
  │
  ▼
failed-final → manager notified → architect escalation
  │
  ├─► FIX verdict: architect provides guidance, retry
  ├─► REDESIGN verdict: epic restructured, restart
  └─► REPLAN verdict: plan modified, DAG rebuilt
```

After the architect reviews, the manager receives one of three verdicts:

- **FIX** -- the implementation approach is sound, provide specific guidance
- **REDESIGN** -- the epic's architecture needs changes before retry
- **REPLAN** -- the epic should be split, merged, or removed from the plan

## Timeout Enforcement

The system tracks elapsed time for each non-terminal state:

```
Room entered "developing" at 2025-01-15T10:00:00Z
Timeout configured: 900 seconds
Current time:        2025-01-15T10:16:00Z
Elapsed:             960 seconds → TIMEOUT triggered
```

When a timeout fires:

1. Room status transitions to `timeout`
2. The manager is notified via the channel
3. The manager decides whether to retry, escalate, or cancel
4. If no action is taken within 300 seconds, auto-escalation occurs

## Audit Trail

Every state transition is logged to `lifecycle-audit.jsonl` in the war-room:

```jsonl
{"ts":"2025-01-15T10:00:00Z","from":"planning","to":"planned","actor":"manager","reason":"Tasks decomposed"}
{"ts":"2025-01-15T10:00:05Z","from":"planned","to":"ready","actor":"system","reason":"Dependencies satisfied"}
{"ts":"2025-01-15T10:00:10Z","from":"ready","to":"developing","actor":"manager","reason":"Engineer assigned"}
{"ts":"2025-01-15T10:15:00Z","from":"developing","to":"review","actor":"engineer","reason":"TASK-001 done"}
{"ts":"2025-01-15T10:20:00Z","from":"review","to":"failed","actor":"qa","reason":"Test coverage 72%, required 95%"}
{"ts":"2025-01-15T10:20:05Z","from":"failed","to":"fixing","actor":"manager","reason":"Retry 1/3"}
```

This creates a complete, timestamped record of every lifecycle event for debugging and compliance.

## Progress Tracking

Agents report progress through two complementary mechanisms:

### progress.json

Machine-readable progress updated by agents via the `report_progress` MCP tool:

```json
{
  "percent": 65,
  "message": "Implementing TASK-003 of 5. Tests passing for TASK-001 and TASK-002.",
  "updated_at": "2025-01-15T10:12:00Z"
}
```

The `percent` field is clamped to 0-100 and drives the dashboard progress bars.

### PROGRESS.md

Human-readable progress notes maintained by the engineer:

```markdown
## Progress

- [x] TASK-001: Login endpoint (done, tests passing)
- [x] TASK-002: Token validation (done, tests passing)
- [ ] TASK-003: Rate limiting (in progress)
- [ ] TASK-004: Integration tests
- [ ] TASK-005: OpenAPI docs
```

:::tip[Dashboard Integration]
The FastAPI dashboard polls `progress.json` from all active war-rooms and streams updates to the Next.js frontend via SSE. This gives the user real-time visibility into every epic's progress without inspecting files manually.
:::

## Lifecycle Generation

The lifecycle can be customized per plan or per epic:

| Script | Purpose |
|--------|---------|
| `engine/New-Lifecycle.ps1` | Generate default lifecycle.json |
| `create-lifecycle` skill | Custom lifecycle from epic requirements |
| `engine/Validate-Transition.ps1` | Check if a transition is valid |

The `create-lifecycle` skill can generate specialized lifecycles for different epic types -- for example, a "documentation" lifecycle might skip the QA review step entirely.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/war-rooms/*/lifecycle.json` | Per-room state machine |
| `.agents/war-rooms/*/status.txt` | Current state |
| `.agents/war-rooms/*/progress.json` | Completion tracking |
| `engine/Set-RoomStatus.ps1` | Status transition with validation |
| `engine/Watch-Timeouts.ps1` | Timeout enforcement loop |
| `mcp_servers/warroom/` | Status and progress MCP tools |
