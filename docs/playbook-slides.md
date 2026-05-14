---
marp: true
theme: default
class: invert
paginate: true
---

# Agentic Engineering Playbook
## Build Agents That Actually Ship
A field guide for engineers working in an AI-first SDLC.
*Based on the iGOT.AI EPIC Format*

---

# The Core Thesis
**Code Quality = Context Quality**

The quality of the AI's code is entirely determined by the quality of the EPICs, Definitions of Done, and Acceptance Criteria.
*Not the model. Not the framework. The context.*

**The 2-22 Framework:**
Invest **2 hours** in context quality (EPIC, AC, DoD, CONTEXT.md) to unlock **22 hours** of correct autonomous agent productivity.

---

# 1. The Pyramid Principle
**Lead with your conclusion, then prove it.**

- **BLUF** (Bottom Line Up Front): First sentence = the task/decision.
- **MECE** (Mutually Exclusive, Collectively Exhaustive): No overlap or gaps in criteria.
- **Rule of 3**: Group support into ≤3 clusters.

*Why?* LLMs process context top-to-bottom. If the conclusion is at the bottom, the agent makes decisions before knowing the goal.

---

# 2. Prompt-Driven Context
**In agentic systems, your context is the source code.**

- **System Layer**: `SKILL.md`, `ROLE.md` (Session init)
- **Planning Layer**: `PLAN.md`, `CONTEXT.md` (Task start)
- **Execution Layer**: `TODO.md`, `QA.md` (Review & handoff)

*Context Degradation*: Agents drift over time. Solve this with **structured context resets** at the start of every session, not by blaming the model.

---

# 3. Context Engineering
**Designing the information environment for an agent's mind.**

Four Properties of Good Context:
1. **Bounded**: One context per feature.
2. **Current**: Reflects actual state, not intended state.
3. **Append-only**: History is never deleted.
4. **Role-scoped**: Each agent owns exactly one file.

---

# 4. MCP & Skills
**MCP** (Model Context Protocol) composes capabilities dynamically like a package manager for tools.
**Skills** (`SKILL.md`) instruct an agent *how* to use those tools.

- Keep skills single-purpose.
- Lead with trigger conditions.
- Include worked examples.
- **Role-Based Access**: MCP servers are scoped by role (e.g., Engineer gets rw filesystem; Supervisor gets read-only).

---

# 5. Roles: Worker & Evaluator
**Self-review is a cognitive trap for humans and LLMs.**

- **Worker (Engineer)**: Claims tasks, implements, writes `TODO.md` release notes, posts `RELEASE` event.
- **Evaluator (QA)**: Reviews against Acceptance Criteria, writes `QA.md`, posts `BUG` or `DELIVER`.

*The Contract:* QA never invents requirements. Scope creep kills velocity.

---

# 6. English as Embedding Layer
**Write context in English.**

- 70-80% of LLM training data is English.
- Highest token efficiency (1 word ≈ 1-1.5 tokens).
- Highest instruction-following compliance.
- Matches the language of code and RLHF alignment.

*Rule:* User-facing content can be localized. Agent context is ALWAYS English.

---

# 7. DDD & TDD for Agents
- **Domain-Driven Design (DDD)**: Use a **Ubiquitous Language**. Every term in `PLAN.md` must match the code domain model precisely.
- **Test-Driven Development (TDD)**: Write Acceptance Criteria *before* engineering starts.
  - **GIVEN / WHEN / THEN** format is the lingua franca of AC.
  - QA agents can parse this directly into test cases.

---

# 8. The EPIC Planning Standard
**The EPIC is the spec, the test, and the contract.**

1. **Outcome Statement**: One-line business result (Pyramid Principle).
2. **Roles**: Who participates.
3. **Definition of Done (DoD)**: Binary phase exit gates.
4. **Acceptance Criteria (AC)**: Per-task GIVEN/WHEN/THEN tests.
5. **Tasks**: Atomic deliverables with routing tags (e.g., `[backend]`).
6. **depends_on**: Explicit dependency graph for parallel execution.

---

# 9. Agentic Ops Best Practices
**Agents fail differently than humans. They hallucinate silently.**

The 5 Pillars of Agentic Ops:
1. **Observable**: Every action posted to `ROOM.jsonl`.
2. **Bounded**: Scoped MCP access.
3. **Recoverable**: Append-only context.
4. **Heartbeated**: `WORKING` events every 5 mins.
5. **Escalating**: Max 3 `BUG` cycles, then `BLOCKED`.

***The File-First Rule:*** Write your file completely before posting the ROOM event.

---

# Summary
Every technique in this playbook serves one purpose: **to make your context so precise that the agent cannot fail to understand what you want.**

That is the craft of agentic engineering.
