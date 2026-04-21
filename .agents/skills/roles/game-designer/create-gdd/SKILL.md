---
name: create-gdd
description: Create a Game Design Document from game brief
tags: [game-designer, design, gdd]
: core
source: project
---

# Workflow: Create GDD

**Goal:** Create a comprehensive Game Design Document from the game brief.

**Prerequisites:** `game-brief.md` must exist (or user provides brief inline)
**Input:** `.output/design/game-brief.md`
**Output:** `.output/design/gdd.md` — full design document ready for epic/story decomposition

---

## Step 1 — Load Prerequisites

1. Search for `**/project-context.md`. If found, read as technical constraint reference.
2. Load game brief: search `.output/design/game-brief.md`. If not found, ask user for path or brief content.
3. Extract and state the game pillars from the brief:
   - Core fantasy: {what players feel}
   - Core loop: {3-step loop}
   - Target audience: {player profile}
   - Monetization: {model}
   - Technical constraints: {from project-context.md if any}

**STOP** — State the pillars to the user and confirm: "These are the pillars I'll validate every design decision against. Correct?"

---

## Step 2 — Define Game Pillars

Formally articulate **3-5 game pillars** from the brief. Each pillar is a non-negotiable design value that every mechanic must serve.

Format each as:
> **Pillar {N}: {Name}** — {one sentence: what this means for every design decision}

Example for a casual puzzle game:
- **Clever Feel** — Every puzzle solution should feel like a "Eureka!" moment, never like trial and error
- **Just One More** — Sessions must naturally invite another play immediately upon completion
- **Accessible Mastery** — Easy to learn in 30 seconds, deeply satisfying after 100 hours

Confirm pillars with user: "Are these the right pillars? Say 'C' to continue or suggest changes."

---

## Step 3 — GDD Sections (Write Sequentially)

Write each section completely before moving to the next. After each section, ask: "Happy with this section? (C to continue, F for feedback)"

### Section 1: Game Overview

```
- Full game concept (3-4 sentences expanding on the one-liner from the brief)
- Genre + subgenre
- Platform: iOS / Android / both
- Target audience (age, typical play session, skill level)
- Unique selling proposition (what makes this meaningfully different from the top 3 competitors)
- Why NOW is the right time for this game
```

### Section 2: Core Mechanics

For each mechanic in the game:
```
**Mechanic: {Name}**
- How it works: {player action} → {system response} (concrete, not vague)
- How it serves the core fantasy: {direct connection to Pillar N}
- Player mastery path: {easy to learn X, satisfying to master Y}
- Variants / unlocks / progression: {how this mechanic evolves}
- Dependencies on other mechanics: {what it connects to}
```

Ensure every mechanic maps to at least one pillar. Flag any that do not.

### Section 3: Game Modes & Progression

```
- Game modes (main, endless, challenge, tutorial, etc.)
- Level/stage structure (how many levels, acts, worlds, etc.)
- Difficulty curve (how challenge scales — early, mid, late game)
- Player progression system (what unlocks, how it's earned, meta-progression)
- Session pacing (average session length, natural stopping points, re-engagement hooks)
```

### Section 4: UI/UX Design

```
**Key Screens:**
For each screen:
- Name and purpose
- Key UI elements visible
- Player action available on this screen
- Transition to/from (navigation flow)

**Main HUD Elements:**
- {element}: {what it shows} / {when it changes}

**Key Feedback Moments:**
- Level complete: {visual + audio response}
- Level fail: {visual + audio response}
- Reward received: {visual + audio response}
- New mechanic introduced: {tutorial approach}

**Unity uGUI Notes:**
- Canvas structure (World Space / Screen Space Overlay)
- Key component types needed (CanvasGroup for fades, TextMeshProUGUI for text, etc.)
- Performance: target 60fps — avoid expensive layouts during animations
```

### Section 5: Monetization Design

```
- Model: {premium | free-to-play | hybrid}
- Soft currency: {name, earn rate, spend on what}
- Hard currency (if IAP): {name, earn rate, price points}
- IAP items: {item, price, value proposition, purchase trigger}
- Ad placements (if any): {type — interstitial/rewarded/banner, trigger moment, frequency cap}
- Player-friendly constraints: {no pay-to-win guarantees if applicable}
- Ethical guidelines: {no dark patterns — no fake scarcity, no misleading offers}
```

### Section 6: Audio & Visual Direction

```
**Visual Style:**
- Reference games: {2-3 titles + what specifically to take from each}
- Art style: {2D/3D, realistic/stylized, color palette philosophy}
- Key visual moments: {the "wow" moments in the game visually}
- Character/environment design direction: {brief style guide}

**Audio Direction:**
- Music mood: {genre, tempo, emotional tone by game state}
- SFX principles: {satisfying feedback design — what sounds when}
- Silence as design: {when to let the game breathe}
```

### Section 7: Technical Requirements

Read `contributes/roles/game-engineer/skills/unity-coding/SKILL.md` before writing this section to ensure accuracy.

```
**Unity Setup:**
- Unity version: {from project-context.md or recommend}
- Key packages: UniTask (async), UniRx (reactive), VContainer (DI), TextMeshPro, etc.
- Architecture pattern: {from unity-coding — feature module pattern, Clean Architecture, etc.}

**Performance Targets:**
- 60fps non-negotiable on target device (specify: iPhone 12 / mid-range Android / both)
- Memory budget: {MB target}
- Load time target: {seconds for initial load, level load}
- No garbage collection spikes during gameplay

**Platform-Specific:**
- iOS: {minimum iOS version, App Store guidelines affecting design}
- Android: {minimum API level, Play Store guidelines}
- Orientation: {portrait / landscape / both}

**Third-Party SDKs:**
- Analytics: {tool}
- Ad mediation: {if applicable}
- IAP: Unity IAP / RevenueCat / etc.
- Other: {crash reporting, etc.}

**Existing Code Constraints:**
{From project-context.md — what exists and must be integrated with}
```

### Section 8: Out of Scope & Risks

```
**Explicitly Out of Scope (v1):**
- {feature}: reason excluded from MVP

**Design Risks:**
- {risk}: {mitigation approach}

**Technical Risks:**
- {risk}: {mitigation approach — often: "prototype first"}

**Scope Risks:**
- {feature}: {watch-out — potential scope creep}

**Assumptions:**
- {assumption that could invalidate the design if wrong}
```

---

## Step 4 — Validate Against Pillars

After all sections are written, validate each core mechanic against all pillars:

| Mechanic | Pillar 1: {Name} | Pillar 2: {Name} | Pillar 3: {Name} | Issue |
|----------|-----------------|-----------------|-----------------|-------|
| {mechanic 1} | ✅ | ✅ | ❌ | {what's missing} |
| {mechanic 2} | ✅ | ✅ | ✅ | — |

For any ❌: either modify the mechanic to serve the pillar, or explicitly document it as a known design tension with justification.

---

## Step 5 — Open Questions & Next Steps

List:
1. **Unresolved design questions** — decisions that remain open
2. **Prototype candidates** — mechanics that need playtesting before committing to full dev
3. **Art/audio dependencies** — what needs to be created vs what already exists in project
4. **Research needed** — competitor analysis, user testing, technical spikes

---

## Step 6 — Save

1. Create `.output/design/` if needed.
2. Save to `.output/design/gdd.md`.
3. Report: "GDD saved to `.output/design/gdd.md`."
4. Suggest next step: "Run `[game-designer] create epics and stories` to decompose this GDD into engineering work items."
