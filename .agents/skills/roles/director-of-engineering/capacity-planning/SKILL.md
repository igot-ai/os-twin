---
name: capacity-planning
description: Model team capacity against committed work to prevent overcommitment, identify slack for absorption, and plan for known disruptions like oncall rotations, tech debt sprints, and leaves. Produces capacity forecasts with risk indicators.
---

# capacity-planning

## Purpose

Overcommitted teams produce low-quality work, burn out, and miss deadlines. This skill provides a structured approach to modeling capacity and preventing the #1 cause of project failure in big organizations: promising more than teams can deliver.

## Capacity Model

### Step 1 — Calculate Raw Capacity

```
Raw capacity = Team size × Sprint days × Hours per day
```

### Step 2 — Apply Availability Factors

| Factor | Typical Reduction |
|--------|------------------|
| Meetings & ceremonies | -15% |
| Oncall rotation | -10% per person on rotation |
| Planned leave | Actual days |
| Context switching | -10% per concurrent project |
| Unplanned work (bugs, incidents) | -15% |
| Tech debt / maintenance | -10% |

```
Effective capacity = Raw capacity × (1 - sum of reduction factors)
```

### Step 3 — Compare to Committed Work

```markdown
## Capacity Forecast — [Team/Room]

| Metric | Value |
|--------|-------|
| Raw capacity | X person-days |
| Effective capacity | Y person-days |
| Committed work | Z person-days |
| **Utilization** | **Z/Y = N%** |

### Health Indicator
| Utilization | Status | Action |
|-------------|--------|--------|
| < 70% | 🟢 Healthy slack | Can absorb spillover |
| 70–85% | 🟡 Optimal | Sustainable pace |
| 85–100% | 🟠 At risk | No room for surprises |
| > 100% | 🔴 Overcommitted | **Must cut scope or add capacity** |
```

### Step 4 — Forecast Risks

- What happens if a key engineer is unavailable for 2 weeks?
- What happens if the upstream dependency is 1 sprint late?
- What happens if a production incident consumes 3 days?

## Planning Horizons

| Horizon | Accuracy | Purpose |
|---------|----------|---------|
| This sprint | ±10% | Execution confidence |
| Next sprint | ±25% | Commitment planning |
| This quarter | ±40% | Resource allocation |
| Next quarter | ±60% | Headcount planning |

## Anti-Patterns

- Planning at 100% utilization → zero slack means any surprise causes a miss
- Ignoring context-switching cost → 3 projects at 33% each ≠ 1 project at 100%
- Not accounting for oncall → oncall engineers are not available for project work
- Planning with averages → averages hide dangerous variance
- Not revisiting the plan → capacity plans must be updated weekly
