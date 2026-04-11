---
title: "Plans, Epics & DAG"
description: "How OSTwin breaks work into plans, decomposes them into epics, and builds a dependency graph for parallel execution."
sidebar:
  order: 6
---

OSTwin organizes work in a three-level hierarchy: **Plans** contain **Epics** which are ordered by a **DAG** (Directed Acyclic Graph). This structure enables the manager agent to parallelize independent work while respecting dependencies.

## Plan Hierarchy

```
Plan (PLAN.md)
  ├── Epic 1: Setup database schema
  │     ├── Task 1.1: Create users table
  │     ├── Task 1.2: Create sessions table
  │     └── Task 1.3: Write migration scripts
  ├── Epic 2: Implement auth API  (depends on Epic 1)
  │     ├── Task 2.1: Login endpoint
  │     ├── Task 2.2: Token refresh
  │     └── Task 2.3: Password reset
  ├── Epic 3: Build admin dashboard  (depends on Epic 2)
  │     ├── Task 3.1: User management page
  │     └── Task 3.2: Session monitoring
  └── Epic 4: Write documentation  (depends on Epics 2 & 3)
        ├── Task 4.1: API reference
        └── Task 4.2: Admin guide
```

## Plan Definition Format

Plans are defined in a markdown file (`PLAN.md`) with structured epic blocks:

```markdown
# Authentication System

Build a complete authentication system with database-backed
sessions, REST API, admin dashboard, and documentation.

## EPIC-001: Database Schema
Setup the PostgreSQL schema for users and sessions.
- depends_on: []
- roles: [engineer, qa]

### DoD
- [ ] Users table with email, password_hash, created_at
- [ ] Sessions table with token, user_id, expires_at
- [ ] Migration scripts tested on clean database

## EPIC-002: Auth API
Implement REST endpoints for authentication flows.
- depends_on: [EPIC-001]
- roles: [engineer, qa, architect]

### DoD
- [ ] POST /auth/login returns JWT
- [ ] POST /auth/refresh extends session
- [ ] POST /auth/reset sends password reset email
- [ ] 95% test coverage on auth module

## EPIC-003: Admin Dashboard
Build the admin interface for user and session management.
- depends_on: [EPIC-002]
- roles: [engineer, qa]

## EPIC-004: Documentation
Write API reference and admin guide.
- depends_on: [EPIC-002, EPIC-003]
- roles: [engineer]
```

## Per-Plan Files

Each plan generates several files during processing:

| File | Purpose |
|------|---------|
| `PLAN.md` | Source plan with epic definitions |
| `PLAN.meta.json` | Computed metadata (timestamps, status, epic count) |
| `PLAN.roles.json` | Role assignments per epic |
| `PLAN.refined.md` | Manager-refined plan with expanded details |
| `DAG.json` | Computed dependency graph |
| `PLAN.skills.json` | Skill assignments per epic |

These files live in `.agents/plans/{plan-id}/`.

## Epic Structure

Each epic is a self-contained unit of work with clear acceptance criteria:

### Definition of Done (DoD)

The DoD is a checklist of concrete, verifiable outcomes:

```markdown
### DoD
- [ ] Login endpoint returns valid JWT with 1-hour expiry
- [ ] Invalid credentials return 401 with descriptive error
- [ ] Rate limiting: max 5 attempts per minute per IP
- [ ] All endpoints have OpenAPI documentation
- [ ] Test coverage >= 95% on auth module
```

### Acceptance Criteria (AC)

More detailed behavioral specifications:

```markdown
### AC
Given a user with valid credentials
When they POST to /auth/login with email and password
Then they receive a 200 response with a JWT token
And the token contains user_id and role claims
And the token expires in 3600 seconds
```

### Tasks

Epics are broken into ordered tasks by the manager or engineer:

```markdown
### Tasks
- TASK-001: Create auth router with login endpoint
- TASK-002: Implement JWT token generation and validation
- TASK-003: Add rate limiting middleware
- TASK-004: Write integration tests
- TASK-005: Generate OpenAPI docs
```

## Epic Metadata Directives

Epics support inline metadata directives that control execution:

| Directive | Type | Description |
|-----------|------|-------------|
| `depends_on` | `string[]` | Epic refs that must complete first |
| `roles` | `string[]` | Roles to assign to the war-room |
| `priority` | `int` | Execution priority within a wave (lower = first) |
| `timeout` | `int` | Max seconds before auto-escalation |
| `max_retries` | `int` | How many times QA can fail before escalation |
| `model` | `string` | Model override for this epic's agents |
| `no_mcp` | `bool` | Whether to disable MCP for this epic |
| `skill_refs` | `string[]` | Additional skills for this epic |

## DAG Building: Kahn's Algorithm

OSTwin converts epic dependencies into a DAG using **Kahn's algorithm** for topological sorting:

1. Parse all `depends_on` references from epics
2. Build an adjacency list and compute in-degrees
3. Initialize a queue with all epics that have zero dependencies (in-degree = 0)
4. Process the queue: for each epic, reduce in-degrees of its dependents
5. Epics reaching in-degree 0 join the current wave
6. Repeat until all epics are scheduled or a cycle is detected

:::caution[Cycle Detection]
If Kahn's algorithm terminates with unprocessed epics, the plan contains a dependency cycle. The manager will report the cycle and refuse to execute the plan until the user resolves it.
:::

## DAG.json Structure

The computed DAG is stored as a JSON file:

```json
{
  "plan_id": "plan-001",
  "generated_at": "2025-01-15T09:00:00Z",
  "nodes": {
    "EPIC-001": {
      "title": "Database Schema",
      "depends_on": [],
      "wave": 0,
      "priority": 1,
      "roles": ["engineer", "qa"]
    },
    "EPIC-002": {
      "title": "Auth API",
      "depends_on": ["EPIC-001"],
      "wave": 1,
      "priority": 1,
      "roles": ["engineer", "qa", "architect"]
    },
    "EPIC-003": {
      "title": "Admin Dashboard",
      "depends_on": ["EPIC-002"],
      "wave": 2,
      "priority": 1,
      "roles": ["engineer", "qa"]
    },
    "EPIC-004": {
      "title": "Documentation",
      "depends_on": ["EPIC-002", "EPIC-003"],
      "wave": 3,
      "priority": 1,
      "roles": ["engineer"]
    }
  },
  "waves": [
    ["EPIC-001"],
    ["EPIC-002"],
    ["EPIC-003"],
    ["EPIC-004"]
  ],
  "critical_path": ["EPIC-001", "EPIC-002", "EPIC-003", "EPIC-004"]
}
```

## Key DAG Concepts

### PLAN-REVIEW Root

Every DAG includes a synthetic `PLAN-REVIEW` node at wave 0. This node represents the plan review step where the manager validates the plan before execution begins. All user-defined epics depend on `PLAN-REVIEW` implicitly.

### Dependency Gating

An epic cannot begin execution until **all** of its dependencies have reached the `passed` terminal state. If any dependency fails, the dependent epic is blocked and the manager is notified.

:::note[Partial Failure]
If EPIC-002 depends on EPIC-001 and EPIC-001 fails, EPIC-002 is not automatically failed. The manager may retry EPIC-001, adjust the plan, or override the gate manually.
:::

### Wave Parallelism

Epics in the same wave have no dependencies on each other and can execute in parallel. The system creates one war-room per epic and runs all rooms in a wave concurrently (up to the 50-room limit).

```
Wave 0: [PLAN-REVIEW]
Wave 1: [EPIC-001]                    ← Sequential start
Wave 2: [EPIC-002, EPIC-005, EPIC-006] ← 3 rooms in parallel
Wave 3: [EPIC-003, EPIC-004]          ← 2 rooms in parallel
Wave 4: [EPIC-007]                    ← Final integration
```

### Critical Path

The longest path through the DAG determines the minimum execution time. The manager uses the critical path to prioritize epics and allocate resources.

## Two-Stage DAG

OSTwin uses a two-stage DAG process:

### Planning DAG

Created during the `plan-review` phase. Uses rough estimates and may contain placeholder dependencies. The manager refines this DAG based on plan review feedback.

### Solid DAG

Created after plan review is complete and all epics are fully specified. This is the executable DAG that drives war-room creation and wave scheduling.

```
PLAN.md → Planning DAG → Manager Review → PLAN.refined.md → Solid DAG → Execution
```

:::tip[DAG is Immutable During Execution]
Once the Solid DAG is computed and execution begins, the DAG structure is not modified. If a mid-execution change is needed, the manager creates a new plan revision with an updated DAG.
:::

## Key Source Files

| File | Purpose |
|------|---------|
| `engine/Build-DAG.ps1` | Kahn's algorithm implementation |
| `engine/Get-NextWave.ps1` | Wave resolution from DAG state |
| `.agents/plans/*/PLAN.md` | Plan definitions |
| `.agents/plans/*/DAG.json` | Computed dependency graphs |
| `engine/Invoke-PlanReview.ps1` | Plan review orchestration |
