---
name: create-story
description: Create a dev story with acceptance criteria
tags: [game-designer, planning, story]

source: project
---

# Workflow: Create Story

**Goal:** Create a comprehensive, self-contained story file that gives the engineer everything needed for flawless implementation — preventing common LLM mistakes like reinventing wheels, using wrong libraries, or breaking existing patterns.

**Prerequisites:** `epics-and-stories.md` must exist
**Input:** `.output/planning/epics-and-stories.md` + optional story number
**Output:** `.output/planning/stories/{story-id}.md` — implementation-ready story with full context

---

## Step 1 — Identify Target Story

If the user provides a story ID (e.g., "E2-3" or "epic 2 story 3"):
- Load that specific story from `epics-and-stories.md`
- Confirm: "Creating story file for E{N}-{N}: {title}. Correct?"

If no story specified:
- Load `epics-and-stories.md` and find the first story that is:
  - Status: not yet in `.output/planning/stories/`
  - Priority: P1 first, then P2
- Confirm: "No story specified. Creating next up: E{N}-{N}: {title}. Correct?"

---

## Step 2 — Load All Context

Load all available context artifacts in parallel:

1. **Epics file** — the full story with acceptance criteria
2. **GDD** — `.output/design/gdd.md` — for mechanic and system context
3. **UX Design** — `.output/design/ux-design.md` — for exact screen specifications
4. **Architecture** — `.output/design/game-architecture.md` — for technology choices
5. **project-context.md** — for naming conventions, package rules, performance rules
6. **Previous story files** — check `.output/planning/stories/` for learnings from prior stories in same epic

Note any MISSING files — the story will need to include explicit notes about what's unclear.

---

## Step 3 — Analyze for Developer Guardrails

This is the most important step. Extract everything the engineer must know:

**From project-context.md:**
- Exact naming conventions for classes and files in this feature
- DI container pattern (VContainer inject point)
- Async pattern (UniTask method signatures)
- Performance rules that apply to this story

**From architecture:**
- Which module/folder this story's code belongs in
- Dependencies (what other classes/services this feature uses)
- Data flow pattern

**From UX Design:**
- Exact component types for each UI element (`TextMeshProUGUI`, `Button`, `Image`)
- Animation durations and easing curves
- Canvas structure and z-order
- Touch target sizes

**From GDD:**
- Mechanic rules (edge cases, failure conditions)
- Progression requirements

**From prior stories in same epic:**
- Patterns already established (must be consistent)
- Learnings from previous implementation
- Files already created that this story extends

---

## Step 4 — Write the Story File

Create the story file at `.output/planning/stories/E{N}-{N}-{title}.md`:

```markdown
# Story E{N}-{N}: {Title}

**Epic:** E{N} — {Epic Name}
**Size:** {S | M | L}
**Priority:** {P1 | P2 | P3}
**Assignable to:** {engineer | cv-analytics}
**Status:** ready-for-dev

---

## User Story

**As a** {player | game developer},
**I want** {specific capability},
**So that** {clear value}.

---

## Acceptance Criteria

- [ ] Given {precondition}, When {action}, Then {result}
- [ ] Given {precondition}, When {action}, Then {result}
{add all ACs from epics-and-stories.md}

---

## Developer Context (Read Before Implementing)

### Files to Create
| File | Location | Purpose |
|------|----------|---------|
| `{ClassName}.cs` | `Assets/Scripts/{Feature}/` | {description} |
| `{ClassName}SceneBuilder.cs` | `Assets/Editor/` | Editor tool to build UI |

### Files to Modify
| File | Change |
|------|--------|
| `{ExistingClass}.cs` | {what to add/change} |

### Dependencies
- `{ClassName}` from Story E{N}-{N} must be complete first
- Requires packages: {VContainer | UniTask | UniRx | etc.}

### Naming Conventions (Must Follow)
- Class: `{Feature}{Type}` e.g., `{ConcreteClassName}`
- File: Match class name exactly
- Namespace: `{Namespace}`

### Architecture Pattern
```csharp
// Example scaffold — follow this pattern exactly:
public class {Feature}Controller : IInitializable, IDisposable
{
    private readonly {Feature}Model _model;
    
    [Inject]
    public {Feature}Controller({Feature}Model model)
    {
        _model = model;
    }
    
    public void Initialize() { /* VContainer IInitializable */ }
    public void Dispose() { /* VContainer IDisposable */ }
}
```

### UI Specifications (From UX Design)
{Copy exact UI specs from ux-design.md for this screen}

- Canvas: Screen Space Overlay
- {Element name}: `{ComponentType}` — {spec}
- Fade: Use `CanvasGroup.alpha` — never `Image.color.a`

### Animation Specifications
{Copy exact animation specs}

- {Trigger}: Duration {Xs}, Pattern: {scale/fade/move description}

### Performance Rules
- [ ] No LINQ in Update() or any callback triggered per-frame
- [ ] No GetComponent<T>() in Update() — cache in Awake()/Initialize()
- [ ] All UI fades via CanvasGroup — not Image.color
- {story-specific performance rule if applicable}

### Known Pitfalls to Avoid
- {Specific thing that went wrong in prior story / known gotcha in this feature area}
- {Another pitfall}

---

## Technical Notes

{Any additional architecture decisions, third-party integration details, or edge cases}

---

## Definition of Done

- [ ] All ACs pass in Play Mode
- [ ] No compiler errors or warnings
- [ ] Scene builder creates all objects correctly (`GameObject > UI > {Feature}`)
- [ ] Runs at 60fps on target device
- [ ] No GC allocations in hot path
- [ ] Code reviewed against unity-code-review skill
```

---

## Step 5 — Validate

Before saving, confirm every section is complete:

- [ ] All ACs from epics-and-stories.md are included
- [ ] Files to create/modify are specified with exact paths
- [ ] Naming conventions explicitly stated
- [ ] Architecture pattern with code scaffold included
- [ ] UI specs include Unity component types (not just "button")
- [ ] Performance rules listed
- [ ] Known pitfalls included (even if "none identified")

Fix any incomplete sections.

---

## Step 6 — Save

1. Create `.output/planning/stories/` if needed.
2. Save to `.output/planning/stories/E{N}-{N}-{title}.md`.
3. Report: "Story file saved. Engineer has everything needed for flawless implementation."
4. Suggest: "Hand off to engineer: `[engineer] implement story E{N}-{N}`"
