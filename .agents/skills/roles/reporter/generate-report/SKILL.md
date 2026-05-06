---
name: generate-report
description: Use this skill to compose a full report spec from a brief — gather data, build pages using available components, and render to PDF.
tags: [reporter, pdf, report-generation, document-composition]

---

# generate-report

## Overview

This skill guides the reporter through the complete report generation workflow — from reading a brief to delivering a rendered PDF. It covers data gathering, spec composition, component selection, and engine invocation.

## When to Use

- When assigned a report generation task in a war-room
- When a `task` message arrives requiring a PDF deliverable
- When composing a status report, audit report, sprint summary, or brand guide

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Report spec | JSON | `<war-room>/artifacts/report-spec.json` |
| Generated PDF | PDF | `<war-room>/artifacts/<report-name>.pdf` |

## Instructions

### 1. Read the Brief

Extract from `brief.md`:
- **Report type** — status, audit, brand, QA summary, sprint, data analysis
- **Data sources** — files, APIs, aggregated metrics
- **Audience** — executives, engineers, clients
- **Tone** — formal, technical, conversational
- **Branding** — reference `brand.json` if provided

### 2. Gather Data

Collect data from the sources specified in the brief:

```bash
# Read project artifacts
cat TODO.md QA.md PLAN.md

# Parse JSON data
python3 -c "import json; data = json.load(open('data.json')); ..."

# Process CSV
python3 -c "import csv; ..."
```

Normalize data into structures suitable for report components:
- Tables → `{ "columns": [...], "rows": [[...], ...] }`
- Metrics → `{ "cards": [{"label": "...", "value": "...", "trend": "..."}] }`
- Charts → `{ "data": {"labels": [...], "values": [...]} }`

### 3. Select Components

Choose from the available page components:

| Component | Best For |
|-----------|----------|
| `cover` | Title page — always include for reports > 1 page |
| `toc` | Table of contents — include for reports > 3 pages |
| `text_section` | Narrative blocks, summaries, analysis |
| `data_table` | Structured data with rows and columns |
| `metrics` | KPI cards with values and trends |
| `bar_chart` | Comparisons, distributions, rankings |
| `pie_chart` | Proportions, market share, composition |
| `timeline` | Roadmaps, project milestones, history |
| `checklist` | Do's and don'ts, compliance checks |
| `color_palette` | Brand color documentation |
| `typography` | Font specimens and type scales |
| `logo_usage` | Logo presentation guidelines |
| `clear_space` | Logo spacing and minimum sizing rules |

### 4. Compose the Report Spec

Build the JSON spec:

```json
{
  "title": "<Report Title>",
  "subtitle": "<Optional subtitle>",
  "author": "igot.ai",
  "brand_file": "brand.json",
  "page_size": "A4",
  "output": "<output-filename>.pdf",
  "pages": [
    {
      "type": "cover",
      "title": "<Report Title>",
      "subtitle": "<Subtitle>",
      "date": "<YYYY-MM-DD>"
    },
    {
      "type": "toc",
      "items": [
        { "title": "Section 1", "page": 2 },
        { "title": "Section 2", "page": 4 }
      ]
    },
    {
      "type": "text_section",
      "heading": "<Section Title>",
      "body": "<Narrative content in markdown>"
    },
    {
      "type": "data_table",
      "heading": "<Table Title>",
      "columns": ["Column A", "Column B", "Column C"],
      "rows": [
        ["val1", "val2", "val3"],
        ["val4", "val5", "val6"]
      ]
    },
    {
      "type": "metrics",
      "heading": "Key Metrics",
      "cards": [
        { "label": "Revenue", "value": "$1.2M", "trend": "+15%" },
        { "label": "Users", "value": "42K", "trend": "+8%" }
      ]
    },
    {
      "type": "bar_chart",
      "heading": "<Chart Title>",
      "data": {
        "labels": ["A", "B", "C"],
        "values": [30, 50, 20]
      }
    }
  ]
}
```

### 5. Render the PDF

Save the spec and invoke the engine:

```bash
# Save the spec
cat > <war-room>/artifacts/report-spec.json << 'EOF'
<spec JSON>
EOF

# Generate the PDF
cd .agents/roles/reporter
python -m reporter generate <spec-file>.json -o <output>.pdf
```

### 6. Validate the Output

Before reporting completion:
- [ ] PDF opens without errors
- [ ] No empty pages
- [ ] All tables have headers
- [ ] All charts have labels
- [ ] Brand tokens from `brand.json` are consistently applied
- [ ] Cover page + TOC present for reports > 3 pages

### 7. Post Done

Post a `done` message with:
```markdown
## Report Generated — EPIC/TASK-XXX
- **Output:** <path-to-pdf>
- **Pages:** <N>
- **Components used:** <list>
- **Data sources:** <list>
```

## Verification

After generating the report:
1. PDF renders without errors
2. All data from the brief is represented in the report
3. Component types match the data they represent
4. Brand styling is consistent throughout
