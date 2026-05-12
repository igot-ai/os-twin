---
title: "Pillar 4: War-Rooms"
description: "Isolated execution units where agents collaborate on a single epic with full filesystem-level separation."
sidebar:
  order: 4
  icon: rocket
---

War-rooms are OSTwin's core execution primitive. Each war-room is a **self-contained directory** where a team of agents collaborates on a single epic. Everything an agent needs -- its brief, channel, artifacts, progress state -- lives inside the room directory.

## Directory Layout

Every war-room follows a strict directory structure:

```
.agents/war-rooms/room-042/
  config.json          # Goal contract: epic ref, roles, definition of done
  brief.md             # What the team must accomplish
  tasks.md             # Breakdown of tasks to complete
  channel.jsonl        # Append-only message log
  progress.json        # Current completion percentage
  status               # Current lifecycle state (e.g. pending, in_progress)
  retries              # Current retry count
  done_epoch           # Epoch timestamp of completion
  task-ref             # Task or Epic reference
  lifecycle.json       # State machine definition
  lifecycle.md         # Readable version of state machine
  artifacts/           # Deliverables produced by agents
  pids/                # Process IDs for running agents
  contexts/            # Room contexts
  assets/              # Room assets
```

:::note[Everything is a File]
War-rooms use the filesystem as their coordination layer. There is no database, no message broker, no shared memory process. This makes rooms inspectable with `ls`, debuggable with `cat`, and portable with `cp`.
:::

## Goal Contract: config.json

The `config.json` file is the war-room's contract. It defines what the room exists to accomplish and how agents should operate within it.

```json
{
  "RoomId": "room-042",
  "TaskRef": "EPIC-007",
  "TaskDescription": "Implement user authentication flow",
  "WorkingDir": ".",
  "DefinitionOfDone": [
    "JWT working",
    "Tests pass"
  ],
  "AcceptanceCriteria": [
    "POST /login returns 200"
  ],
  "PlanId": "plan-001",
  "DependsOn": [
    "EPIC-003",
    "EPIC-005"
  ],
  "MaxRetries": 3,
  "TimeoutSeconds": 900
}
```

## Message Channel

The `channel.jsonl` file is an append-only log of structured messages. Every inter-agent communication is recorded here.

```jsonl
{"id":"msg-001","ts":"2025-01-15T10:01:00Z","from":"manager","to":"engineer","type":"task","ref":"TASK-001","body":"Implement login endpoint per brief.md"}
{"id":"msg-002","ts":"2025-01-15T10:15:00Z","from":"engineer","to":"qa","type":"done","ref":"TASK-001","body":"Login endpoint implemented. See artifacts/auth.py. All tests pass."}
{"id":"msg-003","ts":"2025-01-15T10:20:00Z","from":"qa","to":"engineer","type":"pass","ref":"TASK-001","body":"Code review passed. 94% coverage. No security issues found."}
```

### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `task` | manager -> agent | Assign work with requirements |
| `done` | agent -> qa/manager | Report task completion |
| `review` | qa -> engineer | Detailed review feedback |
| `pass` | qa -> manager | Task meets acceptance criteria |
| `fail` | qa -> engineer | Task needs fixes, with specifics |
| `fix` | engineer -> qa | Resubmission after fixing issues |
| `error` | any -> manager | Unrecoverable error, needs escalation |
| `signoff` | role -> manager | Role confirms epic completion |

### Channel Scripts

The channel is managed through dedicated MCP tools and PowerShell scripts:

| Script | Purpose |
|--------|---------|
| `channel_post_message` | Append a message with file locking |
| `channel_read_messages` | Read with optional filters (role, type, ref) |
| `channel_get_latest` | Get the most recent message of a given type |

All writes use `fcntl.LOCK_EX` (exclusive file locking) to prevent corruption from concurrent agent writes.

## Multi-Agent Collaboration Flow

A typical war-room execution follows this pattern:

```
Manager                Engineer              QA
  │                       │                   │
  ├─── task ─────────────>│                   │
  │                       ├── implements ──>  │
  │                       ├─── done ─────────>│
  │                       │                   ├── reviews
  │                       │<──── fail ────────┤
  │                       ├── fixes ────────> │
  │                       │                   ├── reviews
  │                       │<──── pass ────────┤
  │<───── signoff ────────┤                   │
  │<──────────────────── signoff ─────────────┤
  ├── updates status to "passed"              │
```

:::tip[Asynchronous by Default]
Agents don't run simultaneously inside a room. The manager orchestrates turns: engineer works, then QA reviews, then engineer fixes. This eliminates race conditions and makes the entire flow reproducible.
:::

## 5 Isolation Guarantees

War-rooms provide five levels of isolation:

| Guarantee | Mechanism | What It Prevents |
|-----------|-----------|------------------|
| **Filesystem isolation** | Each room has its own directory tree | Agents in room-042 cannot read room-043's files |
| **Channel isolation** | Separate `channel.jsonl` per room | Messages don't leak between epics |
| **Memory isolation** | Filtered views via `exclude_room` | Agents query cross-room memory without seeing their own |
| **MCP isolation** | Per-room `mcp.json` configuration | Tools are scoped to the room's needs |
| **Model isolation** | Per-room `model_override` | Different rooms can use different LLM models |

## Room Creation Flow

War-rooms are created by the manager agent during plan execution:

1. **DAG resolution** -- manager reads the DAG to find the next executable epics
2. **Room scaffolding** -- `war-rooms/New-WarRoom.ps1` creates the directory with config, brief, and lifecycle
3. **Role assignment** -- manager selects roles from the registry based on epic requirements
4. **Skill linking** -- relevant skills are union-merged from role, room, and plan levels
5. **Agent invocation** -- `roles/_base/Invoke-Agent.ps1` launches each role in sequence

```powershell
New-WarRoom -PlanId "plan-001" -EpicRef "EPIC-007" `
  -Roles @("engineer","qa") -Brief $briefContent
```

## Room Teardown

When a war-room reaches a terminal state (`passed` or `failed-final`):

1. Final status is written to `status`
2. All artifacts are preserved in the `artifacts/` directory
3. Memory entries published during execution remain in the shared ledger
4. The room directory is retained for audit and debugging purposes

:::caution[Rooms Are Never Deleted]
Even failed rooms are preserved. The `channel.jsonl` and `artifacts/` directory serve as an audit trail. If you need to reclaim disk space, archive rooms explicitly rather than deleting them.
:::

## Concurrency: 50 Rooms, Wave-Based

OSTwin supports up to **50 concurrent war-rooms** organized in waves:

- The DAG determines which epics can execute in parallel (no unsatisfied dependencies)
- Each wave is a set of rooms that can run simultaneously
- When all rooms in a wave complete, the next wave begins
- The manager monitors all active rooms via progress polling

Wave-based execution maximizes parallelism while respecting epic dependencies.

## Monitoring: Dashboard SSE

The FastAPI dashboard provides real-time war-room monitoring via Server-Sent Events:

- **Room status** -- current lifecycle state for all active rooms
- **Progress** -- completion percentage updated by agents
- **Channel activity** -- live message feed from all rooms
- **Error alerts** -- immediate notification of agent failures

The Next.js frontend subscribes to the SSE endpoint and renders a live dashboard view of all war-rooms in the current plan.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/war-rooms/New-WarRoom.ps1` | Room creation and scaffolding |
| `.agents/roles/_base/Invoke-Agent.ps1` | Agent invocation within a room |
| `.agents/mcp/warroom-server.py` | Channel and status MCP server |
| `.agents/war-rooms/` | All war-room directories |
| `dashboard/api/rooms.py` | Room status API endpoint |
