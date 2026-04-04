---
name: design-review
description: Use this skill to review a QA-escalated failure for architectural compliance — produce design guidance with a FIX, REDESIGN, or REPLAN verdict.
tags: [architect, review, design, escalation]
trust_level: core
---

# design-review

## Overview

This skill guides the architect through reviewing a failure that was escalated by QA or triaged by the manager as a `design-issue`. The output is a `design-guidance.md` with a clear recommendation: **FIX**, **REDESIGN**, or **REPLAN**.

## When to Use

- When the manager routes a `design-review` message to the architect
- When a war-room enters the `architect-review` state
- When QA escalates with classification `DESIGN` or `SCOPE`

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Design guidance | Markdown | `<war-room>/design-guidance.md` |
| Guidance message | Channel | `design-guidance` message |

## Instructions

### 1. Gather Context

Read the following artifacts in order:
1. **`brief.md`** — original epic/task requirements
2. **`triage-context.md`** — manager's classification and QA feedback
3. **`qa-report.md`** — QA's specific findings
4. **Engineer's `done` message** — what was actually built
5. **Source code** — the current implementation

### 2. Analyze the Root Cause

Determine whether the failure is:

| Category | Symptoms | Typical Root Cause |
|----------|----------|--------------------|
| **Implementation Bug** | Code doesn't match spec, logic errors | Wrong code, right design |
| **Design Flaw** | Right code, wrong architecture | Interface mismatch, wrong abstractions |
| **Scope Gap** | Feature incomplete, missing requirements | Brief is inadequate or contradictory |

### 3. Evaluate Architectural Compliance

- [ ] Does the implementation follow project architectural patterns?
- [ ] Are module boundaries correct?
- [ ] Are interfaces well-defined and minimal?
- [ ] Is the data flow logical and efficient?
- [ ] Are there separation-of-concerns violations?
- [ ] Does the design scale for future requirements?

### 4. Formulate Recommendation

| Verdict | When | Next State |
|---------|------|-----------|
| **FIX** | Implementation bug, design is sound | → `fixing` → `engineering` |
| **REDESIGN** | Design flaw, but scope is correct | → `fixing` with new design spec → `engineering` |
| **REPLAN** | Requirements gap, brief needs updating | → `plan-revision` → update `brief.md` → `engineering` |

### 5. Write design-guidance.md

```markdown
# Design Guidance — EPIC/TASK-XXX

> Architect: architect
> Date: <YYYY-MM-DD>
> Verdict: FIX / REDESIGN / REPLAN

## Context
<what was escalated and why>

## Analysis
<root cause analysis — what went wrong architecturally>

## Recommendation

### Verdict: <FIX / REDESIGN / REPLAN>

<detailed explanation of what should change>

### Implementation Sketch (if REDESIGN)
```
<pseudocode or diagram of the new design>
```

### Brief Updates (if REPLAN)
The following changes to `brief.md` are needed:
- <change 1>
- <change 2>

## Consequences
- **Positive:** <what this fixes>
- **Risk:** <what could still go wrong>
- **Effort estimate:** <small / medium / large>
```

### 6. Post to Channel

Post a `design-guidance` message with the verdict and a summary of the recommendation.

## Verification

After providing design guidance:
1. `design-guidance.md` exists in the war-room
2. Verdict is one of: FIX, REDESIGN, REPLAN
3. Recommendation includes actionable implementation steps
4. If REPLAN: specific `brief.md` changes are listed
