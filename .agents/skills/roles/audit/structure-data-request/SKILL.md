---
name: structure-data-request
description: Use this skill to compose a formal, structured data request using the DATA template and send it as a task message to the data analyst via the war-room channel.
tags: [audit, risk-officer, data-request, data-analyst-handoff, war-room]
: core
---

# structure-data-request

## Overview

This is the **primary handoff skill** between the Risk Officer (audit) and the Data Analyst. It translates scoped questions into a structured request following the DATA template (Define, Articulate, Timeline, Audience), then sends it as a war-room `task` message that the data analyst can execute without ambiguity.

## When to Use

- After `scope-investigation` and `analytical-lenses` have produced the scope and questions
- When commissioning any analytical work from a data analyst role
- When re-requesting after validating output with `validate-output`

## Prerequisites

- `scope-request.md` from `scope-investigation`
- `analysis-questions.md` from `analytical-lenses`

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Data request spec | JSON | `<war-room>/artifacts/data-request.json` |
| Task message | War-room message | Channel `task` message to data analyst |

## Instructions

### 1. Apply the DATA Template

For each question from `analysis-questions.md`, structure the request:

**D — Define the output:** What exactly should the deliverable look like?

| Output Type | When to Use |
|-------------|-------------|
| Table | Ranked lists, exception reports, comparison matrices |
| Visualization | Distributions, trends, scatter plots, heat maps |
| Profile | Entity-level dossier with narrative and data |
| Dashboard | Ongoing monitoring with drill-down capability |

Specify: rows, columns, sort order, summary totals, chart type, axes, reference lines, segmentation.

**A — Articulate the logic:** What is the analytical test?

- The calculation or formula (plain language, not code)
- The comparison benchmark (policy threshold, market rate, historical average, peer group)
- The exception criteria (what triggers a flag, at what severity level)
- Edge cases: nulls, new entities with no history, data quality issues

**T — Timeline and cadence:** When is it needed?

| Cadence | Delivery |
|---------|----------|
| One-time | Deadline + review meeting date |
| Periodic | Monthly/quarterly + specific delivery dates |
| Continuous | Real-time with alert routing and escalation protocols |

**A — Audience and action:** Who consumes this, and what decision will it inform?

| Audience | Format |
|----------|--------|
| Audit Committee | Executive summary, quantified exposure, recommendations |
| Risk Officer | Detailed exception list, supporting evidence, investigation leads |
| Operational Management | Actionable items, responsible parties, resolution timelines |

### 2. Compose the Data Request Spec

Build the JSON artifact:

```json
{
  "request_id": "<INVESTIGATION-ID>-<SEQ>",
  "title": "<descriptive title>",
  "scope_ref": "scope-request.md",
  "questions_ref": "analysis-questions.md",
  "requests": [
    {
      "question_id": "Q1",
      "define_output": {
        "type": "table | visualization | profile | dashboard",
        "format": "<specific format description>",
        "sort_order": "<field, direction>",
        "summary_required": true
      },
      "articulate_logic": {
        "calculation": "<plain language formula>",
        "benchmark": "<comparison standard>",
        "flag_criteria": "<what triggers exception>",
        "severity_levels": {
          "red": "<threshold>",
          "amber": "<threshold>",
          "green": "<threshold>"
        },
        "edge_cases": "<null handling, new entity rules>"
      },
      "timeline": {
        "cadence": "one-time | periodic | continuous",
        "deadline": "<date or SLA>",
        "convert_to_monitoring": "<condition for making recurring>"
      },
      "audience": {
        "primary": "<role>",
        "escalation": "<condition> → <escalation target>",
        "confidentiality": "standard | restricted | confidential"
      }
    }
  ]
}
```

### 3. Post the Task Message to Data Analyst

Send via war-room channel using the `task` message type:

```json
{
  "from_role": "audit",
  "type": "task",
  "epic": "<INVESTIGATION-ID>",
  "body": "## Data Analysis Request — <title>\n\n### Scope\n<scope statement from scope-request.md>\n\n### Request 1: <Q1 title>\n**Output:** <define_output summary>\n**Logic:** <articulate_logic summary>\n**Deadline:** <timeline>\n**Audience:** <audience>\n\n### Request 2: <Q2 title>\n...\n\n### Artifacts\n- Full spec: `artifacts/data-request.json`\n- Scope: `artifacts/scope-request.md`\n- Questions: `artifacts/analysis-questions.md`"
}
```

### 4. Monitor Progress

Read progress from the data analyst's channel messages:

```python
# Check for progress updates
messages = read_messages(from_role="data-analyst")
progress = [m for m in messages if m["type"] == "progress"]
```

When the analyst posts a `done` message, hand off to the `validate-output` skill.

## Consuming Data Analyst Output

When the data analyst posts a `done` message:

```json
{
  "from_role": "data-analyst",
  "type": "done",
  "body": "## Analysis Complete — <request_id>\n- **Output:** <path to artifact>\n- **Findings:** <summary>\n- **Data quality notes:** <any issues encountered>"
}
```

→ Invoke the `validate-output` skill to review the deliverable before acting on it.

## Verification

Before sending the task message:
1. Every request has all four DATA elements filled (Define, Articulate, Timeline, Audience)
2. No placeholder text remains — all fields are specific
3. Edge case handling is defined for each calculation
4. The data-request.json artifact is saved in the war-room
5. The task message includes references to all supporting artifacts
