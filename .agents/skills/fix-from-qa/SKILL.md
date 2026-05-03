---
name: fix-from-qa
description: Use this skill to address QA failure feedback -- read every point, fix without regressions, and deliver a new done report."
tags: [engineer, bugfix, qa-response]

---

# fix-from-qa

## Overview

This skill guides you through handling QA rejection feedback. The goal is to address **every** point raised, avoid introducing new issues, and deliver a clean re-submission.

## When to Use

- When you receive a `fix` message from the manager (routed from QA)
- When re-entering the `developing` state after a `fixing` triage
- When QA posts a `fail` verdict with specific issues

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Code fixes | Various | Project working directory |
| Updated tests | Various | Project test directory |
| Updated TASKS.md | Markdown | `<war-room>/TASKS.md` (if epic) |
| New done report | Markdown | Channel `done` message |

## Instructions

### 1. Parse the QA Feedback

Read the `fix` message carefully. Extract:
- **Numbered issues** -- each specific problem QA found
- **Severity** -- critical / major / minor
- **Expected vs actual** -- what QA expected and what happened
- **Suggested fixes** -- any hints from QA

Also read `triage-context.md` if it exists -- the manager may have added classification context.

### 2. Create a Fix Plan

For each issue, determine:

| # | Issue | Root Cause | Fix Approach | Risk |
|---|-------|-----------|-------------|------|
| 1 | <issue> | <why> | <what to change> | <regression risk> |
| 2 | <issue> | <why> | <what to change> | <regression risk> |

Address **critical** issues first, then **major**, then **minor**.

### 3. Apply Fixes

For each issue:
1. Make the targeted code change
2. Write or update a test that covers the specific issue
3. Run the test suite -- ensure the fix works AND no regressions
4. If this is an epic: add a fix sub-task to TASKS.md and check it off

**Rules:**
- Fix only what QA flagged -- don't refactor unrelated code
- Each fix should be minimal and focused
- If a fix requires significant redesign, flag it in your done message

### 4. Self-Verify

Before re-submitting, run the full checklist:
- [ ] Every numbered QA issue has been addressed
- [ ] All tests pass (including new tests for each fix)
- [ ] Code lints cleanly
- [ ] No new hardcoded secrets
- [ ] TASKS.md updated (if epic)

### 5. Post the Done Report

Post a `done` message explicitly mapping fixes to QA issues:

```markdown
## Fix Report -- EPIC/TASK-XXX (Retry #N)

### Issues Addressed

| # | QA Issue | Fix Applied | Test Added |
|---|---------|-------------|------------|
| 1 | <issue summary> | <what was changed> |  `test_name` |
| 2 | <issue summary> | <what was changed> |  `test_name` |

### Files Modified
- `path/to/file.py` -- <what changed>

### Regression Check
- Full test suite:  all passing
- No new issues introduced

### Notes
<any caveats or items that need design-level discussion>
```

## Verification

After submitting fixes:
1. Every QA issue has a corresponding code change and test
2. No new test failures introduced
3. Done message references each QA issue by number
4. TASKS.md reflects any new fix sub-tasks (if epic)
