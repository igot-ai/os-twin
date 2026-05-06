---
name: milestone-tracking
description: Track deliverables across multiple war-rooms with milestone timelines, completion percentages, critical path identification, and slippage detection. Produces actionable status dashboards with early warning indicators.
---

# milestone-tracking

## Purpose

Milestones are the heartbeat of program execution. This skill maintains a master timeline that shows what's on track, what's slipping, and what needs intervention — before deadlines are missed.

## Milestone Status Model

| Status | Icon | Meaning |
|--------|------|---------|
| On Track | 🟢 | Progress matches plan |
| At Risk | 🟡 | Behind plan but recoverable |
| Behind | 🟠 | Behind plan, needs intervention |
| Blocked | 🔴 | Cannot proceed, external dependency |
| Complete | ✅ | Delivered and verified |

## Master Timeline Template

```markdown
# Program Milestone Tracker — [Program Name]

**Updated:** [date]
**Ship date:** [date]
**Overall status:** 🟢🟡🟠🔴

## Critical Path
[The sequence of milestones that determines the ship date]

## Milestone Table

| # | Milestone | Owner | Due | Status | % | Notes |
|---|-----------|-------|-----|--------|---|-------|
| 1 | [name] | [room] | [date] | 🟢 | 80% | On track |
| 2 | [name] | [room] | [date] | 🟡 | 40% | 2 days behind |
| 3 | [name] | [room] | [date] | 🔴 | 10% | Blocked on #2 |

## Slippage Log
| Milestone | Original Due | Current Due | Days Slipped | Reason |
|-----------|-------------|-------------|-------------|--------|
| [name] | [date] | [date] | N | [reason] |

## This Week's Focus
1. [Most critical action needed]
2. [Second priority]
3. [Third priority]
```

## Weekly Review Process

1. Collect status from each war-room (automated where possible)
2. Update milestone table
3. Recalculate critical path if any milestone slipped
4. Identify new risks or blockers
5. Publish status update

## Anti-Patterns

- Tracking milestones without clear completion criteria → "done" must be defined
- Updating monthly → weekly minimum; critical milestones need daily tracking
- Ignoring "at risk" status → at risk becomes behind becomes blocked if not addressed
- Status reporting without context → "40% complete" means nothing without timeline context
