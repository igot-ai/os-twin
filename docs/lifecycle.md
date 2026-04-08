# Epic Lifecycle

## State Machine

Each war-room has a `lifecycle.json` defining its state machine. The lifecycle
controls which role acts in each state and what transitions are valid.

### Typical Lifecycle Flow

```
pending
  |  (all upstream dependencies in DAG are "passed")
  v
developing / engineering
  |  (agent posts "done" to channel)
  v
review (QA)
  |
  +-- pass --> passed (TERMINAL -- epic complete)
  |
  +-- fail --> developing (increment retries, engineer re-enters with feedback)
  |
  +-- escalate --> manager-triage
                    |
                    +-- fix --> developing (another attempt)
                    |
                    +-- redesign --> developing (revised brief)
                    |
                    +-- reject --> failed-final (TERMINAL)

developing (on error or retries exhausted)
  |
  v
failed
  |
  +-- retry --> developing (if retries < max_retries)
  |
  +-- exhaust --> failed-final (TERMINAL)
```

## `lifecycle.json` Format

```json
{
  "initial_state": "engineering",
  "states": {
    "engineering": {
      "type": "agent",
      "role": "engineer",
      "transitions": {
        "done": "review"
      }
    },
    "review": {
      "type": "agent",
      "role": "qa",
      "transitions": {
        "pass": "passed",
        "fail": "developing",
        "escalate": "manager-triage"
      }
    },
    "developing": {
      "type": "agent",
      "role": "engineer",
      "transitions": {
        "done": "review"
      }
    },
    "manager-triage": {
      "type": "builtin",
      "role": "manager",
      "transitions": {
        "fix": "developing",
        "redesign": "developing",
        "reject": "failed-final"
      }
    },
    "passed": {
      "type": "terminal"
    },
    "failed-final": {
      "type": "terminal"
    }
  }
}
```

## All Possible States

| State | Type | Role | Description |
|-------|------|------|-------------|
| `pending` | waiting | -- | Waiting for upstream dependencies |
| `engineering` | agent | engineer | Initial implementation phase |
| `developing` | agent | engineer | Implementation/fixing phase |
| `review` | agent | qa | QA reviewing the work |
| `optimize` | agent | engineer | Performance optimization pass |
| `manager-triage` | builtin | manager | Manager deciding next action |
| `architect-review` | agent | architect | Architect reviewing design |
| `fixing` | agent | engineer | Fixing issues from review |
| `signoff` | waiting | -- | Awaiting human sign-off |
| `paused` | waiting | -- | Manually paused |
| `blocked` | waiting | -- | Blocked on external dependency |
| `passed` | terminal | -- | Epic completed successfully |
| `failed` | transient | -- | Failed, may retry |
| `failed-final` | terminal | -- | Failed permanently |

## State Transition Mechanisms

### 1. Filesystem Status File

Each room has a `status` file containing a single word (the current state).
This is the source of truth.

### 2. API Endpoint

```
POST /api/plans/{plan_id}/epics/{epic_ref}/state
Body: { "status": "developing" }
```

Writes the new status to the `status` file and recalculates `progress.json`.

### 3. Room Actions

```
POST /api/plans/{plan_id}/rooms/{room_id}/action
Body: { "action": "stop" }    --> status = "failed-final"
Body: { "action": "pause" }   --> status = "paused"
Body: { "action": "resume" }  --> status = "pending"
```

### 4. Manager Loop

The manager loop (`Start-ManagerLoop.ps1`) polls every 5 seconds:
1. Reads DAG and progress
2. For each room in `pending`: checks if all dependencies are `passed`
3. If ready: spawns a worker and transitions to `developing`/`engineering`
4. For rooms in `failed`: checks retry count against `max_retries`

### 5. Resume on Restart

`Start-Plan.ps1 -Resume` handles recovery:
- `failed-final` and `blocked` rooms reset to `pending`
- `fixing` rooms reset to `developing`

## Retry Logic

| Setting | Default | Location |
|---------|---------|----------|
| `max_retries` | 3 | `config.json` -> `constraints.max_retries` |
| `timeout_seconds` | 900 (15 min) | `config.json` -> `constraints.timeout_seconds` |

When a room reaches `failed`:
- If `retries < max_retries`: auto-transition to `developing`, increment counter
- If `retries >= max_retries`: transition to `failed-final` (terminal)

The retry counter is stored in the room's `retries` file.

## Timeout Enforcement

Rooms stuck in a state for longer than `timeout_seconds` are force-transitioned
to `failed`. The whitepaper specifies a default of 40 minutes for complex epics.

## Audit Trail

Every state transition is logged to `{room_dir}/audit.log`:

```
2026-04-01T10:00:00Z  pending -> developing  (manager: dependencies met)
2026-04-01T11:30:00Z  developing -> review   (engineer: done message posted)
2026-04-01T11:45:00Z  review -> passed       (qa: all tests passing)
```

Exposed via `GET /api/plans/{plan_id}/epics/{task_ref}/audit`.

## Progress Tracking

`Update-Progress.ps1` scans all rooms and writes:

**`progress.json`** (machine-readable):
```json
{
  "updated_at": "2026-04-07T13:01:36Z",
  "total": 7,
  "passed": 6,
  "failed": 1,
  "blocked": 0,
  "active": 0,
  "pending": 0,
  "pct_complete": 85.7,
  "critical_path": "5/6",
  "rooms": [
    { "room_id": "room-000", "task_ref": "PLAN-REVIEW", "status": "passed" },
    { "room_id": "room-006", "task_ref": "EPIC-006", "status": "failed-final" }
  ]
}
```

**`PROGRESS.md`** (human-readable): Formatted summary for quick status checks.

## Lifecycle Generation

`Resolve-Pipeline.ps1` generates `lifecycle.json` for each room based on:
- The room's assigned role(s)
- The pipeline variant specified in the plan (`Pipeline: standard`)
- Custom lifecycle definitions embedded in the epic markdown

`ConvertFrom-AsciiLifecycle.ps1` can parse ASCII lifecycle notation for
inline definitions.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/lifecycle/Resolve-Pipeline.ps1` | Generate lifecycle.json per room |
| `.agents/lifecycle/ConvertFrom-AsciiLifecycle.ps1` | Parse ASCII lifecycle notation |
| `.agents/roles/manager/Start-ManagerLoop.ps1` | Polls rooms, enforces lifecycle |
| `.agents/plan/Update-Progress.ps1` | Scans rooms, writes progress files |
| `.agents/plan/Test-DependenciesReady.ps1` | Dependency gate check |
| `dashboard/routes/plans.py` | State change API, progress recalculation |
| `dashboard/tasks.py` | Background polling for state changes |
