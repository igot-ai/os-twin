---
name: okr-alignment
description: Define and cascade OKRs (Objectives and Key Results) from organizational level down to team and war-room level. Ensures every team's work maps to business objectives with measurable key results, no gaps, and no overlaps.
---

# okr-alignment

## Purpose

OKRs prevent the most expensive problem in big organizations: teams building things that don't matter. This skill produces structured OKR cascades that connect every war-room's work to business outcomes.

## OKR Cascade Process

### Step 1 — Receive Company Objectives

Input: Company-level objectives (typically 3–5 per quarter)

### Step 2 — Decompose into Engineering Objectives

For each company objective, ask:
- What engineering work directly enables this objective?
- What infrastructure/platform work is a prerequisite?
- What technical debt, if unaddressed, would block this objective?

### Step 3 — Assign to War-Rooms

For each engineering objective, define 2–4 key results:
- **Measurable** — includes a number or yes/no
- **Time-bound** — achievable within the quarter
- **Owned** — assigned to a specific war-room
- **Verifiable** — can be independently confirmed

## OKR Template

```markdown
## Objective: [Clear, inspiring statement]
**Owner:** [war-room or team name]
**Quarter:** Q[X] [Year]

### Key Results

| KR# | Key Result | Metric | Current | Target | Owner |
|-----|-----------|--------|---------|--------|-------|
| 1 | [specific result] | [metric] | [baseline] | [goal] | [room] |
| 2 | [specific result] | [metric] | [baseline] | [goal] | [room] |
| 3 | [specific result] | [metric] | [baseline] | [goal] | [room] |

### Dependencies
- [KR1 depends on Room X completing Y]
- [KR2 requires infrastructure Z from platform-engineer]

### Risks
- [Risk 1: mitigation plan]
```

## Scoring (End of Quarter)

| Score | Meaning |
|-------|---------|
| 0.0–0.3 | Failed — significant miss |
| 0.4–0.6 | Partial — some progress but fell short |
| 0.7–0.9 | Successful — strong delivery |
| 1.0 | Perfect — either a win or the target was too easy |

**Ideal average score: 0.6–0.7** — if teams consistently score 1.0, the OKRs are too easy.

## Anti-Patterns

- OKRs that are just task lists → key results must be outcomes, not outputs
- Every team has the same OKRs → defeats the purpose of alignment
- Too many OKRs per team → 3 objectives max, 3–4 KRs each
- OKRs that can't be measured → if you can't tell if it's done, it's not a KR
- Setting OKRs and never checking → monthly check-ins are mandatory
