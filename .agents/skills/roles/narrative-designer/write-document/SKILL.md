---
name: write-document
description: Write technical documentation or guides"
tags: [tech-writer, documentation, writing]

---

# Workflow: Write Document

**Goal:** Author any technical document through guided conversation -- from architecture decision records to feature specs, API references, or onboarding guides.

**Input:** User description of document type and content
**Output:** A well-structured markdown document saved to `.output/docs/`

---

## Step 1 -- Define the Document

Ask (if not already stated):
1. "What type of document? (ADR / feature spec / API reference / onboarding guide / other)"
2. "Who is the audience? (engineers / designers / new team members / AI agents)"
3. "What's the core question this document answers?"
4. "Any reference files to read first? (code, GDD, architecture docs)"

---

## Step 2 -- Choose Structure

**Architecture Decision Record (ADR):**
```markdown
# ADR-{N}: {Title}

**Date:** {date}
**Status:** {Proposed | Accepted | Deprecated}

## Context
{why this decision was needed}

## Decision
{what was decided}

## Consequences
{what becomes easier, harder, or different}

## Alternatives Considered
{other options and why they were rejected}
```

**Feature Specification:**
```markdown
# Feature Spec: {Feature Name}

## Summary
{1-2 sentence description}

## User Story
As a {user}, I want {capability}, so that {value}.

## Acceptance Criteria
- [ ] Given {precondition}, When {action}, Then {result}

## Technical Notes
{Unity classes, patterns, constraints}

## Out of Scope
{what is NOT in this feature}
```

**API / Class Reference:**
```markdown
# {ClassName} Reference

## Overview
{purpose of this class}

## Methods

### {MethodName}({params})
**Returns:** {type}
**Description:** {what it does}
**Example:**
```csharp
{code example}
```
```

**Onboarding Guide:**
```markdown
# {Topic} -- Getting Started

## Prerequisites
{what you need before starting}

## Setup Steps
1. {step}
2. {step}

## Quick Start
{minimum to get something working}

## Common Tasks
{table of tasks and how to do them}

## Troubleshooting
{common problems and solutions}
```

---

## Step 3 -- Draft and Review

Write the complete document. Always include:
- Purpose statement at the very top
- Mermaid diagram if there's any structure, flow, or hierarchy
- Tables for comparisons, parameters, or any list > 5 items
- Fenced code blocks with language specifier for all code

Present: "Here's the complete document. Approve (C) or give feedback (F)?"

Apply any feedback and re-present once.

---

## Step 4 -- Save

1. Create `.output/docs/` if needed.
2. Save to `.output/docs/{document-kebab-name}.md`.
3. Report: "Saved to `.output/docs/{name}.md`."
