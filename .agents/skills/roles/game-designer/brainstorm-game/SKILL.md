---
name: brainstorm-game
description: Brainstorm game concepts and mechanics
tags: [game-designer, design, brainstorm]
trust_level: core
source: project
---

# Workflow: Brainstorm Game

**Goal:** Facilitate high-volume creative ideation for game concepts — pushing past obvious ideas into truly novel territory before any commitment to a specific concept.

**Use when:** "I want to explore game ideas" or "help me brainstorm concepts"
**Output:** `.output/design/brainstorm-{topic}.md` — organized idea catalog with ranked concepts

**Critical mindset:** Keep the user in generative exploration mode as long as possible. The first 20 ideas are always obvious. The magic is in ideas 50-100. Aim for quantity over quality in the ideation phase.

---

## Step 1 — Set the Brainstorm Context

Ask these framing questions:

1. "What's the starting seed? (genre, mechanic, theme, emotion, or 'open')"
2. "Who is the target player? (age, platform, session length, skill level)"
3. "Any explicit constraints? (must be mobile / must be casual / must use X mechanic / etc.)"
4. "What's the goal of this session? (find a new concept / explore a specific mechanic / expand on existing idea)"

Wait for answers. Then confirm:
"Great. We're brainstorming {seed} for {player} with constraints: {constraints}. I'll facilitate with structured techniques. Let's aim for 50+ ideas before we filter."

---

## Step 2 — Round 1: Rapid Fire (20 ideas)

Use the SCAMPER technique on the seed:

**S**ubstitute: What if you substituted the core action?
**C**ombine: What if you combined two unrelated genres?
**A**dapt: What if you adapted a non-game activity into a game?
**M**odify/Magnify: What if you exaggerated one mechanic to absurdity?
**P**ut to other use: What other contexts could this mechanic serve?
**E**liminate: What if you removed the most central element?
**R**everse: What if the player's goal was inverted?

Generate 20 ideas using SCAMPER. Present as a numbered list.
Ask: "Which 2-3 of these spark anything? Or shall we continue generating?"

---

## Step 3 — Round 2: Deep Dive (20 more ideas)

Pick the 2-3 most interesting from Round 1 and explore each deeper:

For each selected concept:
- 5 mechanic variations
- 3 monetization models that would fit
- 2 unexpected twists that would make it unique

Generate 20 more ideas. Present organized by parent concept.
Ask: "Interesting directions emerging? Or explore more?"

---

## Step 4 — Round 3: Constraint Breaking (10+ ideas)

Apply constraint-breaking techniques:

1. **Opposite Day:** What if the core game loop was completely reversed?
2. **Genre Mashup:** Combine {genre} + {completely different genre}
3. **Platform Native:** What mechanic only works on mobile? (gyroscope, AR, real-time location, social sharing)
4. **Emotional Core:** What emotion do players almost never feel in games? Design for that.
5. **5-Second Core:** What's a mechanic so simple you can learn it in 5 seconds but master in 100 hours?

Generate 10+ ideas. Total should now be 50+.

---

## Step 5 — Organize and Rank

Group all ideas by theme/mechanic:

```markdown
## Idea Catalog

### Cluster A: {Theme}
1. **{Concept Name}** — {2-sentence description}
   - Core loop: {action → feedback → reward}
   - Unique hook: {what makes this different from existing games}
   - Risk: {main design risk or challenge}

### Cluster B: {Theme}
...
```

Then rank the top 5 by:

| Rank | Concept | Novelty | Feasibility | Player Appeal | Total |
|------|---------|---------|-------------|---------------|-------|
| 1 | {name} | 8/10 | 7/10 | 9/10 | 24 |

Ask: "Based on this ranking, are you drawn to any of these? Want to explore the top concept deeper or keep generating?"

---

## Step 6 — Concept Deep Dive (if user selects one)

If the user wants to explore a concept further:

1. Define the core loop in detail: {action} → {immediate feedback} → {reward} → {progression}
2. Identify the "just one more" hook: what makes players want to continue?
3. Identify the skill ceiling: what separates novice from expert play?
4. Quick competitive check: "What existing games does this resemble? What makes yours different?"
5. Identify the ONE core mechanic that must feel perfect for the game to work

Output: "Concept brief ready. Run `[game-designer] create game-brief` to formalize this into a game brief."

---

## Step 7 — Save

1. Create `.output/design/` if needed.
2. Save to `.output/design/brainstorm-{topic}.md`.
3. Report: "Brainstorm saved — {N} ideas cataloged, top 5 ranked."
4. Suggest: "Run `[game-designer] create game-brief` to develop the top concept into a full game brief."
