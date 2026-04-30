---
name: escalation-routing
description: Classify and route escalations to the correct role based on type — technical issues to principal-engineer, process issues to program-manager, reliability issues to sre-lead, and organizational issues handled directly. Prevents escalation pile-up and ensures timely resolution.
---

# escalation-routing

## Purpose

In a large org, escalations are inevitable. The director's job is not to solve every escalation — it's to route each one to the person best equipped to resolve it, track resolution, and prevent escalation pile-up.

## Escalation Classification

| Type | Signals | Route to |
|------|---------|----------|
| **Technical** | Architecture disagreement, technology choice, design flaw | `principal-engineer` |
| **Process** | Missed deadlines, unclear requirements, blocked dependencies | `program-manager` |
| **Reliability** | Production incident, SLO breach, performance degradation | `sre-lead` |
| **Security** | Vulnerability discovered, compliance gap, data breach risk | `security-engineer` |
| **Quality** | Recurring bugs, test coverage gaps, QA/engineer friction | `staff-manager` |
| **People** | Skill gap, workload imbalance, team friction | Handle directly |

## Escalation Severity

| Severity | Response Time | Examples |
|----------|--------------|---------|
| **S1 — Critical** | < 1 hour | Production down, data breach, security incident |
| **S2 — High** | < 4 hours | SLO breach, blocked release, critical bug |
| **S3 — Medium** | < 1 day | Cross-team dependency block, process breakdown |
| **S4 — Low** | < 1 week | Tool request, process improvement suggestion |

## Routing Process

```markdown
## Escalation: [Title]

**From:** [who escalated]
**Severity:** S1 | S2 | S3 | S4
**Type:** Technical | Process | Reliability | Security | Quality | People
**Routed to:** [role]
**Context:** [what happened, what was tried, what's the impact]
**Expected resolution:** [what "resolved" looks like]
**Deadline:** [based on severity]
**Status:** Open | In Progress | Resolved | Closed
```

## Follow-Up Protocol

1. **Acknowledge** the escalation within the response time for its severity
2. **Route** to the appropriate role with full context
3. **Track** resolution progress daily for S1/S2, weekly for S3/S4
4. **Close** only when the escalator confirms the issue is resolved
5. **Post-mortem** for any S1 — why did it escalate? How do we prevent recurrence?

## Anti-Patterns

- Solving every escalation yourself → you become the bottleneck
- Routing without context → the recipient wastes time gathering information you already had
- Not tracking resolution → escalations that disappear into the void erode trust
- Ignoring patterns → 3 escalations about the same service = systemic issue
