---
name: chaos-engineering
description: Design and evaluate chaos experiments to test system resilience against real-world failure scenarios. Produces experiment plans with hypotheses, blast radius controls, abort conditions, and results analysis.
---

# chaos-engineering

## Purpose

Chaos engineering answers the question: "Will our system survive failure X?" Instead of waiting for production to surprise us, we inject controlled failures and observe the results.

## Chaos Experiment Framework

### Step 1 — Hypothesis

Define what you expect to happen:

```markdown
**Hypothesis:** When [failure scenario], the system will [expected behavior] because [resilience mechanism].

Example: "When the primary database becomes unreachable for 30 seconds, the application will serve cached data with < 5% error rate because the read-through cache and circuit breaker are configured."
```

### Step 2 — Experiment Design

```markdown
## Chaos Experiment: [Name]

**Target service:** [service]
**Failure type:** [network, compute, storage, dependency]
**Injection method:** [tool/technique]

### Blast Radius Controls
- **Scope:** [% of traffic, specific instance, single AZ]
- **Duration:** [max time for injection]
- **Abort conditions:** [when to immediately stop]
  - Error rate > [X]%
  - Latency p99 > [Y]ms
  - Any S1 alert fires

### Measurements
- Error rate before, during, after
- Latency percentiles before, during, after
- Recovery time after injection stops
- User-visible impact

### Prerequisites
- [ ] Runbook exists for this failure mode
- [ ] Monitoring is in place for affected metrics
- [ ] Team is aware and standing by
- [ ] Abort mechanism is tested
```

### Step 3 — Execute

1. Baseline: Record current system metrics
2. Inject: Apply the failure
3. Observe: Monitor all measurements
4. Abort if: Any abort condition is met
5. Recover: Remove the failure injection
6. Stabilize: Verify system returns to baseline

### Step 4 — Analyze Results

```markdown
## Results

**Hypothesis confirmed?** Yes | Partially | No

| Metric | Baseline | During Chaos | After Recovery |
|--------|----------|-------------|----------------|
| Error rate | X% | Y% | Z% |
| Latency p99 | Xms | Yms | Zms |
| Recovery time | N/A | N/A | N seconds |

### Findings
- [What worked as expected]
- [What didn't work as expected]
- [New failure modes discovered]

### Actions
| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| P[X] | [fix resilience gap] | [who] | [when] |
```

## Common Experiment Types

| Experiment | What it tests |
|-----------|---------------|
| Kill a service instance | Auto-scaling and load balancing |
| Add network latency | Timeout configuration and circuit breakers |
| Block a dependency | Fallback and graceful degradation |
| Fill disk | Disk pressure handling and alerting |
| CPU stress | Throttling behavior and autoscaling triggers |
| DNS failure | Service discovery resilience |

## Anti-Patterns

- Running chaos in production without blast radius controls → chaos, not engineering
- No hypothesis → injecting failures randomly doesn't produce learnings
- Never running chaos → you will discover your resilience gaps in production at 3am instead
- Not fixing findings → chaos experiments that produce action items nobody follows up on
