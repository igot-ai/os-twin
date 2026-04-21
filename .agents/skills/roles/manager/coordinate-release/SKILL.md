---
name: coordinate-release
description: Use this skill to draft RELEASE.md when all war-rooms pass -- collect signoffs from all roles and finalize the release."
tags: [manager, release, coordination, signoff]
: core
---

# coordinate-release

## Overview

This skill guides the manager through the release coordination process. It is triggered when **all** war-rooms in a plan reach the `passed` state. The output is a `RELEASE.md` and collected signoffs.

## When to Use

- When all war-rooms in the current plan have status `passed`
- When drafting a release after a full plan execution cycle
- When collecting signoffs for a completed delivery

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Release notes | Markdown | `<plan-dir>/RELEASE.md` |
| Signoff records | Channel | `signoff` messages from each role |

## Instructions

### 1. Verify All War-Rooms Passed

Before starting the release process:

```bash
# Check all war-rooms
for room in <plan-dir>/.war-rooms/*/; do
  status=$(cat "$room/status.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
  echo "$room: $status"
done
```

- [ ] Every war-room is in `passed` state
- [ ] No war-rooms are in `fixing`, `triage`, or `developing` state
- [ ] QA report exists for every war-room

### 2. Gather Release Content

For each war-room, collect:
- Epic/Task identifier (EPIC-XXX / TASK-XXX)
- Summary from the engineer's final `done` message
- QA verdict summary from `qa-report.md`
- Files changed across all war-rooms

### 3. Draft RELEASE.md

```markdown
# Release Notes -- <Plan Title>

> Version: <version>
> Date: <YYYY-MM-DD>
> Plan: <plan reference>

## Summary

<one-paragraph overview of what this release delivers>

## Changes

### EPIC-001 -- <title>
- **Summary:** <what was delivered>
- **War-room:** <room-id>
- **QA verdict:** PASS
- **Key files:** <list of primary files changed>

### EPIC-002 -- <title>
- **Summary:** <what was delivered>
- **War-room:** <room-id>
- **QA verdict:** PASS
- **Key files:** <list of primary files changed>

## Test Results

| Epic/Task | Tests Run | Passed | Failed | Coverage |
|-----------|----------|--------|--------|----------|
| EPIC-001 | <N> | <N> | 0 | <X%> |
| EPIC-002 | <N> | <N> | 0 | <X%> |

## Signoffs

| Role | Agent | Status | Date |
|------|-------|--------|------|
| Engineer | engineer |  Pending | -- |
| QA | qa |  Pending | -- |
| Manager | manager |  Pending | -- |
| Architect | architect |  Pending (if involved) | -- |

## Known Issues

<any non-blocking issues or technical debt introduced>

## Rollback Plan

<steps to revert if needed>
```

### 4. Collect Signoffs

Post a `release` message to the channel requesting signoffs from all involved roles:

```
Requesting signoff for release <version>.
Please review RELEASE.md and post `signoff` to approve.
```

Track signoffs as they arrive:
- [ ] Engineer signoff received
- [ ] QA signoff received
- [ ] Manager signoff (self)
- [ ] Architect signoff (if involved in any triage)

### 5. Finalize

Once all required signoffs are collected:
1. Update RELEASE.md signoff table with dates
2. Post a final `release` message confirming the release is complete
3. Update plan status to `released`

## Verification

After coordinating the release:
1. RELEASE.md exists and covers all war-rooms
2. All signoff statuses are recorded
3. No war-rooms are missing from the release notes
4. Test results table is complete
