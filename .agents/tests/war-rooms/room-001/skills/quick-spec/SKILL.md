---
name: quick-spec
description: "Rapidly produce a feature specification"
tags: [game-designer, design, spec]
trust_level: core
---

# Workflow: Quick Spec

**Goal:** Rapidly produce a minimal but engineer-ready implementation spec for a single feature or UI screen -- when you need to start coding without a full GDD/UX process.

**Use when:** "I have a rough idea, just get me to code quickly"
**Input:** User description (inline) or screenshot/mockup
**Output:** `.output/planning/quick-specs/{feature-name}-spec.md` -- minimal spec ready for engineer

---

## Step 1 -- Capture the Idea

Ask these 5 questions (gather all at once -- don't go one by one):

1. "What is the feature/screen name?"
2. "What does the player do here? (1-3 sentences)"
3. "What does the player see? (describe or paste reference image)"
4. "What's the success condition? (what does 'done' look like?)"
5. "Any explicit constraints? (colors, existing components to use, performance notes)"

Wait for responses. If the user provides a screenshot or image, analyze it to extract UI elements automatically.

---

## Step 2 -- Generate the Spec

Write a compact spec document:

```markdown
# Quick Spec: {Feature Name}

**Created:** {date}
**Scope:** {Single screen | Single mechanic | Single system}

## What Is This?

{2-3 sentence description of the feature and player value}

## Acceptance Criteria

- [ ] Given {precondition}, When {action}, Then {result}
- [ ] Given {precondition}, When {action}, Then {result}
- [ ] {minimum 2, maximum 5 ACs}

## UI Elements (if applicable)

| Element | Type | Content | Behavior |
|---------|------|---------|---------|
| {name} | {UnityComponentType} | {text/asset} | {what it does} |

## Implementation Notes

- **Files to create:** `{ClassName}.cs` in `Assets/Scripts/{Feature}/`
- **Editor script:** `{Feature}SceneBuilder.cs` in `Assets/Editor/` (if UI)
- **Key pattern:** {which existing pattern to follow, e.g., "follows RevivePopup pattern"}
- **Must NOT:** {any explicit constraint}

## Animation (if applicable)

| Event | Duration | Pattern |
|-------|---------|---------|
| {trigger} | {Xs} | {description} |

## Out of Scope (for this ticket)

- {what's explicitly NOT being built now}
```

Present the spec: "Here's the quick spec. Approve to save, or tell me what's missing."

---

## Step 3 -- One-Round Refinement

Allow one round of feedback. Apply changes immediately. Re-present.

---

## Step 4 -- Save

1. Create `.output/planning/quick-specs/` if needed.
2. Save to `.output/planning/quick-specs/{feature-name}-spec.md`.
3. Report: "Quick spec saved."
4. Suggest: "Hand off to engineer: `[engineer] implement {feature-name}`"
