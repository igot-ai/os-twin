---
name: generate-project-context
description: Generate project-context.md for codebase understanding
tags: [architect, context, documentation]
trust_level: core
source: project
---

# Workflow: Generate Project Context

**Goal:** Create a concise, AI-optimized `project-context.md` file containing the critical rules, patterns, and conventions that all AI agents must follow when implementing game code. This file is the single source of truth for agent consistency.

**Prerequisites:** Unity project must exist with `ProjectSettings/ProjectVersion.txt` or existing codebase
**Input:** Existing project files, `PackageManager/manifest.json`, existing scripts
**Output:** `project-context.md` in the project root (or `.output/project-context.md`)

---

## Step 1 — Discover Existing Context

1. Search for existing `**/project-context.md`. If found:
   - Read it completely
   - Ask: "Found existing project context. Update it or create fresh? (U/F)"
2. Check Unity project identity:
   - Read `ProjectSettings/ProjectVersion.txt` → extract Unity version
   - Read `Packages/manifest.json` → identify key packages (VContainer, UniTask, UniRx, TMP, etc.)
3. Scan existing C# scripts for patterns:
   - Naming conventions (class names, file names, namespace patterns)
   - Architecture patterns (MonoBehaviour usage, ScriptableObject patterns, DI containers)
   - Folder structure patterns

Present summary: "**Discovered:** Unity {version}, {N} packages, {N} existing scripts, {N} naming patterns."

---

## Step 2 — Identify Critical Implementation Rules

Ask the user these targeted questions to capture rules that LLMs commonly get wrong:

**Group 1: Architecture Rules**
- "What DI container do you use? (VContainer / Zenject / None)"
- "What async pattern? (UniTask / Coroutines / async-await native)"
- "What reactive pattern? (UniRx / R3 / Custom events / None)"
- "What is your feature module structure? (e.g., Feature/Controller, Feature/Model, Feature/View)"

**Group 2: Unity-Specific Rules**
- "Any MonoBehaviour lifecycle rules? (e.g., never use Awake for dependency injection)"
- "Performance rules? (e.g., no LINQ in Update, no GetComponent in Update, pool all objects)"
- "Assembly definition rules? (each feature = its own .asmdef?)"
- "Any editor script conventions? (MenuItems path format, where editor scripts live)"

**Group 3: Naming & Organization**
- "Class naming pattern? (e.g., Feature + Type suffix: ReviveController, ReviveModel)"
- "Test file naming? (e.g., ClassName.Tests.cs, ClassName_Tests.cs)"
- "Asset naming? (e.g., btn_name_variant.png, icn_name.png)"

Wait for answers. Compile into rules.

---

## Step 3 — Generate project-context.md

Write the file with this structure:

```markdown
# Project Context

> AI agent reference file. Read this before implementing any code.
> Generated: {date}

## Project Identity

- **Engine:** Unity {version}
- **Platform:** {iOS | Android | Both}
- **Architecture:** {pattern — e.g., Feature Module + VContainer DI + UniTask}
- **Target device:** {e.g., iPhone 12 / mid-range Android}

## Key Packages

| Package | Version | Purpose |
|---------|---------|---------|
| VContainer | {ver} | Dependency injection |
| UniTask | {ver} | Async/await |
| UniRx | {ver} | Reactive extensions |
| TextMeshPro | {ver} | Text rendering |
| {others} | | |

## Critical Rules (Must Follow)

### Architecture Rules
- {DI rule: e.g., "Always inject via VContainer — never use Singleton pattern"}
- {Async rule: e.g., "Use UniTask for all async — never use Task or Thread"}
- {Reactive rule: e.g., "Use UniRx Subject for all events — never use C# events"}

### Unity Lifecycle Rules
- {e.g., "Never use Awake() for DI injection — use VContainer lifecycle hooks"}
- {e.g., "Inject in Constructor, Initialize in VContainer IInitializable.Initialize()"}

### Performance Rules (60fps Non-Negotiable)
- No LINQ in Update() or any hot path
- No GetComponent<T>() in Update() — cache in Awake()
- No string concatenation in hot path — use StringBuilder
- No allocation in hot path — use object pooling
- CanvasGroup for all UI fades — never change Canvas alpha directly
- Disable Canvas on hide, do not destroy/recreate

### Naming Conventions
- **Classes:** {FeatureName}{Type} — e.g., `ReviveController`, `ReviveModel`, `ReviveView`
- **Files:** Match class name — `ReviveController.cs`
- **Tests:** `{ClassName}.Tests.cs` in `Tests/` folder
- **Assets:** {pattern — e.g., `btn_name_variant.png`, `icn_name.png`}
- **Namespaces:** {pattern — e.g., `GameName.Feature.SubSystem`}

### Folder Structure
```
Assets/
├── Scripts/
│   └── {Feature}/
│       ├── {Feature}Controller.cs
│       ├── {Feature}Model.cs
│       ├── {Feature}View.cs
│       └── Tests/
├── Editor/
│   └── {Feature}SceneBuilder.cs   ← [MenuItem] scripts
├── UI/
│   └── {Feature}/                  ← sprites and assets
└── Prefabs/
    └── {Feature}/
```

### Editor Script Rules
- All editor scripts in `Assets/Editor/` — never in runtime `Scripts/`
- `[MenuItem]` path: `"GameObject/UI/{Feature}"` or `"Tools/{Feature}"`
- Always call `AssetDatabase.SaveAssets()` and `AssetDatabase.Refresh()` at end

### Test Rules
- Edit Mode tests in `Assets/Tests/EditMode/`
- Play Mode tests in `Assets/Tests/PlayMode/`
- Test class follows `{ClassName}Tests` pattern
- Mock with NSubstitute or custom test doubles — no live Unity services in unit tests

## Integration Points

{List any external SDKs, services, or third-party integrations with their initialization patterns}

## Existing Patterns to Follow

{List 2-5 key existing patterns that new code must mirror — e.g., "RevivePopup pattern for all popups"}

## Known Pitfalls

{List 2-5 specific things that went wrong before and must not be repeated}
```

After writing, confirm: "project-context.md drafted. Review and confirm? (C to save / E to edit)"

---

## Step 4 — Validate

Before saving, confirm:
- [ ] Unity version included
- [ ] All key packages listed
- [ ] At least 3 architecture rules
- [ ] At least 3 performance rules
- [ ] Naming conventions specified
- [ ] Folder structure documented

Fix any missing sections.

---

## Step 5 — Save

1. Create output directory if needed.
2. Save to `project-context.md` at project root (or `.output/project-context.md` if no Unity project found).
3. Report: "project-context.md saved. All AI agents will now follow these rules."
4. Suggest next step: "Run `[architect] game-architecture` to design the system architecture using this context."
