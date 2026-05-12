# Agentic Engineering Playbook
**Build Agents That Actually Ship.**

A field guide for engineers working in an AI-first SDLC. Every section maps a concept to how it changes the way you write prompts, design contexts, and structure epics — because in agentic systems, **your planning is your code**.

---

## 01. The Pyramid Principle
Borrowed from consulting, the **Pyramid Principle** is the most important thinking structure for anyone writing prompts, EPICs, or technical specs for AI agents. The rule is simple: *lead with your conclusion, then prove it*.

An LLM processes your prompt top-to-bottom and must hold all prior context in its attention window. If the conclusion is at the bottom, the agent has already made decisions before it knows what you want.

### The Three Pyramid Rules
| Rule | Meaning | In Practice |
| --- | --- | --- |
| **BLUF** | Bottom Line Up Front | First sentence = the task/decision |
| **MECE** | Mutually Exclusive, Collectively Exhaustive | No overlap in acceptance criteria; no gaps |
| **Rule of 3** | Group support into ≤3 clusters | Max 3 goals per EPIC phase, 3 AC per Story |

> **The Pyramid Principle is the foundation of every other concept in this handbook.** EPICs lead with the outcome. Prompts lead with the task. Context files lead with the current state. Master this, and everything else becomes cleaner.

---

## 02. Prompt-Driven Context
In classical software, your source code *is* the product. In agentic systems, **your context is the source code**. What you give the agent completely determines what it builds.

**Core Principle:** The quality of the AI's output is entirely a function of the quality of its input context. There is no "prompt magic." There is only context quality.

### What "Context" Means in This System
*   **CONTEXT.md**: The agent's memory. Tech stack, current phase, blockers, routing tags. Re-read at every session start.
*   **PLAN.md**: The Supervisor's spec. Phase goals, tasks per role, AC, DoD. The source of truth.
*   **SKILL.md**: Capability instruction files. Loaded on-demand via MCP.
*   **TODO.md**: Engineer's append-only log. Release notes per version.

> **If you find yourself correcting an agent mid-task, you have a context problem, not a model problem.** Go back and improve the PLAN.md before the next cycle.

---

## 03. Context Engineering
Context Engineering is designing the information environment for an agent's mind. A poorly-structured context produces hallucinations and out-of-scope changes. 

### The Four Properties of Good Context
1. **Bounded**: One context per feature. No cross-feature contamination.
2. **Current**: CONTEXT.md reflects *actual* current state, not intended state.
3. **Append-only**: History is never deleted. Agents read the full chain of decisions.
4. **Role-scoped**: Each agent owns exactly one file. Reads others' as read-only.

### CONTEXT.md Format — Required Fields
```yaml
# CONTEXT.md — {Feature Name}
Project:          {repo name}
Tech stack:       TypeScript, Postgres 15, Redis, Next.js 14
Routing tags:     [backend], [frontend]
Current phase:    Phase 2
Last completed:   v1d (Phase 1 — auth scaffolding)
Current blocker:  none
Architecture decisions:
  - JWT stored in httpOnly cookie (not localStorage)
  - Prisma ORM, no raw SQL
Phase summary:
  Phase 1 — Auth scaffolding (DONE)
  Phase 2 — Payment flow (ACTIVE)
  Phase 3 — Notifications (PENDING)
Agent assignments:
  Supervisor: Claude
  Engineer:   Cursor / Claude Code
  QA:         Claude (separate session)
```

---

## 04. MCP & Skills
**MCP (Model Context Protocol)** connects AI agents to tools and data dynamically. **Skills** (`SKILL.md` files) sit on top of MCP, instructing an agent *how* to use those tools.

### Skill File Design Rules
*   **Lead with trigger conditions** — when to use this skill, when not to.
*   **Include a worked example** — agents learn from demonstration.
*   **State constraints explicitly** — what the skill must never do.
*   **Version your skills** — changes break running agents.
*   **Keep skills single-purpose** — one SKILL.md per domain.

### MCP Server Scoping — Role-Based Access
Not every agent needs every tool.
*   **Supervisor**: filesystem (read), ROOM bus
*   **Engineer**: filesystem (rw), shell, git, DB
*   **QA**: filesystem (read), test runner, ROOM bus
*   **DevOps**: cloud CLI, registry, ROOM bus

---

## 05. Roles: Worker & Evaluator
The fundamental unit of agentic collaboration is the **Worker / Evaluator pair**. One agent produces; another validates. 
**Self-review is a cognitive trap for both humans and LLMs.**

### Worker Agent (Engineer)
*   **CLAIM** before starting any task
*   **WORKING heartbeat** every ~5 min on long tasks
*   Write **TODO.md Release Notes FIRST**, then post RELEASE event
*   Wait for QA response via `--wait-for BUG,DELIVER`
*   Max 3 BUG cycles, then post BLOCKED and escalate

### Evaluator Agent (QA)
*   **REVIEWING** before starting review (prevents duplicate QA)
*   Read **TODO.md Release Notes** before testing
*   Write **QA.md bug table FIRST**, then post BUG event
*   Test against **PLAN.md AC**, not personal preference

> QA never invents requirements. Scope creep kills velocity.

---

## 06. English as the Embedding Layer
When writing context consumed by an LLM — **write in English**. 
*   **Training data density**: ~70–80% of most LLM pretraining corpora is English.
*   **Token efficiency**: 1 English word ≈ 1–1.5 tokens (vs. 2-4 tokens for other languages).
*   **Instruction following**: Highest benchmark scores.
*   **Code alignment**: Code is written in English; context matches code natively.

All PLAN.md, CONTEXT.md, SKILL.md, AC, and DoD must be written in **English**. User-facing content can be localized.

---

## 07. Domain-Driven Design & TDD for Agents

### Domain-Driven Design (DDD)
*   **Ubiquitous Language**: A shared vocabulary between engineers, agents, and domain experts.
*   **Bounded Context**: Each feature context folder = one bounded context.
*   **Aggregates**: Group related entities that change together.
*   **Domain Events**: ROOM.jsonl is your event bus (`RELEASE`, `BUG`, `DELIVER`).

### Test-Driven Development (TDD) for Agent Tasks
Supervisor writes Acceptance Criteria (the "test") in PLAN.md → Engineer implements until AC passes → QA runs AC as literal test cases → DELIVER only when all AC are green.

**GIVEN / WHEN / THEN is the lingua franca of AC.**
```text
AC-1: GIVEN valid userId and cartId
      WHEN  PaymentSession.create() is called
      THEN  returns a unique SessionId AND persists to DB
```

---

## 08. The EPIC Planning Standard
The EPIC is the primary source of truth. The EPIC is the spec, the test, and the contract between human intent and machine execution.

### The Canonical EPIC Format
```markdown
## EPIC-001 - {Outcome Statement}
Roles:        @engineer, @qa, @devops
# One-paragraph definition of the business problem and the goal. (Pyramid Principle)

### Definition of Done
- [ ] All Acceptance Criteria pass (QA verified)
- [ ] No HIGH or CRITICAL bugs open
- [ ] Unit test coverage ≥ 80% for new code
- [ ] CONTEXT.md updated to reflect completion
- [ ] Deployed to staging and smoke-tested

### Acceptance Criteria
- [ ] AC-1: GIVEN {precondition} WHEN {action} THEN {expected result}
- [ ] AC-2: GIVEN {precondition} WHEN {action} THEN {expected result}

### Tasks
- [ ] Task 1: {technical deliverable} — [routing-tag]
- [ ] Task 2: {technical deliverable} — [routing-tag]

depends_on: [EPIC-000]
```

### EPIC Quality Checklist
*   Has a unique `EPIC-{NNN}` ID.
*   Outcome statement is one sentence (BLUF).
*   Roles are explicitly listed.
*   IN/OUT scope is explicit.
*   DoD is a binary checklist.
*   Every task has ≥2 AC in `GIVEN/WHEN/THEN` format.
*   Tasks have routing tags (`[backend]`, `[frontend]`).
*   `depends_on` is declared.

---

## 09. Agentic Ops: Best Practices
Agents fail differently than humans. They hallucinate silently, get stuck in loops, or produce plausible-looking but wrong output.

### The Five Pillars of Agentic Ops
1. **Observable**: Every action is posted to ROOM.jsonl. 
2. **Bounded**: Agents operate within scoped MCP servers.
3. **Recoverable**: All context files are append-only.
4. **Heartbeated**: Long-running agents post WORKING events every ~5 min.
5. **Escalating**: Max 3 BUG cycles. On cycle 4, post BLOCKED and escalate to Supervisor.

> **The File-First Rule:** Always write your file completely *before* posting the ROOM event. File first. Event second. Always.

---

## 10. Code Quality = Context Quality

Everything converges on a single, non-negotiable truth:
**The quality of the AI's code is entirely determined by the quality of the EPICs, Definitions of Done, and Acceptance Criteria.**

### The 2-22 Framework
*   **Invest 2 hours:** Human writes precise EPIC, AC, DoD, CONTEXT.md, seeds the ROOM.
*   **Unlock 22 hours:** Agents execute, loop, validate, and ship — autonomously, correctly.

Every technique in this playbook serves one purpose: **to make your context so precise that the agent cannot fail to understand what you want.** That is the craft of agentic engineering.