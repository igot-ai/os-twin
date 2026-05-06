---
name: risk-register
description: Maintain a living risk register with probability and impact scoring, mitigation plans, risk owners, and regular review cadence. Produces prioritized risk dashboards that drive proactive management rather than reactive firefighting.
---

# risk-register

## Purpose

Risk registers prevent surprises. By identifying, scoring, and mitigating risks proactively, the program manager converts "unknown unknowns" into "known knowns" with plans.

## Risk Scoring Matrix

### Probability

| Score | Label | Meaning |
|-------|-------|---------|
| 5 | Almost Certain | > 90% chance |
| 4 | Likely | 60–90% chance |
| 3 | Possible | 30–60% chance |
| 2 | Unlikely | 10–30% chance |
| 1 | Rare | < 10% chance |

### Impact

| Score | Label | Timeline | Quality | Cost |
|-------|-------|----------|---------|------|
| 5 | Severe | > 1 month delay | Major feature cut | > 50% budget overrun |
| 4 | Major | 2–4 week delay | Feature degradation | 25–50% overrun |
| 3 | Moderate | 1–2 week delay | Minor feature impact | 10–25% overrun |
| 2 | Minor | < 1 week delay | Cosmetic impact | < 10% overrun |
| 1 | Negligible | No delay | No quality impact | Within budget |

### Risk Level = Probability × Impact

| Level | Score Range | Action |
|-------|-----------|--------|
| 🔴 Critical | 15–25 | Immediate mitigation, escalate to director |
| 🟠 High | 10–14 | Active mitigation, weekly review |
| 🟡 Medium | 5–9 | Monitor, mitigation plan ready |
| 🟢 Low | 1–4 | Accept and monitor |

## Risk Register Template

```markdown
# Risk Register — [Program Name]

**Updated:** [date]
**Next review:** [date]

| ID | Risk | Prob | Impact | Score | Level | Owner | Mitigation | Status |
|----|------|------|--------|-------|-------|-------|-----------|--------|
| R-001 | [description] | 3 | 4 | 12 | 🟠 | [who] | [plan] | Open |
| R-002 | [description] | 2 | 5 | 10 | 🟠 | [who] | [plan] | Mitigating |
| R-003 | [description] | 4 | 2 | 8 | 🟡 | [who] | [plan] | Monitoring |

## Risk Trends
| ID | Last Score | Current Score | Trend |
|----|-----------|--------------|-------|
| R-001 | 12 | 12 | → Stable |
| R-002 | 15 | 10 | ↓ Improving |

## Closed Risks
| ID | Risk | Resolved | How |
|----|------|----------|-----|
| R-010 | [description] | [date] | [outcome] |
```

## Risk Categories

- **Technical** — architecture won't support requirements, performance issues
- **Resource** — key person unavailable, team overcommitted
- **Dependency** — external dependency delayed or cancelled
- **Scope** — requirements unclear or expanding
- **External** — vendor, compliance, market changes

## Anti-Patterns

- Risks without owners → unowned risks don't get mitigated
- Static register → risks change weekly; the register must be living
- Only tracking negative risks → opportunities (positive risks) should be tracked too
- Mitigation plans that are just "hope" → "we'll deal with it if it happens" is not mitigation
