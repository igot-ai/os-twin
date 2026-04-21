---
name: correct-course
description: Course-correct when implementation diverges from architecture
tags: [architect, escalation, correction]

source: project
---

# Workflow: Correct Course

**Goal:** Manage significant changes during implementation — when the engineer hits a blocker, discovers a design gap, or implementation deviates from the original plan. Produces a Sprint Change Proposal with specific artifact edits.

**Use when:** "Implementation is off track" or "We need to change direction" or "Found a problem"
**Input:** Description of the issue + current project artifacts
**Output:** `.output/planning/sprint-change-{date}.md` — Sprint Change Proposal with specific before/after edits

---

## Step 1 — Understand the Trigger

Ask:
1. "What specifically went wrong or changed? (concrete description)"
2. "When was this discovered? (during implementation / QA feedback / design review)"
3. "What's the impact if we don't address it?"

Also load:
- `.output/planning/epics-and-stories.md` — current plan
- `.output/design/gdd.md` — design reference
- `.output/design/game-architecture.md` — architecture reference
- `.output/design/ux-design.md` — UX reference
- `project-context.md` — technical constraints

If GDD or Epics cannot be found: "Cannot assess impact without these documents. Please provide paths."

---

## Step 2 — Impact Analysis

Systematically assess which artifacts are affected:

**Scope categorization:**
- **Minor** — only affects 1-2 stories in the current epic
- **Moderate** — affects multiple epics or a core system
- **Major** — requires GDD changes, architecture rethink, or MVP scope reduction

**Impact table:**

| Artifact | Affected? | What Changes |
|----------|-----------|-------------|
| Current sprint stories | {Yes/No} | {specific stories} |
| Future stories | {Yes/No} | {which ones} |
| GDD | {Yes/No} | {which sections} |
| Architecture | {Yes/No} | {which systems} |
| UX Design | {Yes/No} | {which screens} |
| project-context.md | {Yes/No} | {what rules} |

Present impact table. Ask: "Does this capture the full impact? Anything I'm missing?"

---

## Step 3 — Change Proposal Options

Based on impact, present 2-3 resolution options:

**Option A: Direct Adjustment** — modify/add stories, minimal design change
**Option B: Scope Reduction** — defer affected features to P3/future sprint  
**Option C: Redesign** — modify GDD/Architecture/UX to fix the root cause

For each option:
- Impact on current sprint completion
- Risk to GDD pillars
- Effort to implement

Ask: "Which approach fits your constraints best?"

---

## Step 4 — Draft Specific Edits

For the chosen option, write specific before/after edits for each affected artifact:

```markdown
### Story E{N}-{N}: {title}
**Section:** Acceptance Criteria

OLD:
- {existing AC}

NEW:
- {updated AC}
- {new AC added}

**Rationale:** {why this change is necessary}

---

### GDD Section {N}: {section name}
**Change type:** {Addition | Modification | Deletion}

OLD:
{existing text}

NEW:
{updated text}

**Rationale:** {why}
```

For each edit, ask: "Approve [A] / Edit [E] / Skip [S]"

---

## Step 5 — Sprint Change Proposal

Compile the full proposal:

```markdown
# Sprint Change Proposal

**Date:** {date}
**Trigger:** {description of what caused this}
**Scope:** {Minor | Moderate | Major}

## Problem Statement

{Clear description of what went wrong and why a change is needed}

## Impact Summary

{Impact table from Step 2}

## Chosen Approach

{Which option was selected and why}

## Required Changes

### Story Changes
{All story edits from Step 4}

### GDD Changes  
{All GDD edits from Step 4}

### Architecture Changes
{If any}

### UX Design Changes
{If any}

## Implementation Handoff

**Route to:** {engineer | game-designer | architect} based on scope
**Success criteria:** {what done looks like after these changes}
**Sprint impact:** {days added, stories affected, MVP implications}

## Approval Status

[ ] Changes approved by product owner
[ ] Artifacts updated
[ ] Engineer briefed
```

---

## Step 6 — Save

1. Create `.output/planning/` if needed.
2. Save to `.output/planning/sprint-change-{date}.md`.
3. Report: "Sprint Change Proposal saved."
4. Based on scope:
   - Minor: "Proceed with engineering — stories updated."
   - Moderate: "Update epics-and-stories.md with approved changes before continuing."
   - Major: "Run `[game-designer] update gdd` and `[architect] game-architecture` before engineering resumes."
