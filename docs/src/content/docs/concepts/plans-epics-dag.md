---
title: "Plans, Epics & DAG"
description: "How OSTwin composes big plans, decomposes them into epics for agents, and uses DoD and AC as the twin pillars that drive autonomous quality."
sidebar:
  order: 6
---

OSTwin organizes work in a three-level hierarchy: **Plans** contain **Epics** which are ordered by a **DAG** (Directed Acyclic Graph). But the real story is how a plan — a human-authored vision of what to build — gets decomposed into units of work that autonomous agents can execute with high quality, without human micromanagement.

The key insight: **DoD (Definition of Done) and AC (Acceptance Criteria) are the twin pillars** that let every agent — regardless of role — understand what "done" looks like and how to verify it. Tasks are deliberately kept minimal. The agent fills in the how.

## The Decomposition Story

```
Human Intent                          Agent Execution
─────────────                         ───────────────
"What should we build?"               "How do I build it right?"

Plan (the big picture)          →     Epic (a scoped unit of work)
  └── Written by humans               └── Assigned to a war-room
  └── Declares the WHY                     └── DoD: WHAT must be true
  └── Establishes constraints              └── AC: HOW to verify it's true
                                           └── Tasks: agent decides the HOW
```

A plan starts as a single document — `PLAN.md` — capturing what the human wants built. The manager agent then decomposes this plan into epics, each with a clear scope. But here's the critical design choice: **we deliberately define only the most basic tasks**. We don't prescribe detailed step-by-step instructions.

Why? Because over-specifying tasks biases the agent toward a particular implementation path. By keeping tasks minimal, we force each agent to harness its own practice — its skills, its experience, its judgment — to determine the best approach. The guardrails aren't in the tasks. The guardrails are in **DoD and AC**.

## DoD and AC: Two Pillars, One Quality Contract

Every epic carries two complementary specifications that together form its **quality contract**:

### Definition of Done (DoD) — The WHAT

The DoD is a checklist of concrete, verifiable outcomes. It answers the question: **"What must be true when this epic is complete?"**

```markdown
### Definition of Done
- [ ] Login endpoint returns valid JWT with 1-hour expiry
- [ ] Invalid credentials return 401 with descriptive error
- [ ] Rate limiting: max 5 attempts per minute per IP
- [ ] All endpoints have OpenAPI documentation
- [ ] Test coverage >= 95% on auth module
```

The DoD is **outcome-oriented**. It doesn't say *how* to implement rate limiting — only that it must exist and behave a certain way. This gives the engineer agent the freedom to choose the right approach while keeping the goalposts clear.

### Acceptance Criteria (AC) — The HOW to Verify

AC provides behavioral specifications that answer: **"How do we prove the DoD is satisfied?"**

```markdown
### Acceptance Criteria
Given a user with valid credentials
When they POST to /auth/login with email and password
Then they receive a 200 response with a JWT token
And the token contains user_id and role claims
And the token expires in 3600 seconds
```

AC is **verification-oriented**. It gives the QA agent a precise script to test against. Where DoD says "login works," AC says "here's exactly what 'login works' looks like when I test it."

### Why Both Pillars Are Essential

DoD and AC support each other. Neither is sufficient alone:

| Without DoD | Without AC |
|-------------|------------|
| The engineer doesn't know *what* to build | The engineer knows what but can't tell if they built it correctly |
| The QA agent has no outcomes to verify | The QA agent has outcomes but no test plan to verify them |
| Tasks drift toward tangential work | "Done" becomes subjective — "it works on my machine" |

Together, they create a closed loop:

```
DoD defines the target ─────► Engineer implements toward the target
                                       │
                                       ▼
AC defines the test ─────► QA verifies against the test
                                       │
                                       ▼
                             If DoD ✓ and AC ✓ → epic passes
                             If DoD ✗ or AC ✗ → epic fails, retry
```

This is why **you can run an epic without explicit tasks** — the agent can derive tasks from DoD+AC. But you should never run an epic without both DoD and AC. They are the minimum viable contract for quality.

## Plan Hierarchy

With this philosophy in mind, here's the full hierarchy:

```
Plan (PLAN.md)
  ├── Epic 1: Setup database schema
  │     └── DoD: [outcomes]  AC: [behavioral specs]
  ├── Epic 2: Implement auth API  (depends on Epic 1)
  │     └── DoD: [outcomes]  AC: [behavioral specs]
  ├── Epic 3: Build admin dashboard  (depends on Epic 2)
  │     └── DoD: [outcomes]  AC: [behavioral specs]
  └── Epic 4: Write documentation  (depends on Epics 2 & 3)
        └── DoD: [outcomes]  AC: [behavioral specs]
```

Each epic is a self-contained unit. Its DoD and AC travel with it into the war-room, becoming the contract that every agent in that room works against.

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

### Definition of Done
- [ ] Users table with email, password_hash, created_at
- [ ] Sessions table with token, user_id, expires_at
- [ ] Migration scripts tested on clean database

### Acceptance Criteria
Given a clean PostgreSQL database
When the migration scripts are executed
Then the users table exists with columns: email, password_hash, created_at
And the sessions table exists with columns: token, user_id, expires_at
And running migrations on an already-migrated database produces no errors

## EPIC-002: Auth API
Implement REST endpoints for authentication flows.
- depends_on: [EPIC-001]
- roles: [engineer, qa, architect]

### Definition of Done
- [ ] POST /auth/login returns JWT
- [ ] POST /auth/refresh extends session
- [ ] POST /auth/reset sends password reset email
- [ ] 95% test coverage on auth module

### Acceptance Criteria
Given a registered user with email "test@example.com" and password "secret"
When they POST to /auth/login with those credentials
Then they receive a 200 response with a JWT token
And the token contains user_id and role claims
And the token expires in 3600 seconds

## EPIC-003: Admin Dashboard
Build the admin interface for user and session management.
- depends_on: [EPIC-002]
- roles: [engineer, qa]

## EPIC-004: Documentation
Write API reference and admin guide.
- depends_on: [EPIC-002, EPIC-003]
- roles: [engineer]
```

## Tasks: Deliberately Minimal

Epics *may* include a task breakdown, but tasks are intentionally basic:

```markdown
### Tasks
- TASK-001: Implement auth endpoints
- TASK-002: Write tests
```

That's it. Not "TASK-001: Create Express router at `src/routes/auth.ts`, add JWT middleware using `jsonwebtoken` package, implement bcrypt comparison..." — that level of detail biases the agent and defeats the purpose of having autonomous agents in the first place.

**The principle**: Tasks provide sequencing hints, not implementation instructions. The agent uses its skills and judgment to determine the how. DoD and AC are what keep it on track.

You can even omit tasks entirely. The manager or engineer agent will derive them from the DoD and AC:

```
DoD: "Login endpoint returns valid JWT"
AC:  "POST /auth/login → 200 + JWT token"
        │
        ▼ (agent derives)
TASK-001: Implement login endpoint
TASK-002: Validate against AC scenarios
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

## How DoD and AC Flow Through the System

The quality contract doesn't stay in `PLAN.md` — it propagates through every stage:

```
PLAN.md
  │
  ├── DoD + AC written per epic
  │
  ▼
config.json (war-room)
  │   DefinitionOfDone: [...]
  │   AcceptanceCriteria: [...]
  │
  ├── Engineer reads DoD → derives tasks, implements
  ├── QA reads AC → writes test scenarios, verifies
  ├── QA reads DoD → checks outcomes checkbox by checkbox
  │
  ▼
Channel messages
  │   engineer → qa: "done" (claims DoD is satisfied)
  │   qa → engineer: "pass" (verified both DoD and AC)
  │   qa → engineer: "fail" (AC scenario X failed)
  │
  ▼
Terminal state: "passed" only when DoD ✓ AND AC ✓
```

Every role in the war-room uses DoD and AC differently, but they all use the same source of truth. This is what makes multi-agent collaboration work without a human in the loop — the quality contract is unambiguous and shared.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/Build-PlanningDAG.ps1` | Kahn's algorithm implementation |
| `.agents/plan/Start-Plan.ps1` | Wave resolution from DAG state |
| `.agents/plans/*/PLAN.md` | Plan definitions |
| `.agents/plans/*/DAG.json` | Computed dependency graphs |
| `.agents/plan/Start-Plan.ps1 (Plan Review logic)` | Plan review orchestration |
