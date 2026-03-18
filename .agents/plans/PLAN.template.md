<!-- MANAGER INSTRUCTION:
When generating a plan, you MUST explicitly define a `Lifecycle` for EACH Epic.
The roles and lifecycle MUST BE DYNAMICALLY DESIGNED based on the specific requirements of the Epic. 
Not all tasks require an engineer or qa. For example, a research epic might only need a researcher and analyst, while a documentation epic might need a writer and editor.
Whatever the roles, you must design a closed-loop workflow optimized for those specific autonomous agents, allowing them to operate without stalling.
Always map out the transition states, including what happens on failure.

Example of a dynamic closed workflow for a generic task:
```text
pending → [Primary Task] → [Review/Audit] ─┬─► passed → signoff
                 ▲                         │
                 └───── [Fixing State] ◄───┘ (on fail)
```
-->

# Plan: Example Feature

> Created: 2026-03-17T00:00:00+00:00
> Status: draft
> Project: /path/to/your/project

## Config

working_dir: /path/to/your/project

---

Per-epic format:
```
Roles: <role1>, <role2>, ...    (dynamically chosen agents for this epic's workflow)
Objective: <mission>            (what this war-room must achieve — be specific)
Lifecycle:                      (REQUIRED: Dynamically map the closed-loop transitions between the chosen roles, including specific failure/correction states)
Pipeline: <stage1 -> stage2>    (OPTIONAL: only for non-default stage sequences)
Skills: <capabilities>          (comma-separated, guides agent focus)
Working_dir: <path>             (scope agents to a subdirectory)
Capabilities: <cap1, cap2>     (optional: auto-generates review stages)
```

Available roles: architect, engineer, qa, security-auditor, database-architect, devops, or any custom role.

#### War-Room Lifecycle (Closed Loop)

Every war-room runs a dynamically designed closed lifecycle where the specific agents assigned to that epic iterate and correct each other's work until all quality gates pass.

For example, an Engineering Epic might use:

```text
pending → engineering → qa-review ─┬─► passed → signoff
               ▲                   │
               └──── fixing ◄──────┘ (on fail)
```

While a Research Epic might use:
```text
pending → research → peer-review ─┬─► passed → signoff
              ▲                   │
              └──── revising ◄────┘ (on fail)
```

- Each loop repeats until the review passes or retries are exhausted.
- Complex loops can include escalations (e.g. failing a design review routes back to an architect).

#### Pipeline Directive (Optional)

Override the default lifecycle to add specialized review stages.
Each review stage becomes an additional quality gate with its own correction loop:

```
Pipeline: architect -> engineer -> security-review -> qa
Pipeline: engineer -> schema-review -> qa
Pipeline: researcher -> engineer -> architect-review -> qa
```

Stages containing "review", "qa", "audit", "check", or "verify" get
pass/fail/escalate transitions with correction loops back through fixing.

#### Capabilities Directive

Declare required capabilities. The system auto-inserts review stages:

```
Capabilities: security, database        (adds security-review + schema-review stages)
Capabilities: accessibility, security   (adds a11y-review + security-review stages)
```

Capability-to-stage mapping:
- `security` -> `security-review` (by `security-auditor`)
- `database` -> `schema-review` (by `database-architect`)
- `architecture` -> `architect-review` (by `architect`)
- `infrastructure` -> `infra-review` (by `devops`)
- `accessibility` -> `a11y-review` (by `accessibility-specialist`)

---

## Goal

A clear, concise description of what this plan aims to achieve and the problem it solves.

## EPIC-001 - Research & Strategy

Roles: researcher, analyst
Objective: Investigate market trends and synthesize a strategy document
Lifecycle:
```text
pending → research → review ─┬─► passed → signoff
              ▲              │
              └─ revising ◄──┘ (on fail)
```

Tasks: Gather data on competitor products. Analyze features and formulate a strategy document.

#### Definition of Done
- [ ] Strategy document created and peer-reviewed

#### Tasks
- [ ] TASK-001 — Gather competitor data
- [ ] TASK-002 — Synthesize into strategy

Acceptance criteria:
- Document includes at least 3 competitor profiles.
- Strategy is clear and actionable.

depends_on: []

## EPIC-002 - Feature Implementation

Roles: backend-engineer, frontend-engineer, qa
Objective: Implement core feature logic and UI
Lifecycle:
```text
pending → backend-dev → frontend-dev → qa-review ─┬─► passed → signoff
               ▲              ▲                   │
               │              └──── ui-fixing ◄───┤ (on ui bug)
               └──────────── backend-fixing ◄─────┘ (on api bug)
```

Tasks: Build the APIs based on the strategy. Implement the matching UI.

#### Definition of Done
- [ ] End-to-end feature is built and tested

#### Tasks
- [ ] TASK-001 — Build REST APIs
- [ ] TASK-002 — Build React components

Acceptance criteria:
- UI successfully fetches data from APIs.
- QA validates all user journeys.

depends_on: [EPIC-001]

## EPIC-003 - Documentation & Delivery

Roles: technical-writer, editor
Objective: Create user guides and deployment documentation
Lifecycle:
```text
pending → drafting → editorial-review ─┬─► passed → signoff
             ▲                         │
             └─────── editing ◄────────┘ (on fail)
```

Tasks: Write end-user documentation. Produce a runbook for the ops team.

#### Definition of Done
- [ ] Documentation approved by Editor

#### Tasks
- [ ] TASK-001 — Write User Guide
- [ ] TASK-002 — Write Ops Runbook

Acceptance criteria:
- Runbook contains troubleshooting steps.
- Docs are published to the internal portal.

depends_on: [EPIC-002]
