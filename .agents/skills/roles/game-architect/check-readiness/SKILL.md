---
name: check-readiness
description: Validate architecture readiness before engineering
tags: [architect, gate, readiness]
trust_level: core
source: project
---

# Workflow: Check Implementation Readiness

**Goal:** Validate that all upstream design artifacts (GDD, UX Design, Architecture, Epics & Stories) are complete, aligned, and sufficient for the engineering team to begin implementation without designer clarification.

**Prerequisites:** All or most of these should exist before running this check
**Input:** `.output/design/gdd.md`, `.output/design/ux-design.md`, `.output/design/game-architecture.md`, `.output/planning/epics-and-stories.md`
**Output:** `.output/planning/readiness-report.md` — PASS/FAIL verdict with specific gaps

---

## Step 1 — Document Discovery

Load all available artifacts:

1. `.output/design/gdd.md` — **required**
2. `.output/design/game-brief.md` — optional but useful
3. `.output/design/ux-design.md` — required for UI-heavy projects
4. `.output/design/game-architecture.md` — required if exists
5. `.output/planning/epics-and-stories.md` — **required**
6. `project-context.md` — load if exists

For each file: note if FOUND or MISSING. Missing required files = report BLOCKED status.

Present: "Found: {list}. Missing: {list}. Proceeding with available documents."

---

## Step 2 — GDD Completeness Check

Validate the GDD against these criteria:

| Check | Pass Condition | Status |
|-------|---------------|--------|
| Core loop defined | 3-step loop clearly described | |
| Game pillars present | 3-5 pillars with clear definitions | |
| All screen UIs listed | Every screen in GDD Section 4 | |
| Mechanics fully described | Each mechanic has: how it works, player mastery path | |
| Monetization model defined | Model type, items, prices | |
| Technical constraints listed | Unity version, target platform, packages | |
| Out-of-scope explicitly listed | What's NOT in v1 | |

Mark each: ✅ PASS | ⚠️ PARTIAL | ❌ MISSING

---

## Step 3 — Epic & Story Quality Check

For each story in `epics-and-stories.md`, validate:

**Story format check:**
- [ ] Has "As a / I want / So that" format
- [ ] Has ≥2 Given/When/Then acceptance criteria
- [ ] Has Size (S/M/L)
- [ ] L-sized stories are split or marked `[MUST SPLIT]`
- [ ] Technical Notes use real Unity class names
- [ ] Dependencies listed (or "none")
- [ ] Assignable role specified (engineer / cv-analytics)

**Engineer-readiness check (critical):**
For each story, ask: "Can an engineer implement this story without asking the designer a single question?"

Common failure modes to detect:
- "Add a nice animation" → ❌ No duration, easing, or trigger specified
- "Show error message" → ❌ No error text, placement, or style
- "Save player progress" → ❌ No data format, frequency, or failure handling
- "Integrate with backend" → ❌ No API spec or authentication method

Count: PASS | FAIL | WARNING per story.

---

## Step 4 — GDD ↔ Epics Coverage Check

Cross-reference: every feature in the GDD must have at least one epic covering it.

| GDD Feature | Covered by Epic | Status |
|-------------|----------------|--------|
| {mechanic} | E{N}: {name} | ✅ |
| {screen} | E{N}: {name} | ✅ |
| {monetization item} | — | ❌ No epic |

List all GDD features with no epic coverage.

---

## Step 5 — UX ↔ Stories Alignment

For every UI screen in ux-design.md, confirm at least one story implements it:

| Screen | Story | Status |
|--------|-------|--------|
| Gameplay HUD | E1-3: Build HUD | ✅ |
| Revive Popup | E2-1: Build RevivePopup | ✅ |
| {screen} | — | ❌ No story |

---

## Step 6 — Architecture ↔ Stories Technical Alignment

If `game-architecture.md` exists, check:

- [ ] Stories reference real architecture patterns (VContainer, UniTask, UniRx)
- [ ] No story contradicts an architecture decision
- [ ] Performance-critical stories have explicit 60fps/allocation notes
- [ ] Unity version and package dependencies mentioned where relevant

---

## Step 7 — Final Readiness Verdict

Compile the report:

```markdown
# Implementation Readiness Report

**Date:** {date}
**Project:** {project-name}

## Verdict: {READY | BLOCKED | CONDITIONAL}

{READY: "All critical gates pass. Engineering can begin."}
{BLOCKED: "Cannot begin engineering until CRITICAL gaps are resolved."}
{CONDITIONAL: "Engineering can begin on P1 stories. P2 blocked pending {specific items}."}

## Critical Gaps (Must Fix Before Engineering)

{If none: "None — all critical checks pass."}

1. ❌ **{gap title}** — {description} → {who should fix: game-designer / architect}
2. ❌ ...

## Warnings (Should Fix, Non-Blocking)

1. ⚠️ **{warning title}** — {description}
2. ⚠️ ...

## Scorecard

| Area | Status | Score |
|------|--------|-------|
| GDD Completeness | ✅/⚠️/❌ | {N}/{total} |
| Story Quality | ✅/⚠️/❌ | {N}/{total} |
| GDD→Epic Coverage | ✅/⚠️/❌ | {N}/{total} |
| UX→Story Alignment | ✅/⚠️/❌ | {N}/{total} |
| Architecture Alignment | ✅/⚠️/❌ | {N}/{total} |

**Overall: {N}% ready**

## Recommended First Sprint

{If READY or CONDITIONAL:}
Unblocked P1 stories ready for engineering:
- E{N}-{N}: {title} (Size: {S/M})
- E{N}-{N}: {title} (Size: {S/M})
```

---

## Step 8 — Save

1. Create `.output/planning/` if needed.
2. Save to `.output/planning/readiness-report.md`.
3. Report: "Readiness report saved."
4. Suggest next steps based on verdict:
   - READY: "Hand off to engineer: `[engineer] implement story E{N}-{N}`"
   - BLOCKED: "Fix gaps first: `[game-designer] update gdd`" or `[game-designer] create epics and stories`"
