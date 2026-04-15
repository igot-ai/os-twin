<!-- MANAGER INSTRUCTION:
When generating a plan, you MUST explicitly define a `Roles: ...` for EACH Epic.
The `roles` MUST BE DYNAMICALLY DESIGNED based on the specific requirements of the Epic. 
Not all tasks require an engineer or qa. For example, a research epic might only need a researcher and analyst, while a documentation epic might need a writer and editor.
Whatever the roles, you must design a closed-loop workflow optimized for those specific autonomous agents, allowing them to operate without stalling.
IMPORTANT: Lifecycle state names MUST use the ROLE AGENT NAMES (e.g., `@researcher`, `@analyst`, `@engineer`, `qa`), NOT generic action names (e.g., `research`, `review`, `drafting`). This is because the manager loop uses state names to determine which agent to invoke.
Always map out the transition states, including what happens on failure.

Example of a dynamic closed workflow for a generic task:
```text
pending → [primary-role] → [reviewer-role] ─┬─► passed → signoff
                ▲                           │
                └───── [primary-role] ◄─────┘ (on fail → fixing)
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
Roles: @<role1>, @<role2>, ...    (dynamically chosen agents for this epic's workflow)
Objective: <mission>            (what this war-room must achieve — be specific)
Lifecycle:                      (REQUIRED: Dynamically map the closed-loop transitions between the chosen roles, including specific 
working_dir: <path>             (scope agents to a subdirectory)
```

{{AVAILABLE_ROLES}}

#### EPIC Lifecycle (Closed Loop)

Every Epic runs a dynamically designed closed lifecycle where the specific agents assigned to that epic iterate and correct each other's work until all quality gates pass.

For example, an Engineering Epic might use:

```text
pending → engineer → qa ─┬─► passed → signoff
             ▲            │
             └─ engineer ◄┘ (on fail → fixing)
```

While a Research Epic might use:
```text
pending → researcher → analyst ─┬─► passed → signoff
              ▲                 │
              └── researcher ◄──┘ (on fail → fixing)
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

Roles: @researcher, @analyst
Objective: Investigate market trends and synthesize a strategy document
Lifecycle:
```text
pending → researcher → analyst ─┬─► passed → signoff
              ▲                 │
              └── researcher ◄──┘ (on fail → fixing)
```

Tasks: Gather data on competitor products. Analyze features and formulate a strategy document.

### Definition of Done
- [ ] ...

### Tasks
- [ ] ...

### Acceptance criteria:
- [ ] ...

depends_on: [EPIC-xxx]

## EPIC-002 - ...