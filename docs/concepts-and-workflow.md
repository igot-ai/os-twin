# OS Twin — Concepts & Workflow

> Source: `/Users/macbook/Documents/kitemetric/igot/os-twin`

## Core Entities

### Project

The top-level container. A filesystem directory that holds all plans and war-rooms.

- Contains `.agents/` — configuration, plans, role definitions
- Contains `.war-rooms/` — runtime execution directories
- Identified by directory path or `OSTWIN_PROJECT_DIR` env var

### Plan

A markdown document (`{plan_id}.md`) that defines the goal and work breakdown.

- Stored in `.agents/plans/`
- Contains structured sections: Goal, Config, and multiple Epics
- Associated files: `{plan_id}.meta.json` (metadata), `{plan_id}.roles.json` (role config)
- Status lifecycle: `draft` → `launched` → `completed`

### Epic

A unit of work parsed from a Plan's `## Epic:` or `## Task:` headers.

- Contains: objective, acceptance criteria, definition of done, task list
- Can declare dependencies on other Epics (e.g., `depends_on: [EPIC-001]`)
- Each Epic spawns exactly one Room when the Plan is launched

### Room (War-Room)

The runtime execution context for a single Epic. Where AI agents collaborate.

- Directory: `.war-rooms/room-{N}/`
- Contains: `channel.jsonl` (message log), `status`, `brief.md`, `TASKS.md`, `config.json`
- One-to-one mapping with an Epic

**Hierarchy:**

```
Project
  └── Plan (markdown spec)
        └── Epic (parsed from Plan)
              └── Room (1:1 execution context)
                    └── Messages (JSONL channel)
```

---

## Roles

| Role | Purpose | Model |
|------|---------|-------|
| **Manager** | Orchestration loop — spawns rooms, monitors state, routes messages, classifies failures, drafts releases | Bash loop (5s poll) |
| **Engineer** | Implements code — receives epic/task, creates TASKS.md breakdown, codes, posts `done` | Gemini 3-Flash |
| **QA** | Reviews work — validates against acceptance criteria, runs tests, posts `pass`/`fail`/`escalate` | Gemini 3-Flash |
| **Architect** | Design review — triggered only on QA escalation for design/architectural issues | Gemini 3.1-Pro |

---

## Workflow

### Per-Room State Machine

Each Room processes its Epic through a sequential pipeline of roles (not parallel):

```
pending → engineering → qa-review ──┬──► passed ──► release
              ▲                     │
              │              manager-triage
              │               ├─ implementation-bug → fixing ─┘
              │               ├─ design-issue → architect-review ─┘
              │               └─ plan-gap → architect-review → plan-revision ─┘
              │                                                    │
              └────────────────────────────────────────────────────┘
```

### Roles Work Sequentially on the Same Epic

There is no splitting of an Epic across roles. A single Epic flows through a pipeline of roles within its Room:

1. **Engineer** receives the full Epic → implements everything → posts `done`
2. **QA** reviews the same Epic → validates code and tests → posts `pass` or `fail`
3. On failure → **Manager** triages and classifies the issue
4. On design escalation → **Architect** reviews and provides guidance

### Parallelism Happens at the Epic Level

Multiple Epics from the same Plan run in separate Rooms concurrently (up to 50):

```
Plan with 5 Epics:
  Room-001 (EPIC-001): engineer → qa → passed     (concurrent)
  Room-002 (EPIC-002): engineer → qa → fixing      (concurrent)
  Room-003 (EPIC-003): engineer → qa → passed      (concurrent)
  Room-004 (EPIC-004): pending                      (waiting on dependency)
  Room-005 (EPIC-005): engineering                  (concurrent)
```

### Manager Failure Triage

When QA rejects work, the Manager classifies the failure:

| Classification | Trigger | Route |
|---|---|---|
| **implementation-bug** (default) | Specific code issues, test failures | Back to engineer with fix instructions (max 10 retries) |
| **design-issue** | Architecture/scope problems, capability mismatch | To architect, then back to engineer |
| **plan-gap** | Unclear specs, missing requirements | To architect, update brief.md, restart engineering |

### Release Process

Triggered when all Rooms reach `passed`:

1. Manager drafts `RELEASE.md` with all task verdicts and metadata
2. Collects signoffs from: manager, engineer, QA
3. Finalizes with timestamps — release complete

---

## End-to-End Flow

1. User creates a **Plan** (markdown with epics)
2. User launches the plan via `/api/run`
3. **Manager** parses epics, spawns one **Room** per epic
4. **Engineer** receives task → implements → posts `done`
5. Manager routes to **QA** → reviews → `pass` or `fail`
6. On fail → Manager triages → routes back to engineer or escalates to **Architect**
7. Cycle repeats until `passed` or `failed-final` (max retries exhausted)
8. All rooms passed → **Release** drafted and signed off

---

## Key Configuration

| Parameter | Default |
|-----------|---------|
| Poll interval | 5 seconds |
| Max concurrent rooms | 50 |
| Max engineer retries | 10 |
| State timeout | 900 seconds |
| Engineer timeout | 600 seconds |
| QA timeout | 300-600 seconds |

---

## Message Protocol

Agents communicate via `channel.jsonl` in each Room:

```json
{
  "ts": "2026-03-20T10:30:00Z",
  "from": "manager",
  "to": "engineer",
  "type": "task",
  "ref": "EPIC-001",
  "body": "..."
}
```

Message types: `task`, `done`, `review`, `pass`, `fail`, `fix`, `signoff`, `release`, `error`
