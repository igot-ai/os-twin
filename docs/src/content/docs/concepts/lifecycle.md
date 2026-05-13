---
title: "Epic Lifecycle"
description: "How the Worker and Evaluator roles drive every epic through a closed-loop lifecycle — from developing to review, with retry, escalation, and triage."
sidebar:
  order: 7
---

Every epic in OSTwin is driven by two fundamental roles: the **Worker** and the **Evaluator**. Their interaction forms a closed loop that ensures quality — the Worker produces, the Evaluator inspects, and the cycle repeats until the work passes or the system escalates. This page explains how those roles interact through the lifecycle states and what happens when the loop can't close on its own.

## The Workshop Analogy

Think of an OSTwin epic as a **craft workshop**:

- The **Worker** is the artisan at the bench — shaping, assembling, and building the deliverable. In different epics the Worker might be an engineer writing code, a researcher gathering findings, or a writer drafting documentation. The role changes, but the function is the same: **produce**.

- The **Evaluator** is the master inspector — examining the work against acceptance criteria, finding defects, and deciding whether it's ready to ship. In different epics the Evaluator might be a QA tester, a security auditor, or an architect reviewing design. The role changes, but the function is the same: **verify**.

In a real workshop, the artisan doesn't self-certify their own work. They hand it to the inspector, who either stamps it **passed** or sends it back with a list of defects. If the artisan can't fix the defects after several attempts, the workshop master steps in for **triage** — deciding whether to provide guidance, restructure the work, or scrap it entirely.

OSTwin follows exactly this pattern. The lifecycle is the protocol that governs every handoff between Worker and Evaluator.

## Core State Flow

The essential loop every epic follows:

```
  Worker          Evaluator           Outcome
┌──────────┐    ┌──────────┐    ┌───────────────┐
│developing│───►│  review  │───►│    passed      │  ✓ Ship it
│          │    │          │───►│    failed      │──► back to developing
│          │    │          │    │    failed-final│──► triage
└──────────┘    └──────────┘    └───────────────┘
```

Expanding this into the full state diagram:

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

## States and the Roles That Own Them

Each lifecycle state belongs to either the Worker or the Evaluator. Understanding who owns what makes the flow intuitive:

### Worker-Owned States

| State | Who | Description |
|-------|-----|-------------|
| `developing` | Worker | The Worker is actively building — writing code, running tests, producing artifacts |
| `fixing` | Worker | The Worker is addressing specific feedback from the Evaluator's review |

### Evaluator-Owned States

| State | Who | Description |
|-------|-----|-------------|
| `review` | Evaluator | The Evaluator is inspecting the Worker's deliverables against acceptance criteria |

### System-Owned States

| State | Terminal | Description |
|-------|----------|-------------|
| `planning` | No | Epic is being decomposed into tasks by the manager |
| `planned` | No | Tasks are defined, waiting for dependency gates to clear |
| `ready` | No | All dependencies satisfied, room can be created |
| `passed` | Yes | Evaluator approved — all acceptance criteria met, work is done |
| `failed` | No | Evaluator rejected — specific issues documented, retry is possible |
| `failed-final` | Yes | Max retries exhausted — the Worker-Evaluator loop cannot close |
| `blocked` | No | Waiting on external dependency or human input |
| `timeout` | No | Execution exceeded the configured time limit |
| `escalated` | No | Sent to architect for design review |
| `redesign` | No | Architect determined a design change is needed |
| `cancelled` | Yes | Manually cancelled by the manager or user |

:::note[Terminal States]
Only three states are terminal: `passed`, `failed-final`, and `cancelled`. The manager agent is the only role authorized to set terminal states. Workers and Evaluators can transition between non-terminal states, but they cannot declare an epic finished or dead on their own.
:::

## The Worker-Evaluator Handoff

The core cycle is a **handoff protocol** between two roles:

### developing → review

The Worker finishes a task and posts a `done` message. This triggers the transition to `review`, where control passes from Worker to Evaluator. The Worker cannot self-approve — the handoff is mandatory.

```jsonl
{"type":"done","from":"worker"}  → developing → review
```

### review → passed or failed

The Evaluator examines the deliverables against the Definition of Done and Acceptance Criteria:

```jsonl
{"type":"pass","from":"evaluator"}  → review → passed
{"type":"fail","from":"evaluator"}  → review → failed
```

If the Evaluator passes the work, the epic reaches its terminal state. If the Evaluator fails it, the loop continues:

### failed → fixing → review

The Worker receives the Evaluator's feedback and enters `fixing`. Once fixes are complete, the Worker hands off to the Evaluator again:

```
failed → fixing → review → passed?  or  → failed again?
```

Each failure counts toward the retry limit. When retries are exhausted, the system enters **triage**.

## Triage: When the Loop Can't Close

In the workshop analogy, triage is what happens when the artisan has tried three times and the inspector still won't sign off. The workshop master steps in.

```
Attempt 1: develop → review → FAIL
Attempt 2: fix → review → FAIL
Attempt 3: fix → review → FAIL
  │
  ▼
failed-final → manager notified → triage
  │
  ├─► FIX verdict:      architect provides guidance, retry allowed
  ├─► REDESIGN verdict: epic restructured, loop restarts
  └─► REPLAN verdict:   plan modified, DAG rebuilt
```

After triage, the manager receives one of three verdicts:

- **FIX** — the implementation approach is sound, the Worker just needs specific guidance. The loop restarts with a clearer direction.
- **REDESIGN** — the epic's architecture needs changes before the Worker can succeed. The epic is restructured and the loop restarts from `developing`.
- **REPLAN** — the epic itself is flawed (too large, wrong scope, missing dependency). The plan is modified and the DAG is rebuilt.

:::caution[Triage Is Expensive]
Triage means the Worker-Evaluator loop failed to converge. Each triage consumes manager and architect attention — scarce resources that delay other epics. Well-written acceptance criteria and clear epic scoping are the best way to avoid triage.
:::

## Retry Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 3 | Maximum Evaluator rejection cycles before triage |
| `timeout_seconds` | 900 | Max time per Worker attempt (15 minutes) |
| `retry_delay_seconds` | 0 | Delay between retry attempts |

## Transition Mechanisms

State transitions are triggered by four mechanisms:

### 1. Agent Messages (Worker ↔ Evaluator Handoff)

The most common trigger. The Worker's `done` message hands control to the Evaluator. The Evaluator's `pass` or `fail` message determines the outcome.

```jsonl
{"type":"done","from":"worker"}    → developing → review
{"type":"pass","from":"evaluator"} → review → passed
{"type":"fail","from":"evaluator"} → review → failed
```

### 2. Manager Orchestration

The manager controls transitions that require cross-room awareness:

- `planning` → `planned` (after task decomposition)
- `planned` → `ready` (after dependency check)
- `failed` → `developing` (after retry decision)
- `failed` → `failed-final` (after max retries — triggers triage)

### 3. Timeout Enforcement

The system monitors execution time and forces transitions when limits are exceeded:

- `developing` for > `timeout_seconds` → `timeout`
- `timeout` → `escalated` (automatic)

### 4. Manual Override

Users can force state transitions through the dashboard or CLI.

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
Every status update is validated against `lifecycle.json`. If an agent attempts an invalid transition (e.g., `planning` → `passed`), the update is rejected and an error is logged. This prevents agents from bypassing the quality gates.
:::

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
{"ts":"2025-01-15T10:00:10Z","from":"ready","to":"developing","actor":"manager","reason":"Worker assigned"}
{"ts":"2025-01-15T10:15:00Z","from":"developing","to":"review","actor":"worker","reason":"TASK-001 done"}
{"ts":"2025-01-15T10:20:00Z","from":"review","to":"failed","actor":"evaluator","reason":"Test coverage 72%, required 95%"}
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

The `percent` field is clamped to 0–100 and drives the dashboard progress bars.

### PROGRESS.md

Human-readable progress notes maintained by the Worker:

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

## Lifecycle Customization

The lifecycle can be customized per plan or per epic using the `create-lifecycle` skill. This skill generates specialized lifecycles for different epic types — for example, a "documentation" lifecycle might skip the QA review step entirely, while a "security" epic might add an additional security-review stage between `developing` and `review`.

Custom lifecycles can also be configured using the **Pipeline** directive in `PLAN.md`, which inserts additional review stages with their own correction loops:

```
Pipeline: architect -> engineer -> security-review -> qa
```

Each stage containing "review", "qa", "audit", "check", or "verify" gets pass/fail/escalate transitions with correction loops back through fixing.

## Key Files

| File | Purpose |
|------|---------|
| `.agents/war-rooms/*/lifecycle.json` | Per-room state machine definition |
| `.agents/war-rooms/*/status.txt` | Current state |
| `.agents/war-rooms/*/progress.json` | Completion tracking |
| `.agents/mcp/warroom-server.py` | Status and progress MCP tools |
