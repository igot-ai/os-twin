---
name: mermaid-diagram
description: Generate Mermaid diagrams for architecture visualization
tags: [tech-writer, documentation, diagrams]
trust_level: core
source: project
---

# Workflow: Mermaid Diagram

**Goal:** Generate a valid Mermaid diagram from a verbal description or by analyzing existing code/documents — producing a ready-to-paste diagram block.

**Input:** Description of what to diagram, or code/document to analyze
**Output:** Inline Mermaid diagram block

---

## Step 1 — Understand the Diagram Need

Ask (if not provided):
1. "What does this diagram represent?"
2. "Is there existing code or a document I should analyze to extract the structure?"

---

## Step 2 — Choose Diagram Type

| Content | Mermaid Type |
|---------|-------------|
| System components + relationships | `graph TD` / `graph LR` |
| Process/flow with decisions | `flowchart TD` |
| Time-ordered interactions | `sequenceDiagram` |
| Class hierarchy / interfaces | `classDiagram` |
| State machine / transitions | `stateDiagram-v2` |
| Gantt / schedule | `gantt` |
| Entity relationships | `erDiagram` |
| Git branch visualization | `gitGraph` |

---

## Step 3 — Generate the Diagram

Rules for valid Mermaid:
- Node IDs: no spaces → use `camelCase` or `PascalCase`
- Labels with spaces: wrap in `["Label with spaces"]`
- Group related nodes with `subgraph`
- Add relationship labels: `A -->|"does something"| B`
- Depth ≤ 4 levels for readability

Output as a fenced code block:

```mermaid
{diagram content here}
```

Brief explanation: "This diagram shows {what}. Key relationships: {summary}."

---

## Step 4 — Offer Refinement

"Does this capture what you need? (C = confirm / F = feedback)"

If feedback: apply and re-present once.

Offer: "Want a simplified version or more detail on any section?"
