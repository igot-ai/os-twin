---
name: fix-bug
description: Use this skill to fix bugs based on QA feedback by identifying root causes and applying targeted, minimal fixes.
---

# fix-bug

## Trigger
When assigned a `fix` message with QA feedback.

## Process

1. **Read Feedback**: Parse every issue from the QA `fail` message
2. **Root Cause**: For each issue, identify the root cause (not just symptoms)
3. **Fix**: Apply targeted fixes — minimal changes, no unrelated refactoring
4. **Verify**: Run tests to confirm fixes don't introduce regressions
5. **Report**: Post `done` message addressing each QA point

## Output Format

When posting `done` after a fix:
```
## Fixes Applied
- Issue 1: [QA feedback] → [what was fixed and why]
- Issue 2: [QA feedback] → [what was fixed and why]

## Regression Check
- [tests run and results]

## Files Modified
- [file]: [change description]
```

## Rules
- Address ALL points from QA feedback, not just some
- Do not introduce new features while fixing
- Keep diffs minimal and focused
