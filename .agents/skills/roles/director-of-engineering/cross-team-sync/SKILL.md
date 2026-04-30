---
name: cross-team-sync
description: Run structured cross-team synchronization to detect blocked dependencies, duplicate work, conflicting approaches, and misaligned priorities across war-rooms. Produces actionable sync reports with resolution paths.
---

# cross-team-sync

## Purpose

In large organizations, the biggest risks aren't within teams — they're *between* teams. This skill provides a structured process for detecting and resolving cross-team coordination failures before they become project delays.

## Sync Process

### Step 1 — Gather Status

From each war-room, collect:
- Current sprint/epic progress (% complete)
- Blockers (internal and external)
- Upcoming dependencies on other rooms
- Changes to interfaces or shared resources

### Step 2 — Dependency Matrix

Build a dependency matrix:

```markdown
| Room | Depends On | Dependency | Status | Risk |
|------|-----------|------------|--------|------|
| Room A | Room B | Auth API v2 | 🟡 In progress | Medium — 3 days behind |
| Room C | Room A | Event schema | 🟢 Complete | Low |
| Room B | Platform | CI pipeline | 🔴 Blocked | High — no ETA |
```

### Step 3 — Conflict Detection

Check for:
- **Duplicate work** — two rooms solving the same problem differently
- **Interface conflicts** — rooms assuming different API shapes
- **Resource contention** — rooms needing the same limited resource (DBA time, staging env)
- **Priority misalignment** — Room A's blocker is Room B's backlog item

### Step 4 — Resolution Actions

For each finding:

```markdown
## Finding: [Title]
**Type:** Dependency block | Duplicate work | Interface conflict | Priority misalignment
**Affected rooms:** [list]
**Impact:** [what happens if unresolved]
**Resolution:** [specific action — who does what by when]
**Owner:** [who drives the resolution]
**Deadline:** [when it must be resolved]
```

## Output Format

```markdown
# Cross-Team Sync Report — [Date]

## Summary
- **Teams synced:** [count]
- **Blockers found:** [count]
- **Conflicts detected:** [count]
- **Actions assigned:** [count]

## Status Dashboard
[Room status table]

## Dependency Matrix
[Matrix]

## Findings & Actions
[List of findings with resolutions]

## Next Sync
[Date and focus areas]
```

## Anti-Patterns

- Syncing without follow-up → actions without owners and deadlines are wishes
- Too-frequent syncs → weekly is usually right; daily syncs have diminishing returns
- Only syncing within your org → dependencies on platform, SRE, and external teams matter
- Ignoring soft signals → "we're fine" from a team that's 2 sprints behind is a red flag
