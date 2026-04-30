---
name: runbook-authoring
description: Write operational runbooks for production services covering common failure modes, diagnostic steps, remediation procedures, and escalation paths. Produces executable, tested documentation that enables any oncall engineer to resolve known issues.
---

# runbook-authoring

## Purpose

Runbooks capture institutional knowledge about how to operate a service. A good runbook means any engineer can handle a 3am incident — not just the person who built the system.

## Runbook Template

```markdown
# Runbook: [Service] — [Failure Scenario]

**Service:** [name]
**Last tested:** [date]
**Author:** [who]
**Oncall team:** [team]

## Symptom
[What does this look like? What alert fires? What do users see?]

## Impact
[Who is affected? What functionality is degraded?]

## Diagnostic Steps

1. Check [specific dashboard URL]
2. Run: `[diagnostic command]`
3. Expected output: [what healthy looks like]
4. If unhealthy: [what the output shows]

## Remediation

### Option A: [Quick fix — e.g., restart]
1. Run: `[command]`
2. Verify: [how to confirm it worked]
3. Expected recovery time: [X minutes]

### Option B: [If Option A fails — e.g., rollback]
1. Run: `[command]`
2. Verify: [how to confirm it worked]
3. Expected recovery time: [X minutes]

### Option C: [Nuclear option — e.g., failover]
1. Run: `[command]`
2. Verify: [how to confirm it worked]
3. Expected recovery time: [X minutes]
4. Side effects: [what else is affected]

## Escalation
If none of the above work:
- Escalate to: [who — name or role]
- Include: [what information to provide]
- Via: [channel — Slack, PagerDuty, phone]

## Post-Resolution
1. Verify service is healthy: [check]
2. Check for data inconsistencies: [check]
3. Update incident record
4. Schedule RCA if S1/S2
```

## Runbook Quality Criteria

- [ ] Any oncall engineer can follow this without prior knowledge
- [ ] Commands are copy-pasteable (no placeholders without explanation)
- [ ] Each step has expected output / success criteria
- [ ] Escalation path is clear and current
- [ ] Tested within the last quarter

## Anti-Patterns

- Runbooks that say "ask [person name]" → people change teams; runbooks must be self-contained
- Untested runbooks → test quarterly; an untested runbook might be wrong
- Missing diagnostic steps → jumping to remediation without diagnosis can make things worse
- No escalation path → every runbook must end with "if all else fails, escalate to X"
