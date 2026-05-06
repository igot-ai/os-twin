---
name: define-slo
description: Define Service Level Objectives and error budgets for production services. Produces measurable SLO documents with SLI definitions, budget calculations, alerting thresholds, and escalation policies when budgets are at risk.
---

# define-slo

## Purpose

SLOs make reliability measurable. Without them, "is the service reliable enough?" is an opinion. With them, it's a number.

## SLO Components

### SLI (Service Level Indicator)
The metric that measures reliability:
- **Availability:** Successful requests / total requests
- **Latency:** % of requests completing within threshold (e.g., p99 < 200ms)
- **Correctness:** % of responses that return the right answer
- **Freshness:** % of data updated within threshold

### SLO (Service Level Objective)
The target for the SLI:
- Example: "99.9% of requests succeed over a rolling 30-day window"

### Error Budget
The allowed unreliability:
- 99.9% SLO = 0.1% error budget = 43.8 minutes/month

## SLO Document Template

```markdown
# SLO: [Service Name]

**Owner:** [team/room]
**Last reviewed:** [date]
**Review cadence:** Monthly

## Service Description
[What this service does and who depends on it]

## SLIs and SLOs

| SLI | Measurement | SLO Target | Window |
|-----|-------------|-----------|--------|
| Availability | success / total | 99.9% | 30-day rolling |
| Latency (p50) | response time | < 100ms | 30-day rolling |
| Latency (p99) | response time | < 500ms | 30-day rolling |
| Correctness | correct / total | 99.99% | 30-day rolling |

## Error Budget

| SLO | Budget (monthly) | Budget (quarterly) |
|-----|------------------|-------------------|
| 99.9% availability | 43.8 min downtime | 131.4 min downtime |
| 99.9% availability | 8,640 failed requests per 8.64M | |

## Budget Consumption Policy

| Budget Remaining | Action |
|-----------------|--------|
| > 50% | Normal feature development |
| 25–50% | Prioritize reliability work |
| < 25% | Feature freeze — reliability only |
| 0% (exhausted) | All hands on reliability until budget resets |

## Alerting

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| SLO warning | Budget burn rate > 2x normal | P2 | Investigate |
| SLO critical | Budget burn rate > 10x normal | P1 | Incident response |
| Budget exhausted | 0% remaining | P0 | Feature freeze |

## Dependencies
[Other services this SLO depends on]
```

## Anti-Patterns

- SLOs without measurement → if you can't measure the SLI, the SLO is fiction
- SLOs of 100% → nothing is 100% reliable; this creates an impossible standard
- SLOs that never change → review and adjust quarterly based on actual performance
- Error budgets without enforcement → if budget exhaustion doesn't trigger action, it's not a budget
