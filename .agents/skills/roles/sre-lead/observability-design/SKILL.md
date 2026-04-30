---
name: observability-design
description: Design monitoring, alerting, dashboards, and distributed tracing strategies for production services. Ensures every service is observable with actionable alerts, meaningful dashboards, and traceable request flows.
---

# observability-design

## Purpose

You can't fix what you can't see. Observability is the foundation of reliability — it enables detection, diagnosis, and resolution of production issues.

## The Three Pillars

### 1. Metrics (What is happening?)
- **RED metrics** for request-driven services: Rate, Errors, Duration
- **USE metrics** for infrastructure: Utilization, Saturation, Errors
- **Business metrics**: conversions, sign-ups, revenue-impacting events

### 2. Logs (Why is it happening?)
- Structured logs (JSON format)
- Correlation IDs across services
- Log levels used correctly (ERROR = action needed, WARN = investigate, INFO = context, DEBUG = development)

### 3. Traces (Where is it happening?)
- Distributed tracing across service boundaries
- Trace sampling strategy (100% for errors, 1–10% for success)
- Span annotations for business context

## Alerting Design Principles

### Alert Quality Criteria
Every alert must be:
- **Actionable** — receiving this alert means you must DO something
- **Relevant** — routes to the team that can fix it
- **Timely** — fires fast enough to prevent user impact
- **Deduplicated** — one alert per issue, not 50 copies

### Alert Severity

| Severity | Response | Pages? | Example |
|----------|----------|--------|---------|
| Critical | Immediate | Yes | SLO burn rate 10x |
| Warning | Within 1 hour | No | SLO burn rate 2x |
| Info | Review next business day | No | Deployment completed |

### Alert Anti-Patterns
- Alert on every error → creates noise; alert on error RATE thresholds
- Alert without runbook → alert recipients need to know what to do
- Alerts that can't be silenced → maintenance windows exist; alerts should respect them

## Dashboard Design

### Golden Signals Dashboard (every service)
1. **Request rate** — is traffic normal?
2. **Error rate** — are errors within budget?
3. **Latency** — are p50, p95, p99 within SLO?
4. **Saturation** — are resources (CPU, memory, connections) approaching limits?

### Dashboard Rules
- Every dashboard has a title, description, and owner
- Time ranges default to last 24 hours
- Include comparison to previous period
- Mark SLO thresholds on graphs

## Anti-Patterns

- Monitoring everything → focus on the golden signals; more metrics ≠ more observability
- Dashboard graveyards → dashboards nobody looks at should be deleted
- Alert fatigue → noisy alerts train people to ignore all alerts
- Missing correlation IDs → without them, tracing requests across services is impossible
