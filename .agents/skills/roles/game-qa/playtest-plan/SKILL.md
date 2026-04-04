---
name: playtest-plan
description: Create playtest plans for user experience validation
tags: [qa, testing, playtesting]
trust_level: core
source: project
---

# Workflow: Playtest Plan

**Goal:** Create a structured playtest session plan that validates game feel, player experience, and design effectiveness — capturing qualitative feedback that automated tests cannot.

**Prerequisites:** Playable build must exist
**Input:** `.output/design/gdd.md` + session goals
**Output:** `.output/qa/playtest-plan.md` — complete facilitation guide + observation sheets

**Reference skills:** `.agents/skills/roles/qa/qa-knowledge/references/playtesting.md` + `.agents/skills/roles/qa/qa-knowledge/references/balance-testing.md`

---

## Step 1 — Define Session Goals

Load:
1. `.agents/skills/roles/qa/qa-knowledge/references/playtesting.md`
2. `.agents/skills/roles/qa/qa-knowledge/references/balance-testing.md`
3. `.output/design/gdd.md` — extract core loop and design pillars

Ask:
1. "What is the PRIMARY question this playtest must answer?" (e.g., "Is the core loop fun?", "Is the tutorial too hard?")
2. "Who are the playtesters? (team members / external players / target demographic)"
3. "How long is each session? (30min / 60min)"
4. "What build version?"
5. "Any specific features to focus on or avoid?"

Compile into measurable objectives:
```
Primary: {specific question}
Success metric: {how you'll know if the answer is good}
Secondary: {list}
Out of scope: {what not to test}
```

---

## Step 2 — Design Playtest Protocol

```markdown
## Playtest Session Protocol

### Setup (10 min before session)
- [ ] Build installed on test device
- [ ] Screen recording ready (recommended)
- [ ] Observation notes template ready
- [ ] Distractions removed from test environment

### Introduction Script (read aloud, 3-5 min)
"Thank you for playtesting {game name}. A few rules:
1. We're testing the game, not you — no wrong moves
2. Please think aloud — say what you're thinking as you play
3. We cannot answer questions during play — this is intentional
4. Your feedback directly shapes the game"

### Session Flow
| Time | Phase | Facilitator Action |
|------|-------|-------------------|
| 0-2min | Brief | Read introduction script |
| 2-{N}min | Free play | Observe silently, take notes |
| {N}-{N}min | Directed task | Ask player to {specific task} |
| {N}-end | Debrief | Interview questions below |
```

---

## Step 3 — Observation Sheet

```markdown
## Observation Sheet

**Session:** {date} | **Tester:** #{N} | **Duration:** {N}min | **Build:** {version}
**Profile:** {age / gaming experience / target demographic match: yes/no}

### Critical Moments Log

| Time | What Player Did | What Was Expected | Insight |
|------|----------------|-------------------|---------|
| {mm:ss} | {action} | {game behavior} | {observation} |

### Confusion Points (player got stuck)
1. {location}: {what they tried, what they expected}

### Delight Moments (positive reaction)
1. {location}: {what the player said/did}

### Unexpected Behavior
1. {what they did}: {likely mental model mismatch}
```

---

## Step 4 — Post-Session Interview Questions

```markdown
## Debrief Interview (10-15 min)

### Overall Experience
1. "What was your first impression in the first 30 seconds?"
2. "What was the most satisfying moment?"
3. "What was the most frustrating moment?"
4. "Describe the game to a friend in one sentence."

### Core Loop Validation
5. "Did you understand what you were supposed to do? When did that click?"
6. "Did the game feel fair? Any moments where you felt cheated?"
7. "What would make you want to keep playing?"

### UI/UX Validation
8. "Was anything confusing visually? Did you press things you didn't intend?"
9. "Any moments where you didn't know what to do next?"

### Design Pillar Validation
{One question per GDD pillar — e.g., if pillar is "emergent strategy", ask about strategic depth}

### Open-ended
10. "What would you change if you could change one thing?"
11. "Would you play this again? What would bring you back?"
```

---

## Step 5 — Synthesis Template

After all sessions complete, use this to compile findings:

```markdown
## Playtest Synthesis

**Sessions:** {N} | **Tester match:** {N}/{N} target demographic

### Critical Issues (block launch)
| Issue | Frequency | Evidence | Action |
|-------|-----------|---------|--------|
| {issue} | {N}/{N} testers | {quote} | {fix} |

### Design Pillar Validation
| Pillar | Confirmed? | Evidence |
|--------|-----------|---------|
| {pillar} | ✅/⚠️/❌ | {quotes} |

### Delight Moments (protect these)
{What players loved — must NOT be removed in optimization}

### Recommended Actions
1. {specific change → story or GDD update}
```

---

## Step 6 — Save

1. Create `.output/qa/` if needed.
2. Save to `.output/qa/playtest-plan.md`.
3. Report: "Playtest plan ready for {N}-session run."
4. Suggest: "After sessions, compile findings with the synthesis template and run `[qa] test-design` to convert insights into test cases."
