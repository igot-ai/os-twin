---
name: scope-investigation
description: Use this skill to define the boundaries of a risk investigation using the DEPT framework before commissioning analytical work from a data analyst.
tags: [audit, risk-officer, scoping, investigation, data-analyst-handoff]

---

# scope-investigation

## Overview

Before asking a single analytical question, the Risk Officer must define the investigation boundaries — which data domain, which time period, which entity population, and which risk theme. This skill produces a structured **scope request** that a data analyst can act on immediately, preventing the two most common failures: analysis too broad to be actionable, and analysis too narrow to catch systemic issues.

## When to Use

- When starting any new risk investigation or audit engagement
- When a `task` message arrives requiring data analysis commissioning
- When refining an investigation after initial findings suggest broader patterns
- Before invoking the `structure-data-request` skill


## Instructions

### 1. Apply the DEPT Framework

Every investigation begins with four scoping decisions:

**D — Domain:** Which business process or data domain?

| Domain | Examples |
|--------|----------|
| Expenditure | Vendor payments, procurement, capital projects |
| Revenue | Leases, rental income, service charges, percentage rent |
| Assets | Property valuations, depreciation, impairment |
| Personnel | Payroll, commissions, related-party relationships |
| Compliance | Regulatory filings, contractual obligations, escalation clauses |

**E — Entity Population:** Full population, risk-based subset, or specific target?

- **Full population** — all entities (e.g., all vendor payments, all leases)
- **Risk-based subset** — filtered by risk indicator (e.g., payments > $25K, retail leases only)
- **Specific target** — named entity investigation (e.g., only Vendor X, only Property Y)

**P — Period:** What timeframe produces the most meaningful analysis?

- **Point-in-time** — current state snapshot
- **Period** — bounded date range (e.g., Q1 2025)
- **Trend** — comparative (month-over-month, year-over-year)
- **Longitudinal** — full lifecycle from inception to present

**T — Theme:** What risk hypothesis is being tested?

- **Fraud** — fictitious vendors, duplicate payments, kickback schemes
- **Leakage** — below-market revenue, missed escalations, uncollected rent
- **Governance** — approval bypasses, segregation of duties, related-party conflicts
- **Operational** — process delays, data integrity errors, system misconfigurations

### 2. Write the Scope Statement

Compose a single clear paragraph combining all four DEPT elements. This paragraph must be specific enough that a data analyst can begin work immediately without asking clarifying questions.

**Good example:**
> "Analyze all vendor payments in Q1 2025 for threshold-splitting patterns, grouped by approver, with prior-year baseline for comparison."

**Bad example:**
> "Can you check if our vendor payments look okay?"

### 3. Define Scope Boundaries

Explicitly state what is **included** and what is **excluded**:

```markdown
## Scope Boundaries
- **Included:** [entities, domains, timeframes within scope]
- **Excluded:** [what is deliberately out of scope and why]
- **Expansion trigger:** [condition that would warrant broadening the scope]
```

### 4. Produce the Scope Request Artifact

Save a `scope-request.md` in the war-room artifacts directory:

```markdown
# Scope Request — [Investigation Title]

## DEPT Parameters
| Element | Decision |
|---------|----------|
| Domain | [selected domain] |
| Entity Population | [full / subset / target — with criteria] |
| Period | [timeframe type and specific dates] |
| Theme | [risk hypothesis] |

## Scope Statement
[Single paragraph — the analyst's starting brief]

## Boundaries
- **Included:** ...
- **Excluded:** ...
- **Expansion trigger:** ...

## Next Step
→ Apply analytical lenses (see: `analytical-lenses`)
→ Structure the data request (see: `structure-data-request`)
```

## Handoff to Data Analyst

The `scope-request.md` is consumed by the `structure-data-request` skill to compose the formal `task` message sent to the data analyst. The scope request itself is **not** sent directly — it is an intermediate artifact that ensures the Risk Officer has thought through boundaries before formulating specific questions.

**If the scope needs revision** after receiving data analyst output, re-invoke this skill with updated DEPT parameters rather than informally expanding the request.

## Verification

After producing the scope request:
1. All four DEPT elements are explicitly defined
2. The scope statement is specific enough for immediate analyst action
3. Boundaries include both inclusions and exclusions
4. An expansion trigger is defined for scope creep control
