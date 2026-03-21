---
name: data-visualization
description: Use this skill to create charts and visual components — bar charts, pie charts, metrics cards, and timelines with proper data formatting and labeling.
tags: [reporter, data-visualization, charts, metrics]
trust_level: core
---

# data-visualization

## Overview

This skill guides you through creating effective data visualizations for reports. It covers data preparation, component selection, and the formatting rules for each visual component type.

## When to Use

- When a report brief requires charts, graphs, or visual data
- When aggregating metrics into KPI cards
- When building timelines or roadmap visualizations
- When choosing between chart types for a given dataset

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Chart specs | JSON (pages array entries) | Part of `report-spec.json` |

## Instructions

### 1. Choose the Right Visualization

| Data Pattern | Best Component | When |
|-------------|---------------|------|
| Single values with trends | `metrics` | KPIs, summary stats, headline numbers |
| Categories with values | `bar_chart` | Comparisons, rankings, distributions |
| Parts of a whole | `pie_chart` | Market share, composition, budget allocation |
| Sequential events | `timeline` | Roadmaps, milestones, project history |
| Structured records | `data_table` | Detailed data, multi-column comparisons |
| Color values | `color_palette` | Brand documentation |
| Font specimens | `typography` | Brand documentation |
| Pass/fail items | `checklist` | Compliance, do's and don'ts |

### 2. Metrics Cards

For headline numbers with context:

```json
{
  "type": "metrics",
  "heading": "Key Performance Indicators",
  "cards": [
    {
      "label": "Monthly Revenue",
      "value": "$1.2M",
      "trend": "+15%"
    },
    {
      "label": "Active Users",
      "value": "42,000",
      "trend": "+8%"
    },
    {
      "label": "Error Rate",
      "value": "0.3%",
      "trend": "-12%"
    }
  ]
}
```

**Rules:**
- `value` — formatted with units, commas, currency symbols
- `trend` — always include `+` or `-` prefix and `%` suffix
- Keep to 3–4 cards per row for readability
- Use consistent units within a metrics group

### 3. Bar Charts

For comparing values across categories:

```json
{
  "type": "bar_chart",
  "heading": "Revenue by Region",
  "data": {
    "labels": ["North America", "Europe", "Asia Pacific", "Latin America"],
    "values": [450000, 320000, 280000, 150000]
  }
}
```

**Rules:**
- Labels must be concise (abbreviate if > 15 characters)
- Sort by value (descending) unless there's a logical order
- Maximum 8–10 bars per chart for readability
- Include a descriptive heading

### 4. Pie Charts

For showing proportions:

```json
{
  "type": "pie_chart",
  "heading": "Market Share Distribution",
  "data": {
    "labels": ["Product A", "Product B", "Product C", "Other"],
    "values": [45, 25, 20, 10]
  }
}
```

**Rules:**
- Values should sum to 100 (percentages) or a meaningful total
- Maximum 6 segments — group small values into "Other"
- Largest segment first, then descending
- Labels must be distinct and meaningful

### 5. Timeline

For sequential events:

```json
{
  "type": "timeline",
  "heading": "Project Roadmap",
  "events": [
    {
      "date": "2025-Q1",
      "title": "Phase 1 — Foundation",
      "description": "Core architecture and data model"
    },
    {
      "date": "2025-Q2",
      "title": "Phase 2 — Features",
      "description": "User-facing features and API"
    },
    {
      "date": "2025-Q3",
      "title": "Phase 3 — Launch",
      "description": "Public beta and marketing push"
    }
  ]
}
```

**Rules:**
- Events must be in chronological order
- Date format should be consistent (all YYYY-MM-DD or all YYYY-QN)
- Keep descriptions under 2 lines
- Maximum 8–10 events per timeline

### 6. Data Tables

For structured, multi-dimensional data:

```json
{
  "type": "data_table",
  "heading": "Sprint Summary",
  "columns": ["Epic", "Status", "Story Points", "Completion"],
  "rows": [
    ["EPIC-001", "Passed", "13", "100%"],
    ["EPIC-002", "In Progress", "8", "60%"],
    ["EPIC-003", "Pending", "5", "0%"]
  ]
}
```

**Rules:**
- Always include column headers
- Align numbers to the right conceptually (the engine handles formatting)
- Sort by the most important column
- Maximum 20 rows per table — paginate if necessary

### 7. Data Preparation

Before creating visualizations, clean and format the raw data:

```python
# Example: aggregate metrics from war-room data
import json

rooms = [json.load(open(f)) for f in room_files]
metrics = {
    "total_epics": len(rooms),
    "passed": sum(1 for r in rooms if r["state"] == "passed"),
    "failed": sum(1 for r in rooms if r["state"] == "failed-final"),
    "pass_rate": f"{passed / total * 100:.0f}%"
}
```

**Principles:**
- Round numbers appropriately (no `0.33333333...`)
- Use consistent units and formatting
- Include totals or averages where meaningful
- Handle missing data explicitly (show "N/A", not empty cells)

## Verification

After creating visualizations:
1. Each chart type matches the data pattern it represents
2. All values are properly formatted with units
3. Labels are concise and meaningful
4. Charts have descriptive headings
5. No more than the recommended number of segments/bars/rows
