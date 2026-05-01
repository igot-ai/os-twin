---
name: dependency-mapping
description: Map and visualize cross-team and cross-room dependencies to identify critical paths, bottlenecks, circular dependencies, and at-risk deliverables. Produces dependency graphs with status tracking and early warning for blocked chains.
---

# dependency-mapping

## Purpose

Cross-team dependencies are where programs fail. This skill makes dependencies visible, tracked, and actionable — before they become blocks.

## Dependency Types

| Type | Risk Level | Example |
|------|-----------|---------|
| **Hard** — cannot proceed without | 🔴 High | API endpoint must exist before consumer can integrate |
| **Soft** — can work around temporarily | 🟡 Medium | Documentation needed but can use drafts |
| **Information** — need answer, not deliverable | 🟢 Low | Need to know data format, can mock meanwhile |

## Dependency Record Template

```markdown
## Dependency: [ID]

**Consumer:** [room that needs it]
**Producer:** [room that provides it]
**Deliverable:** [what is needed]
**Type:** Hard | Soft | Information
**Status:** Committed | In Progress | At Risk | Blocked | Delivered
**Needed by:** [date]
**Committed for:** [date]
**Gap:** [days between needed and committed, if any]
```

## Dependency Matrix

```markdown
| Consumer ↓ / Producer → | Room A | Room B | Room C | Platform |
|------------------------|--------|--------|--------|----------|
| Room A | — | DEP-01 🟢 | | DEP-04 🟡 |
| Room B | DEP-02 🔴 | — | DEP-03 🟢 | |
| Room C | | | — | DEP-05 🟢 |
```

## Critical Chain Analysis

1. List all hard dependencies
2. Sort by "needed by" date
3. Identify chains: if DEP-01 blocks DEP-02 which blocks DEP-03
4. The longest chain = the critical path for the program
5. Any delay in the critical chain delays the program

## Early Warning System

| Warning | Trigger | Action |
|---------|---------|--------|
| ⚠️ Gap detected | Committed date > needed date | Negotiate earlier delivery or consumer workaround |
| ⚠️ Status change | Moved from "on track" to "at risk" | Escalate to both teams' managers |
| 🔴 Blocked chain | Hard dependency in critical chain is blocked | Escalate to director-of-engineering |
| 🔄 Circular | A depends on B depends on A | Architectural redesign needed |

## Anti-Patterns

- Dependencies tracked in someone's head → they must be visible and written
- Dependencies without committed dates → "we'll get to it" is not a commitment
- Assuming soft dependencies are risk-free → soft dependencies can become hard late in the program
- Not tracking information dependencies → "I assumed the format would be X" causes integration failures
