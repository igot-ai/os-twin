---
name: threat-modeling
description: Conduct STRIDE/DREAD threat models for new features and system changes. Identifies assets, threat actors, attack vectors, and mitigations before code is written. Produces structured threat model documents with risk ratings and security requirements.
---

# threat-modeling

## Purpose

Threat modeling answers: "What can go wrong?" before it goes wrong. By identifying threats during design, we prevent security vulnerabilities from being coded in.

## STRIDE Threat Categories

| Category | Threat | Example |
|----------|--------|---------|
| **S**poofing | Pretending to be someone else | Stolen credentials, session hijacking |
| **T**ampering | Modifying data or code | SQL injection, man-in-the-middle |
| **R**epudiation | Denying an action | Missing audit logs |
| **I**nformation Disclosure | Exposing private data | API leaking PII, verbose errors |
| **D**enial of Service | Making service unavailable | Resource exhaustion, DDoS |
| **E**levation of Privilege | Gaining unauthorized access | Privilege escalation, IDOR |

## DREAD Risk Rating

| Factor | 1 (Low) | 5 (Medium) | 10 (High) |
|--------|---------|-----------|-----------|
| **D**amage | Minor data exposure | Significant data loss | Complete system compromise |
| **R**eproducibility | Hard to reproduce | Requires specific conditions | Always reproducible |
| **E**xploitability | Requires expertise | Moderate skill | Script kiddie can do it |
| **A**ffected users | Single user | Subset of users | All users |
| **D**iscoverability | Requires insider knowledge | Discoverable with effort | Publicly known |

**Risk score = (D + R + E + A + D) / 5**

## Threat Model Template

```markdown
# Threat Model: [Feature/System Name]

**Author:** security-engineer
**Date:** [date]
**Status:** Draft | In Review | Accepted

## System Description
[What the system does, data flows, trust boundaries]

## Assets
| Asset | Classification | Owner |
|-------|---------------|-------|
| User credentials | Confidential | Auth team |
| Payment data | Restricted | Payments team |

## Trust Boundaries
[Where do trust levels change? e.g., client→server, service→database]

## Threat Analysis

### T-001: [Threat Name]
- **Category:** [STRIDE]
- **Description:** [How the attack works]
- **DREAD Score:** [D:? R:? E:? A:? D:? = Avg:?]
- **Risk Level:** Critical | High | Medium | Low
- **Mitigation:** [How to prevent or detect]
- **Status:** Mitigated | Accepted | Open

## Security Requirements
[Derived from the threat analysis — what the implementation MUST include]

## Residual Risks
[Threats that are accepted with documented rationale]
```

## When to Threat Model

- New features that handle user data
- Changes to authentication or authorization
- New API endpoints
- Changes to data storage or processing
- Integration with external services
- Infrastructure changes

## Anti-Patterns

- Threat modeling after the code is written → it's a design activity, not a review activity
- Modeling every tiny change → focus on features with security implications
- Generic threats without context → "SQL injection is possible" is unhelpful; specify WHERE and HOW
- No mitigations → identifying threats without defining how to address them is incomplete
