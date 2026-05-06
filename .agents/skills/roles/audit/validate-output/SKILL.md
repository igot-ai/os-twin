---
name: validate-output
description: Use this skill to pressure-test data analyst output using the Five Validation Questions before acting on findings.
tags: [audit, risk-officer, validation, quality-gate, data-analyst-handoff]

---

# validate-output

## Overview

The Risk Officer is the quality gate between raw analytical output and risk decisions. Accepting output uncritically is as dangerous as not requesting analysis at all. This skill applies the Five Validation Questions to every data analyst deliverable before it informs any risk decision or report.

## When to Use

- When a data analyst posts a `done` message with analysis results
- Before invoking the `risk-decision` skill on any finding
- When deciding whether to accept results or request revision

## Prerequisites

- A `done` message from the data analyst containing analytical output
- The original `data-request.json` from `structure-data-request`

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Revision request (if needed) | War-room message | Channel `revision-request` message |

## Instructions

### 1. Apply the Five Validation Questions

For every analytical deliverable, work through each question in order:

#### Q1: "What's excluded?"

Every analysis has a scope boundary. Identify what fell outside it:

- Could the pattern span a boundary the analyst didn't cross? (fiscal year, entity type, payment channel)
- Were any entities excluded due to data quality issues?
- Did the analyst scope match your original `scope-request.md`?

**Document:** What was excluded and whether it matters.

#### Q2: "What's the false positive rate?"

How many flagged items are genuine issues vs. explainable exceptions?

- What percentage of flagged items did the analyst spot-check?
- Does the detection rule flag too much of the population (>30% is usually noise)?
- Should the rule be tightened by adding secondary criteria?

**Document:** Estimated false positive rate and whether rule tuning is needed.

#### Q3: "What's the baseline?"

Anomalies are only anomalous relative to something:

- What is the normal range for this metric?
- Is the flagged behavior actually unusual, or standard for this entity type?
- Was a baseline provided, and is it appropriate?

**Document:** Whether the baseline is adequate and if results are genuinely anomalous.

#### Q4: "Can you show me the opposite?"

Counter confirmation bias by examining the inverse:

- If anomalous entities show pattern X, do non-anomalous entities also show it?
- What makes the "normal" transactions different from the flagged ones?
- Does the pattern hold after controlling for volume, entity type, or seasonal effects?

**Document:** Whether the counter-analysis supports or weakens the finding.

#### Q5: "What would change this conclusion?"

Identify the assumptions baked into every finding:

- What data quality issues could invalidate the result?
- If benchmark data is outdated, does the conclusion still hold?
- After adjusting for volume or context, does the pattern persist?

**Document:** Key assumptions and their sensitivity to change.

### 2. Produce the Validation Assessment

Save `validation-assessment.md`:

```markdown
# Validation Assessment — [Request ID]

## Deliverable Reviewed
- **From:** [data analyst role]
- **Request:** [data-request reference]
- **Output:** [path to analyst deliverable]

## Validation Results

| Question | Finding | Impact |
|----------|---------|--------|
| What's excluded? | [answer] | [none / low / high] |
| False positive rate? | [estimated %] | [acceptable / needs tuning] |
| Baseline adequate? | [yes / no — why] | [finding valid / uncertain] |
| Counter-analysis? | [supports / weakens] | [strengthens / weakens conclusion] |
| Assumption sensitivity? | [key assumptions] | [robust / fragile] |

## Verdict
**[ACCEPT / REVISE / EXPAND]**

### If ACCEPT:
→ Proceed to `risk-decision` skill with validated findings

### If REVISE:
→ Specific revision needed: [description]
→ Post revision-request to data analyst

### If EXPAND:
→ Scope expansion needed: [new DEPT parameters]
→ Re-invoke `scope-investigation` with broader scope
```

### 3. Post Verdict to Channel

**If ACCEPT — route to risk-decision:**

No channel message needed. Invoke `risk-decision` skill directly with the validated findings.

**If REVISE — post revision request to data analyst:**

```json
{
  "from_role": "audit",
  "type": "revision-request",
  "epic": "<INVESTIGATION-ID>",
  "body": "## Revision Request — <request_id>\n\n### Original Request\n<reference to original task message>\n\n### Validation Issue\n<which validation question failed and why>\n\n### Specific Revision\n<what needs to change — tighter rule, different baseline, excluded data, counter-analysis>\n\n### Updated Deadline\n<revised timeline>"
}
```

**If EXPAND — return to scoping:**

Re-invoke `scope-investigation` with updated DEPT parameters and document the expansion rationale.

## Consuming Data Analyst Output

Parse the data analyst's `done` message for:
- **Output path** — where the deliverable artifact is stored
- **Findings summary** — high-level results
- **Data quality notes** — any issues the analyst encountered during processing
- **Methodology notes** — any deviations from the requested logic

## Verification

After completing validation:
1. All five validation questions are documented with specific answers
2. The verdict is one of: ACCEPT, REVISE, or EXPAND
3. If REVISE, the revision-request message specifies exactly what needs to change
4. If EXPAND, new DEPT parameters are defined
5. The validation-assessment.md artifact is saved in the war-room
