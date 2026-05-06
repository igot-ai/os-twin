---
name: analytical-lenses
description: Use this skill to select the right analytical lens (Distribution, Deviation, Relationship, Temporality, Compounding) and formulate precise questions for the data analyst. 
---

# analytical-lenses

## Overview

Every dataset can be interrogated from multiple angles. A Risk Officer who relies on a single lens — typically "find the policy violations" — misses the majority of insight. This skill teaches five distinct analytical lenses, each producing a different type of risk intelligence, and formats the resulting questions as structured requests a data analyst can execute.

## When to Use

- After `scope-investigation` has defined the DEPT parameters
- When formulating the specific analytical questions for the data analyst
- When initial analysis results require follow-up from a different angle
- When building compound risk profiles that layer multiple lenses

## Prerequisites

- A completed `scope-request.md` from the `scope-investigation` skill

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Analysis questions | Markdown | `<war-room>/artifacts/analysis-questions.md` |

## Instructions

### 1. Select the Appropriate Lens(es)

Choose one or more lenses based on the risk theme from your scope request:

| Lens | Core Question | Best For |
|------|--------------|----------|
| **Distribution** | What does the shape of the data tell us? | Detecting clusters, gaps, outliers near thresholds |
| **Deviation** | What breaks the expected pattern? | Comparing actual vs. benchmark (policy, market, budget) |
| **Relationship** | Who is connected to whom? | Conflict of interest, collusion, entity networks |
| **Temporality** | What does the timeline reveal? | Weekend activity, period-end spikes, accelerating frequency |
| **Compounding** | What happens when multiple indicators converge? | Prioritizing highest-risk entities across all flags |

### 2. Formulate Questions Using Templates

#### Lens 1: Distribution

> "Plot the frequency distribution of `[metric]` across the full `[entity]` population. Highlight any unnatural clusters, gaps, or concentrations — particularly near control thresholds."

> "What is the standard deviation of `[metric]` by `[grouping variable]`? Which groups have the tightest clustering, and which have the widest spread?"

> "Show me the percentile distribution of `[metric]`. Which entities fall below the 10th or above the 90th percentile?"

#### Lens 2: Deviation

> "For each `[entity]`, calculate the variance between `[actual metric]` and `[benchmark metric]`. Rank by absolute variance, largest first."

> "Which `[entities]` deviate by more than `[X%]` from the `[benchmark]`? For each, provide the dollar impact over the `[period]`."

> "Compare each `[entity]`'s current `[metric]` against its own historical average. Flag any entity where the current period deviates by more than 2 standard deviations."

#### Lens 3: Relationship

> "Cross-reference all unique names in `[Dataset A field]` with all unique names in `[Dataset B field]`. Flag any exact or partial matches."

> "For each `[entity]`, map every transaction they're connected to. Produce a network summary: number of connections, total dollar value, distinct counterparties."

> "Identify every instance where the same individual appears in more than one role across our data."

#### Lens 4: Temporality

> "Plot the daily/weekly/monthly volume and value of `[transactions]` over `[period]`. Overlay significant dates. Are there spikes or trend shifts?"

> "For each `[entity]`, calculate the average days between `[event A]` and `[event B]`. Flag intervals exceeding `[X days]` or below `[Y days]`."

> "Segment all transactions by day-of-week. For weekend transactions, is there a secondary pattern — same approver, same method, same vendor?"

#### Lens 5: Compounding

> "For each `[entity]`, count the total number of distinct anomaly flags triggered. Rank by flag count. For entities with 3+ flags, produce a one-page risk profile."

> "Create a risk matrix: rows = `[entities]`, columns = `[anomaly types]`. Sum each row for a composite risk score. Sort descending."

> "Identify any entity that appears as an anomaly across both `[Dataset 1]` and `[Dataset 2]`."

### 3. Layer Lenses for Depth

Single-lens analysis reveals surface issues. Layered analysis reveals systemic risk:

```
Step 1: Distribution   → Identify clustering near thresholds
Step 2: Deviation      → Quantify how far anomalies deviate from baseline
Step 3: Relationship   → Map which people/entities are connected
Step 4: Temporality    → Check timing patterns of connected anomalies
Step 5: Compounding    → Score and rank entities by total flag count
```

### 4. Write the Analysis Questions Artifact

Save `analysis-questions.md`:

```markdown
# Analysis Questions — [Investigation Title]

## Scope Reference
→ See: `scope-request.md`

## Selected Lenses
1. [Lens name] — [rationale for selection]
2. [Lens name] — [rationale for selection]

## Questions

### Q1 — [Lens]: [Short title]
> [Full question text using template, with all placeholders filled]
**Expected output:** [table / chart / profile / dashboard]
**Benchmark:** [policy threshold / market rate / historical average]

### Q2 — [Lens]: [Short title]
> [Full question text]
**Expected output:** ...
**Benchmark:** ...

## Layering Strategy
[How these lenses connect — what Q1 output feeds into Q2, etc.]
```

## Handoff to Data Analyst

These questions are **not** sent directly to the data analyst. They feed into the `structure-data-request` skill, which wraps them in the formal DATA template (Define output, Articulate logic, Timeline, Audience) as a war-room `task` message.

**Cross-reference:** Use questions from the `question-library` skill as a starting point.

## Verification

After formulating analysis questions:
1. At least two different lenses are applied to the same dataset
2. Every question has filled placeholders — no `[entity]` or `[metric]` left generic
3. Expected output format is specified for each question
4. A benchmark or baseline is defined for every deviation or comparison question
5. The layering strategy explains how questions build on each other
