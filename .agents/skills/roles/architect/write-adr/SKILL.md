---
name: write-adr
description: Use this skill to write an Architecture Decision Record — document context, options, decision rationale, and consequences for key technical choices."
tags: [architect, documentation, adr, technical-decisions]
: core
---

# write-adr

## Overview

This skill guides you through writing a standalone Architecture Decision Record (ADR). ADRs capture **why** a technical decision was made, not just what was decided. They serve as a searchable history of architectural choices.

## When to Use

- When making a significant technical decision (new framework, data model, API design)
- When the `create-architecture` skill is too broad — you just need one focused ADR
- When recording a decision made during a design review or triage
- When a later engineer asks "why was it built this way?"

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| ADR document | Markdown | `<war-room>/architecture/adr-NNN.md` or project-level `docs/adr/` |

## Instructions

### 1. Determine the ADR Number

Check existing ADRs and use the next sequential number:

```bash
ls <target-dir>/adr-*.md 2>/dev/null | sort | tail -1
```

If no ADRs exist, start with `adr-001.md`.

### 2. Fill in the ADR Template

Create `adr-<NNN>.md`:

```markdown
# ADR-<NNN>: <Title — A Short Imperative Statement>

> Status: proposed | accepted | deprecated | superseded
> Date: <YYYY-MM-DD>
> Epic: <EPIC-XXX> (if applicable)
> Supersedes: <ADR-XXX> (if applicable)

## Context

<What is the problem or decision to be made?
Include:
- Business/technical requirements driving this
- Constraints (time, budget, team skills, existing tech)
- Forces at play (scalability, security, maintainability)>

## Options Considered

### Option A — <Name>
- **Description:** <how it works>
- **Pros:** <advantages>
- **Cons:** <disadvantages>
- **Effort:** <small / medium / large>

### Option B — <Name>
- **Description:** <how it works>
- **Pros:** <advantages>
- **Cons:** <disadvantages>
- **Effort:** <small / medium / large>

### Option C — <Name> (if applicable)
- ...

## Decision

We chose **Option <X>** because <rationale>.

<Explain WHY this option was chosen over others.
Reference specific forces/constraints that tipped the balance.>

## Consequences

- **Positive:** <what improves as a result>
- **Negative:** <trade-offs we accept>
- **Risks:** <what could go wrong, and mitigations>
- **Technical Debt:** <any debt introduced, with plan to address>

## Follow-up Actions

- [ ] <action item 1 — e.g., implement the chosen approach>
- [ ] <action item 2 — e.g., update related documentation>
- [ ] <action item 3 — e.g., set up monitoring for the risk>
```

### 3. ADR Quality Checklist

Before finalizing:
- [ ] Title is a short, imperative statement (e.g., "Use PostgreSQL for User Data")
- [ ] Context explains the problem clearly to someone unfamiliar
- [ ] At least 2 options are considered with honest pros/cons
- [ ] Decision rationale explains **why**, not just **what**
- [ ] Consequences are realistic and include risks
- [ ] Follow-up actions are concrete and assignable

### 4. Link the ADR

If related to an epic, reference the ADR in:
- `brief.md` — under a "Related Decisions" section
- `architecture/components.md` — if the ADR affects component design
- Other ADRs — use "Supersedes" or "Related to" references

## Verification

After writing the ADR:
1. ADR file exists with the correct sequential number
2. All template sections are filled in (no placeholders remaining)
3. At least 2 options were genuinely considered
4. Decision rationale is clear and defensible
5. Follow-up actions have `[ ]` checkboxes
