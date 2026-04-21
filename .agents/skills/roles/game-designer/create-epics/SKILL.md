---
name: create-epics
description: Break GDD into epics and actionable stories
tags: [game-designer, planning, epics]
: core
source: project
---

# Workflow: Create Epics and Stories

**Goal:** Transform GDD requirements into actionable epics and dev stories for the engineering team.

**Prerequisites:** `gdd.md` must exist
**Input:** `.output/design/gdd.md` + `.output/design/game-brief.md` (for core loop / pillar context)
**Output:** `.output/planning/epics-and-stories.md` — prioritized epics with complete user stories

---

## Step 1 — Load Prerequisites

1. Load GDD: search `.output/design/gdd.md`. If not found, ask user for path.
2. Load game brief: search `.output/design/game-brief.md` (for core loop / pillar reference).
3. Load `project-context.md` if exists (for architecture constraints).
4. Extract all feature areas from GDD sections:
   - Every distinct mechanic, system, UI screen, audio trigger, and integration point
   - List them all before proceeding

Present the feature list and ask: "Are there any features I'm missing, or any that should be excluded from scope?"

---

## Step 2 — Group Into Epics

Group features into **epics** organized by player value delivered.

For each epic, write:

```markdown
## Epic {N}: {Name}

**Value:** {1 sentence — what this gives to the player when complete}
**Precondition:** {what must exist or be done before this epic starts}
**Deliverable:** {what is shipped/playable when this epic is done}
**Priority:** P1 (MVP must-have) | P2 (important) | P3 (nice-to-have)
**Dependencies:** {Epic numbers that must complete first, or "none"}
**Estimated Stories:** {count}
```

**Epic sizing rules:**
- Each epic must deliver visible, testable player value when complete
- Epic scope: 3-8 stories (larger = split into sub-epics)
- Avoid pure "infrastructure" epics unless absolutely necessary
- P1 = core loop, main game screen, critical mechanics (MVP cannot ship without)
- P2 = polish, secondary mechanics, full monetization, social features
- P3 = advanced features, meta-progression, personalization

**Confirm epic grouping** with user before writing stories: "Here are the {N} epics. Does this grouping make sense?"

---

## Step 3 — Write Stories

For each epic, write all user stories in order of dependency.

**Story format:**

```markdown
### Story {Epic}-{N}: {Title}

**As a** {player | game developer | UI designer},
**I want** {specific, concrete capability},
**So that** {clear player value or development enabler}.

**Acceptance Criteria:**
- [ ] Given {precondition}, When {player/system action}, Then {expected result}
- [ ] Given {precondition}, When {player/system action}, Then {expected result}
- [ ] (add more as needed — minimum 2 ACs, maximum 6)

**Technical Notes:**
- {Unity component, class, or architecture note — use real class names}
- {Performance note if applicable — e.g. "Must not allocate during Update()"}
- {Reference to existing code if applicable — e.g. "Extends RevivePopup pattern"}

**Size:** S (< 4h) | M (4–8h) | L (> 8h — must be split before implementation)
**Dependencies:** {Story IDs this story requires, or "none"}
**Assignable to:** engineer | cv-analytics | (both)
```

**Story writing rules:**
1. Stories must be independently testable — one story should not require another to be "half-done" to test
2. Every story must have ≥2 Given/When/Then ACs
3. L-sized stories must be marked `[MUST SPLIT]` — add a note with how to split
4. Technical notes must use real Unity class names (not "the heart icon" but `Image` component)
5. Player-facing stories first within each epic; infrastructure stories last
6. One story = one atomic unit of work an engineer can complete and demo

---

## Step 4 — Prioritize Within Epics

Within each epic, order stories so:
1. Core functionality first (without this, nothing else in the epic works)
2. Edge cases and error handling second
3. Polish and visual refinement last

Tag any story that cannot start without another story:
```
**Dependencies:** Story E{N}-{N} must be complete first
```

Tag `[BLOCKED BY EPIC {N}]` for any story blocked by an incomplete epic.

---

## Step 5 — Summary Table

```markdown
## Summary

### Epics Overview

| Epic | Name | Priority | Stories | Blocked By |
|------|------|----------|---------|-----------|
| E1 | {name} | P1 | {count} | none |
| E2 | {name} | P1 | {count} | E1 |
| E3 | {name} | P2 | {count} | E1, E2 |

### Story Count
- **Total stories:** {count}
- **P1 stories (MVP):** {count}
- **P2 stories:** {count}
- **P3 stories:** {count}
- **Large stories needing split:** {list story IDs}

### Critical Path (P1 — must complete in order)
E{N} → E{N} → E{N}

### MVP Definition
Minimum stories required to ship a playable product:
- {story IDs} from E{N}
- {story IDs} from E{N}

### Recommended First Sprint
Stories to tackle first (unblocked P1 stories):
- E{N}-{N}: {title}
- E{N}-{N}: {title}
```

---

## Step 6 — Validation Pass

Before saving, validate every story:

- [ ] Uses "As a / I want / So that" format
- [ ] Has ≥2 Given/When/Then ACs
- [ ] Has a Size (S/M/L)
- [ ] L-sized stories are marked `[MUST SPLIT]`
- [ ] Technical notes reference real Unity class names
- [ ] Dependencies are listed (or "none")
- [ ] Engineer can implement without asking the designer for clarification

Fix any failing stories before proceeding.

---

## Step 7 — Save

1. Create `.output/planning/` if needed.
2. Save to `.output/planning/epics-and-stories.md`.
3. Report: "Epics and stories saved to `.output/planning/epics-and-stories.md`."
4. Suggest next steps:
   - "Hand off to engineer: `[engineer] implement story E{N}-{N}`"
   - "Hand off to cv-analytics for UI detection first if screens are new: `[cv-analytics] detect UI from screenshot`"
