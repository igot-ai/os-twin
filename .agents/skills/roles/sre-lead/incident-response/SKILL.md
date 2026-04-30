---
name: incident-response
description: Run structured incident response following detect-triage-mitigate-resolve-RCA lifecycle. Produces incident records, coordinates responders, and ensures blameless post-mortems with actionable follow-up items.
---

# incident-response

## Purpose

When production breaks, every minute counts. This skill provides a structured incident response framework that minimizes time-to-recovery and ensures every incident produces learning.

## Incident Severity

| Severity | Impact | Response Time | Example |
|----------|--------|---------------|---------|
| S1 | Service fully down, data loss risk | < 15 min | Database corruption, total outage |
| S2 | Major degradation, workaround exists | < 30 min | 50% error rate, payment failures |
| S3 | Minor degradation, limited impact | < 2 hours | Slow queries, partial feature broken |
| S4 | Cosmetic or non-impacting | < 1 day | UI glitch, log noise |

## Incident Response Lifecycle

### 1. DETECT
- Monitoring alert fires, or user report received
- Validate the alert is real (not a false positive)
- Open an incident record

### 2. TRIAGE
- Classify severity (S1–S4)
- Identify affected services and users
- Assemble response team based on severity
- Assign Incident Commander (IC)

### 3. MITIGATE
**Priority: Restore service FIRST, investigate LATER**
- Rollback recent deployment?
- Scale up infrastructure?
- Enable feature flag / circuit breaker?
- Route traffic to backup?
- Communicate status to stakeholders

### 4. RESOLVE
- Identify root cause
- Deploy fix
- Verify fix in production
- Monitor for recurrence

### 5. RCA (Root Cause Analysis)
Within 48 hours, produce a blameless post-mortem:

```markdown
# Incident Post-Mortem: INC-XXXX

**Date:** [date]
**Duration:** [start to resolution]
**Severity:** S[X]
**Impact:** [what broke, who was affected, for how long]
**IC:** [who led response]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | IC assigned |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Full resolution |

## Root Cause
[What actually broke and why — blameless, focused on systems not people]

## Contributing Factors
- [Factor 1: e.g., missing monitoring for X]
- [Factor 2: e.g., no circuit breaker on Y]

## What Went Well
- [Thing 1: fast detection]
- [Thing 2: clear escalation]

## What Went Poorly
- [Thing 1: slow rollback due to missing runbook]

## Action Items
| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| P0 | [prevent recurrence] | [who] | [when] |
| P1 | [improve detection] | [who] | [when] |
| P2 | [update runbook] | [who] | [when] |
```

## Anti-Patterns

- Investigating before mitigating → restore service first, find root cause second
- Blaming individuals → systems fail, not people; blameless post-mortems are mandatory
- No follow-up on action items → unresolved action items mean the same incident will recur
- Skipping RCA for S3/S4 → small incidents reveal systemic issues
