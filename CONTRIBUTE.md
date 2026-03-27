# Contributing to OS-Twin (Agent OS)

## What Is This Repo?

**OS-Twin** is an operating system for AI agents. It orchestrates hundreds of parallel **War-Rooms**, each containing specialized AI agents (Engineer, QA, Architect, Reporter, etc.) that collaborate through file-based message channels until every task passes quality gates.

The system reads a **plan file** (Markdown), breaks it into epics/tasks, spawns isolated war-rooms for each, and runs agents through a configurable lifecycle pipeline — all without external infrastructure. Just files.

---

## Repository Structure

```
os-twin/
├── .agents/                    # Core orchestration engine
│   ├── config.json             # Global configuration (models, timeouts, concurrency)
│   ├── run.sh                  # Legacy entry point
│   ├── plan/                   # Plan parsing & DAG construction
│   │   ├── Start-Plan.ps1      # Main entry: parses PLAN.md → creates war-rooms → starts loop
│   │   ├── Expand-Plan.ps1     # AI-powered plan refinement
│   │   ├── Build-DependencyGraph.ps1   # Builds DAG.json for task ordering
│   │   └── Build-PlanningDAG.ps1       # Advisory DAG for role assignment
│   ├── roles/                  # Agent role definitions
│   │   ├── _base/              # Shared infrastructure (Invoke-Agent, Resolve-Role, etc.)
│   │   ├── manager/            # Manager loop (the brain)
│   │   ├── engineer/           # Code-writing agent
│   │   ├── qa/                 # Quality assurance reviewer
│   │   ├── architect/          # System design & plan review
│   │   ├── audit/              # Security/compliance review
│   │   ├── reporter/           # Report generation after QA pass
│   │   ├── dynamic-role-plan-reviewer/ # Reviews dynamically-generated roles
│   │   └── registry.json       # Role registry (capabilities, runners, templates)
│   ├── lifecycle/              # Pipeline generation
│   │   └── Resolve-Pipeline.ps1  # Generates lifecycle.json per war-room
│   ├── channel/                # JSONL message bus (post, read, wait-for)
│   ├── war-rooms/              # War-room creation scripts
│   ├── skills/                 # Agent skill packs
│   │   ├── global/             # Skills available to all agents
│   │   └── roles/              # Role-specific skills
│   ├── lib/                    # Shared modules (Log, Utils, Config)
│   └── tests/                  # Pester & unit tests
├── dashboard/                  # FastAPI + Next.js web dashboard
│   ├── api.py                  # FastAPI application
│   ├── api_utils.py            # Shared helpers (skills, roles, plans)
│   ├── routes/                 # API route modules
│   ├── nextjs/                 # Frontend UI
│   └── zvec_store.py           # Vector store for semantic skill search
├── schemas/                    # JSON schemas for validation
├── contributes/                # Community-contributed dynamic roles (archived)
├── PLAN.md                     # Example/active plan file
└── bin/                        # CLI entry points
```

---

## Pipeline Architecture

The system follows a staged pipeline from plan → execution → release:

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐     ┌──────────┐
│  PLAN.md     │────►│  Start-Plan   │────►│  War-Rooms   │────►│  Manager │
│  (Markdown)  │     │  (parse,DAG)  │     │  (isolated)  │     │  Loop    │
└──────────────┘     └───────────────┘     └──────────────┘     └──────────┘
```

### Phase 1: Plan Parsing (`Start-Plan.ps1`)

1. Reads your `PLAN.md` and extracts `EPIC-NNN` and `TASK-NNN` entries
2. Parses per-epic metadata: `Roles:`, `Pipeline:`, `Capabilities:`, `Working_dir:`, `Lifecycle:`
3. Extracts `Definition of Done` and `Acceptance Criteria` blocks
4. Resolves `depends_on:` relationships
5. Creates `room-000` for plan negotiation (architect reviews the plan)
6. Optionally runs AI-powered plan expansion (`-Expand` flag)

### Phase 2: War-Room Creation

Each epic/task gets its own isolated directory under `.war-rooms/`:

```
.war-rooms/
├── room-000/          # Plan review room
│   ├── config.json    # Room configuration (role, deps, plan_id)
│   ├── brief.md       # Task description
│   ├── status         # Current state (pending, engineering, qa-review, etc.)
│   ├── channel.jsonl  # Message log
│   ├── lifecycle.json # State machine for this room
│   ├── skills/        # Resolved skills for this task
│   └── artifacts/     # Agent outputs
├── room-001/
├── room-002/
└── DAG.json           # Dependency graph
```

### Phase 3: Manager Loop (`Start-ManagerLoop.ps1`)

The manager is a continuous polling loop that orchestrates all rooms:

```
                    ┌─────────────────────────────────┐
                    │         MANAGER LOOP             │
                    │  (polls every 5s by default)     │
                    └─────────┬───────────────────────┘
                              │
          ┌───────────────────┼───────────────────────┐
          ▼                   ▼                       ▼
    ┌──────────┐        ┌──────────┐           ┌──────────┐
    │ pending  │        │ pending  │           │ blocked  │
    │          │        │          │           │(awaiting │
    │ Check    │        │ Check    │           │ upstream)│
    │ deps     │        │ deps     │           └──────────┘
    └────┬─────┘        └────┬─────┘
         │ deps met          │
         ▼                   ▼
    ┌──────────┐        ┌──────────┐
    │engineer- │        │engineer- │
    │  ing     │───►    │  ing     │
    │          │ done    │          │
    └────┬─────┘        └──────────┘
         │
         ▼
    ┌──────────┐    fail    ┌──────────┐
    │qa-review │──────────►│ fixing   │──► (back to qa-review)
    │          │           │          │
    └────┬─────┘           └──────────┘
         │ pass                 │ retries exhausted
         ▼                     ▼
    ┌──────────┐          ┌──────────────┐
    │ passed   │          │ failed-final │
    └──────────┘          └──────────────┘
```

**Key manager behaviors:**
- **Dependency gating:** Rooms stay `pending` until all upstream deps are `passed`
- **Concurrency control:** Max concurrent rooms is configurable (`max_concurrent_rooms`)
- **Retry logic:** Failed tasks are retried up to `max_engineer_retries` times
- **State timeouts:** Rooms stuck in a state for > `state_timeout_seconds` are force-retried
- **Triage:** QA failures are classified as `implementation-bug`, `design-issue`, or `plan-gap`
- **Skill resolution:** Before spawning a worker, skills are semantically matched via the dashboard API
- **Hot-reload:** New roles are detected every 30 seconds

### Phase 4: Dynamic Lifecycle Pipelines (`Resolve-Pipeline.ps1`)

Each war-room can have a custom lifecycle pipeline. There are three modes:

| Mode | Trigger | Example |
|------|---------|---------|
| **Explicit** | `Pipeline: engineer -> security-review -> qa` in plan | Custom review chain |
| **Capability-derived** | `Capabilities: security, database` in plan | Auto-inserts specialist review stages |
| **Default** | No directive | `engineering → qa-review → reporting` |

### Communication Protocol

All agents communicate via **JSONL message channels** — no external services needed:

```json
{"ts":"...","from":"manager","to":"engineer","type":"task","ref":"EPIC-001","body":"..."}
{"ts":"...","from":"engineer","to":"manager","type":"done","ref":"EPIC-001","body":"..."}
{"ts":"...","from":"manager","to":"qa","type":"review","ref":"EPIC-001","body":"..."}
{"ts":"...","from":"qa","to":"manager","type":"pass","ref":"EPIC-001","body":"..."}
```

---

## Quick Start

```bash
# 1. Write a plan
cat > my-plan.md << 'EOF'
## EPIC-001 — Build user authentication
Roles: engineer
Pipeline: engineer -> qa

#### Definition of Done
- [ ] Login endpoint works
- [ ] Tests pass

#### Acceptance Criteria
- [ ] Returns JWT on success
EOF

# 2. Launch
pwsh .agents/plan/Start-Plan.ps1 -PlanFile ./my-plan.md -ProjectDir .

# 3. Monitor
ls .war-rooms/room-*/status
```

---

## Roles

| Role | Purpose | Runner |
|------|---------|--------|
| **Manager** | Orchestrates all rooms, routes work, handles retries | `Start-ManagerLoop.ps1` |
| **Engineer** | Writes code, fixes bugs | `Start-EphemeralAgent.ps1` |
| **QA** | Reviews code, runs tests, passes or fails | `Start-QA.ps1` |
| **Architect** | Designs systems, reviews plans, writes ADRs | `Start-Architect.ps1` |
| **Audit** | Security and compliance review | Via registry |
| **Reporter** | Generates reports after tasks pass | Via registry |
| **Dynamic roles** | Created on-the-fly from `registry.json` templates | `Start-EphemeralAgent.ps1` |

---

## Skill System

Agent capabilities are managed through a 3-tier hierarchy:

1. **Global skills** (`.agents/skills/global/`) — loaded for all agents
2. **Role-specific skills** (`.agents/skills/roles/<role>/`) — loaded by role
3. **Room-resolved skills** — semantically matched at runtime via the dashboard's vector search

Skills are resolved before each agent spawn and copied into the room's `skills/` directory.

---

## Dashboard

The web dashboard (`dashboard/`) provides:

- **Plan management** — create, view, and trigger plans via API
- **Skills browser** — search, filter, and manage agent skills
- **War-room monitoring** — view room statuses and message channels
- **Role registry** — browse available roles and their capabilities

Run with:
```bash
ostwin dashboard
# or with a custom port:
OSTWIN_DASHBOARD_PORT=8080 ostwin dashboard
```

---

## Configuration

All tuning is in `.agents/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `manager.poll_interval_seconds` | `5` | How often the manager checks rooms |
| `manager.max_concurrent_rooms` | `50` | Parallel room limit |
| `manager.max_engineer_retries` | `10` | Retries before `failed-final` |
| `manager.state_timeout_seconds` | `900` | Seconds before force-retry |
| `manager.dynamic_pipelines` | `true` | Auto-generate lifecycle from task analysis |
| `manager.capability_matching` | `true` | Route failures to domain specialists |
| `engineer.default_model` | `gemini-3-flash-preview` | LLM model for engineers |
| `architect.default_model` | `gemini-3.1-pro-preview` | LLM model for architects |

---

## Contributing

1. **Roles** — Add new roles under `.agents/roles/<role-name>/` with a `ROLE.md` system prompt and register in `registry.json`
2. **Skills** — Add skill packs under `.agents/skills/roles/<role>/` or `.agents/skills/global/` with a `SKILL.md` file
3. **Pipeline stages** — Extend `Resolve-Pipeline.ps1` to support new review stage types
4. **Tests** — Pester tests go in `.agents/tests/`, Python tests in `dashboard/tests/`
