---
name: risk-decision
description: Use this skill to convert validated analytical findings into one of four decision categories (Accept, Mitigate, Investigate, Escalate) and produce a Risk Decision Record."
tags: [audit, risk-officer, decision-making, risk-management, governance]
trust_level: core
---

# risk-decision

## Overview

Analysis without action is academic exercise. This skill converts validated findings into one of four decision categories -- Accept, Mitigate, Investigate, or Escalate -- and produces a formal Risk Decision Record that documents the reasoning, financial exposure, and required actions.

## When to Use

- After `validate-output` produces an ACCEPT verdict on analytical findings
- When converting any validated risk finding into an organizational action
- When quantifying financial exposure for audit committee reporting

## Prerequisites

- Validated findings from `validate-output` (verdict = ACCEPT)
- Original `data-request.json` for context
- `validation-assessment.md` confirming data quality

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Risk Decision Record | Markdown | `<war-room>/artifacts/risk-decision-record.md` |
| Escalation message (if applicable) | War-room message | Channel `escalate` message |

## Instructions

### 1. Assess the Finding Against Decision Categories

Apply each category's criteria to the validated finding:

#### ACCEPT -- Risk is within appetite

**Criteria:**
- Risk is understood and quantified
- Financial exposure is within defined tolerance
- No pattern of recurrence or systemic concern
- Existing controls are adequate

**Required actions:** Document the decision. Set a monitoring trigger for re-evaluation.

**Example:** Weekend payments represent 20% of transactions but only 8% of dollar volume, with no co-occurring anomaly flags. Accept as normal treasury operations. Re-evaluate if weekend value exceeds 15% of total.

#### MITIGATE -- Control improvement can reduce the risk

**Criteria:**
- Risk exceeds appetite but is controllable
- A specific control change can reduce the exposure
- The cost of mitigation is proportionate to the risk

**Required actions:** Define the control change, responsible owner, implementation timeline, and success metric.

**Example:** Threshold-splitting pattern detected. Mitigation: system-level control blocking >3 payments within 10% of threshold per 30-day window. Owner: IT + Finance. Timeline: 60 days. Success metric: zero clustering in following quarter.

#### INVESTIGATE -- Deeper examination needed before deciding

**Criteria:**
- Findings suggest potential fraud, collusion, or material misstatement
- Current evidence is insufficient to determine root cause
- The finding could be explainable but requires verification

**Required actions:** Define investigation scope, lead investigator, timeline, and confidentiality requirements.

**Example:** Cross-dataset entity match reveals same individual approves vendor payments and holds a below-market lease. Engage forensic audit, review conflict-of-interest disclosures, restrict access to CRO/CAE/General Counsel.

#### ESCALATE -- Immediate senior authority required

**Criteria:**
- Material financial exposure requiring executive attention
- Potential regulatory or legal implications
- Finding that could affect publicly reported figures
- Evidence of deliberate misconduct

**Required actions:** Immediate notification to designated authority, potential payment freeze or access restriction.

**Example:** $447,500 in potentially unauthorized expenditure across two vendors with no PO, no budget, and weekend processing. Escalate to CFO and Audit Committee with recommendation for immediate payment freeze.

### 2. Quantify Financial Exposure

For every finding, calculate exposure before writing the narrative:

| Exposure Type | Calculation |
|---------------|-------------|
| Direct loss | Known amount already lost or misappropriated |
| Projected loss | Current rate  remaining exposure period |
| Opportunity cost | Revenue gap  remaining contract/lease term |
| Range estimate | Best case to worst case if uncertainty exists |

### 3. Produce the Risk Decision Record

Save `risk-decision-record.md`:

```markdown
# Risk Decision Record

| Field | Value |
|-------|-------|
| Finding Reference | [Rule ID + Transaction/Lease IDs] |
| Date of Decision | [YYYY-MM-DD] |
| Decision Category | [Accept / Mitigate / Investigate / Escalate] |

## Summary of Finding
[2-3 sentences: what was detected, in which data, affecting which entities]

## Financial Exposure
| Type | Amount | Period |
|------|--------|--------|
| [Direct / Projected / Opportunity / Range] | $[amount] | [timeframe] |

## Root Cause Assessment
[1-2 sentences: control gap, governance failure, data issue, or deliberate act]

## Decision Rationale
[Why this category was chosen over the alternatives]

## Required Actions
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [specific step] | [name/role] | [date] | [ ] Pending |

## Monitoring Trigger
[Condition that would cause this decision to be revisited]

## Decision Authority
[Name and title of decision maker]
```

### 4. Post Channel Messages (if applicable)

**If ESCALATE:**

```json
{
  "from_role": "audit",
  "type": "escalate",
  "epic": "<INVESTIGATION-ID>",
  "body": "## Escalation -- <finding reference>\n\n### Finding\n<summary>\n\n### Financial Exposure\n$<amount> -- <type>\n\n### Recommended Immediate Action\n<freeze / restrict / notify>\n\n### Escalation Target\n<CFO / Audit Committee / General Counsel>"
}
```

**If INVESTIGATE:**

Post a new `task` message via `structure-data-request` to commission deeper forensic analysis from the data analyst.

## Verification

After producing the risk decision:
1. The decision category is explicitly justified against alternatives
2. Financial exposure is quantified with a specific dollar amount or range
3. Required actions have named owners and deadlines
4. A monitoring trigger is set for re-evaluation
5. For ESCALATE decisions, the channel message is posted immediately
