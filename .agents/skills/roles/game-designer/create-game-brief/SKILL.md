---
name: create-game-brief
description: Create a game brief document from initial concept
tags: [game-designer, design, brief]
trust_level: core
source: project
---

# Workflow: Create Game Brief

**Goal:** Capture and validate the core game vision through collaborative discovery.

**Input:** User's game idea (verbal description, notes, existing concept)
**Output:** `game-brief.md` — structured brief ready for GDD creation

---

## Step 1 — Load Context

1. Search for `**/project-context.md`. If found, read it.
   - Note: game name, genre, target platform, tech stack, existing constraints
   - Note: existing UI patterns, architecture decisions that constrain design
2. If not found: proceed as greenfield (no technical constraints assumed).

State what you found (or "Starting fresh — no project-context.md found") before proceeding.

---

## Step 2 — Discovery Questions

Ask each group as a batch. Wait for answers before proceeding to the next group.

**Group A — Game Identity**

> 1. What is the game's one-sentence concept? (e.g. "A match-3 puzzle where players rescue animals from flooding islands")
> 2. What genre? (puzzle, platformer, idle, runner, RPG, strategy, hyper-casual, etc.)
> 3. Target platform? (iOS only / Android only / both)
> 4. Who is the target player? (age range, typical play session length, gaming experience level)

**Group B — Core Experience**

> 5. What is the ONE core fantasy — what should players FEEL? (e.g. "Feel like a clever master planner", "Feel unstoppable power rushing through levels")
> 6. What is the core loop in 3 steps? (player action → immediate reward → motivation to repeat)
> 7. Win condition per session? Win condition long-term (meta)?

**Group C — Business & Scope**

> 8. Monetization model? (premium one-time / free-to-play IAP / rewarded ads / subscription / hybrid)
> 9. What 3-5 existing games inspire this? (reference titles)
> 10. What is the MVP — the first shippable version?

---

## Step 3 — Validate Core Loop

Before writing the brief, validate the proposed core loop:

1. Restate it: "Your loop is: **{action}** → **{reward}** → **{motivation}**. Correct?"
2. Check: Does the reward reinforce the core fantasy?
3. Check: Is the loop completable in under 5 minutes per session?
4. Check: Is the motivation genuinely compelling (not just "get more coins")?

If any check fails, iterate with the user. Do not proceed until the loop is solid.

---

## Step 4 — Generate Game Brief

Write `game-brief.md`:

```markdown
---
title: Game Brief — {Game Name}
version: 1.0
date: {today}
status: draft
---

# {Game Name} — Game Brief

## Concept
{one-sentence pitch}

## Genre & Platform
- **Genre:** {genre} / {subgenre if applicable}
- **Platform:** {iOS | Android | both}
- **Target Audience:** {age range, experience level, typical session length}

## Core Fantasy
{What players FEEL — not what they DO. 2-3 sentences. Start with "Players feel..."}

## Core Loop
1. **Action:** {what the player does}
2. **Reward:** {what they immediately get/feel}
3. **Drive:** {why they immediately want to do it again}

## Win Conditions
- **Per Session:** {what completing a play session looks like}
- **Long-Term:** {meta-progression goal / end-game}

## Monetization
- **Model:** {model name}
- **Key Revenue Hooks:** {list — e.g. "lives refill", "level skip", "cosmetic bundles"}

## Inspiration
| Title | What We Take From It |
|-------|---------------------|
| {game 1} | {specific mechanic, feel, or system} |
| {game 2} | {specific mechanic, feel, or system} |
| {game 3} | {specific mechanic, feel, or system} |

## MVP Scope (First Shippable Version)
{Bulleted list of features in v1 — concrete and specific}

## Out of Scope (Post-MVP)
{Features explicitly excluded from v1}

## Technical Constraints
{From project-context.md — Unity version, architecture, existing code, platform limits}
{If no constraints found: "No existing constraints — greenfield project"}

## Open Questions
{Unresolved design decisions that need answers before GDD creation}
```

---

## Step 5 — Review & Confirm

1. Present the brief in full.
2. Ask: "Does this capture your vision? Any corrections or additions?"
3. Apply feedback and update.
4. Confirm with: "Brief is finalized. Shall I create the GDD from this brief?"

---

## Step 6 — Save

1. Create directory `.output/design/` if it doesn't exist.
2. Save to `.output/design/game-brief.md`.
3. Report: "Game brief saved to `.output/design/game-brief.md`."
4. Suggest next step: "Run `[game-designer] create a GDD` to expand this into a full Game Design Document."
