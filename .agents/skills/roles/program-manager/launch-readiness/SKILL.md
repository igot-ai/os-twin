---
name: launch-readiness
description: Run structured launch readiness reviews (LRR) to verify all workstreams are prepared for a major release. Produces go/no-go checklists, risk assessments, rollback plans, and success criteria definitions.
---

# launch-readiness

## Purpose

Launch readiness reviews prevent "we shipped but forgot X" disasters. This skill provides a structured checklist that ensures every workstream has completed its pre-launch requirements.

## Launch Readiness Checklist

```markdown
# Launch Readiness Review — [Feature/Release]

**Date:** [date]
**Ship date:** [date]
**Decision maker:** [who decides go/no-go]
**Verdict:** 🟢 GO | 🟡 GO with conditions | 🔴 NO-GO

## Workstream Readiness

### Engineering
- [ ] All planned features are code-complete
- [ ] All P0/P1 bugs are resolved
- [ ] Code has been reviewed and approved
- [ ] Feature flags are configured for gradual rollout

### Quality
- [ ] All test suites pass
- [ ] Performance benchmarks meet SLOs
- [ ] Security review is complete
- [ ] Regression testing is complete

### SRE / Operations
- [ ] SLOs are defined for new features
- [ ] Monitoring and alerting are configured
- [ ] Runbooks are written and tested
- [ ] Rollback procedure is documented and tested
- [ ] On-call team is briefed

### Documentation
- [ ] User-facing documentation is updated
- [ ] API documentation is updated
- [ ] Internal architecture docs are current
- [ ] Release notes are drafted

### Stakeholders
- [ ] Product owner has approved
- [ ] Legal/compliance has approved (if applicable)
- [ ] Support team is briefed
- [ ] Marketing materials are ready (if applicable)

## Risk Assessment at Launch

| Risk | Probability | Impact | Mitigation |
|------|------------ |--------|-----------|
| [risk] | H/M/L | H/M/L | [plan] |

## Rollback Plan

**Trigger:** [what conditions trigger a rollback]
**Method:** [how to roll back — feature flag, deploy previous version, etc.]
**Timeline:** [how long rollback takes]
**Data impact:** [any data migration concerns]
**Decision maker:** [who decides to roll back]

## Success Criteria (T+24h, T+7d, T+30d)

| Timeframe | Metric | Target | Measurement |
|-----------|--------|--------|-------------|
| T+24h | Error rate | < 0.1% | [dashboard] |
| T+7d | User adoption | > X% | [analytics] |
| T+30d | Performance | p99 < Xms | [dashboard] |

## Go/No-Go Decision

**Verdict:** [GO / NO-GO]
**Conditions (if conditional GO):** [what must happen before ship]
**Reasoning:** [why]
```

## Anti-Patterns

- Skipping LRR because "we're behind schedule" → launching unprepared costs more than a short delay
- LRR as a formality → if everything is always green, you're not looking hard enough
- No rollback plan → if you can't undo the launch, you can't launch safely
- No success criteria → without them, you can't tell if the launch succeeded
