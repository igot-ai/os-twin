---
name: game-architecture
description: Design Unity game systems architecture
tags: [architect, design, architecture]
trust_level: core
source: project
---

# Workflow: Game Architecture

**Goal:** Design a comprehensive Unity game architecture document that defines system structure, module boundaries, data flow, and technical decisions — ensuring all AI agents implement consistently at 60fps.

**Prerequisites:** `gdd.md` and `game-brief.md` should exist
**Input:** `.output/design/gdd.md` + `project-context.md` (if it exists)
**Output:** `.output/design/game-architecture.md` — architecture document + auto-updates `project-context.md`

**Reference:** Load `contributes/roles/game-engineer/skills/unity-coding/SKILL.md` and `contributes/roles/game-engineer/skills/unity-ugui/SKILL.md` before writing architecture — all patterns must align with these skills.

---

## Step 1 — Load Context

1. Read `contributes/roles/game-engineer/skills/unity-coding/SKILL.md` — this defines the allowed patterns (VContainer, UniTask, UniRx, Feature Module pattern)
2. Read `contributes/roles/game-engineer/skills/unity-ugui/SKILL.md` — for UI architecture constraints
3. Load `.output/design/gdd.md` — extract:
   - All game systems (mechanics, progression, monetization, social)
   - Performance targets from Section 7
   - Platform targets
4. Load `.output/design/game-brief.md` — extract core loop and scale expectations
5. Load `project-context.md` if exists — existing constraints

Present: "Loaded GDD with {N} systems. Unity constraints loaded from skills. Ready to design architecture."

---

## Step 2 — Confirm Technology Stack

Confirm or establish the foundational technology choices:

**Mandatory for all new Unity mobile projects:**
| Choice | Value | Why |
|--------|-------|-----|
| DI Container | VContainer | Fastest, compile-time safe, no reflection |
| Async | UniTask | Zero-allocation, Unity-native |
| Reactive | UniRx | Proven, good Unity integration |
| UI | TextMeshPro | Required for quality text |
| Architecture | Feature Module + Clean Architecture | Maintainable at scale |

Ask if any of these must differ from defaults. If existing project, check `manifest.json` for actual versions.

Confirm: "Technology stack confirmed. These are the constraints all code must follow."

---

## Step 3 — Identify All Game Systems

From the GDD, enumerate every system:

```
Core Systems (required for game to run):
- {system 1}: {brief description}
- {system 2}: {brief description}

Feature Systems (gameplay mechanics):
- {system}: {brief description}

UI Systems:
- {system}: {brief description}

Service Systems (infrastructure):
- {system}: {brief description}

Analytics / Monetization:
- {system}: {brief description}
```

Confirm list with user: "Here are the {N} systems I identified. Any missing or should be excluded?"

---

## Step 4 — Design System Architecture

For each system, define the module structure:

**Feature Module pattern (mandatory for each gameplay feature):**

```
Assets/Scripts/{Feature}/
├── {Feature}Controller.cs    ← Application layer, orchestrates flow
├── {Feature}Model.cs          ← Domain model, business rules
├── {Feature}View.cs           ← Presentation, subscribes to Model
├── {Feature}Installer.cs      ← VContainer bindings
├── I{Feature}Service.cs       ← Interface for testability
└── {Feature}Config.cs         ← ScriptableObject config
```

**Data flow direction (must not violate):**
```
Config (ScriptableObject)
    ↓
Controller (orchestrates)
    ↓
Model (state + business rules)
    ↓ (events/reactive)
View (renders Model state)
```

For each identified system, write:

```markdown
### System: {Name}

**Module folder:** `Assets/Scripts/{Feature}/`
**Responsibility:** {1 sentence — what this system owns}
**Consumers:** {which other systems use this}
**Dependencies:** {which systems this depends on}

**Key Classes:**
- `{FeatureName}Controller` — {orchestration responsibility}
- `{FeatureName}Model` — {state/logic responsibility}
- `{FeatureName}View` — {presentation responsibility}
- `{FeatureName}Config` (ScriptableObject) — {configurable data}

**VContainer binding:**
```csharp
// In {Feature}Installer.cs
builder.Register<{Feature}Controller>(Lifetime.Scoped).AsImplementedInterfaces().AsSelf();
builder.Register<{Feature}Model>(Lifetime.Scoped);
builder.RegisterComponentInHierarchy<{Feature}View>();
```

**Performance budget:** {frame time allotment, allocation policy}
```

---

## Step 5 — System Dependency Diagram

Create the Mermaid system diagram:

```markdown
## System Architecture Diagram

```mermaid
graph TD
    subgraph "Core Services"
        GameManager
        EventBus
        SaveService
    end
    
    subgraph "Gameplay"
        {Feature1}Controller --> {Feature1}Model
        {Feature1}Model --> {Feature1}View
        {Feature2}Controller --> {Feature2}Model
    end
    
    subgraph "UI"
        HUDController --> HUDView
        PopupManager --> BasePopup
    end
    
    GameManager --> {Feature1}Controller
    GameManager --> {Feature2}Controller
    {Feature1}Model --> EventBus
    EventBus --> HUDController
```
```

After writing diagram, ask: "Does this system diagram capture all the relationships? Any missing connections?"

---

## Step 6 — Cross-Cutting Concerns

Define standards for concerns that span all systems:

```markdown
## Cross-Cutting Concerns

### Error Handling
- All async operations: `UniTask` with `.SuppressCancellationThrow()` on token cancellation
- User-visible errors: route through `ErrorService` — never show raw exceptions
- Logging: `Debug.Log` in dev builds only — use `[Conditional("UNITY_EDITOR")]`

### Event System
- Cross-system events: `UniRx Subject<T>` on `EventBus` (singleton service)
- Intra-module events: Direct `UniRx Subject<T>` on Model
- Never: C# events across module boundaries (creates tight coupling)

### Save System
- Format: {JSON / Binary / PlayerPrefs}
- When to save: {on each significant event / on pause / on level complete}
- Save data is in `{FeatureName}SaveData` plain C# classes — no MonoBehaviour
- Encryption: {Yes/No, and how}

### Scene Management
- Main game scene: persistent (never reload)
- Additive loading: sub-scenes for heavy content
- Never: `SceneManager.LoadScene` with hardcoded strings — use `SceneRef` ScriptableObjects

### Asset Loading
- UI sprites: Load via `UnityEngine.AddressableAssets` — never `Resources.Load`
- Audio: {AudioManager pattern}
- Large assets: async load on demand — never synchronous in hot path

### Testing Strategy
- Unit tests: NUnit in EditMode — all Model classes must be unit-testable
- Integration tests: PlayMode with VContainer test containers
- Performance tests: Unity Performance Testing package for hot paths
```

---

## Step 7 — Performance Architecture

```markdown
## Performance Architecture

### 60fps Budget
Target device: {device specification}
Total frame budget: 16.67ms (60fps)

| System | Budget | Allocation Policy |
|--------|--------|------------------|
| Gameplay logic | 3ms | Zero allocation |
| Physics | 2ms | Fixed update, pooled |
| UI updates | 2ms | Event-driven only, no per-frame |
| Rendering | 8ms | {draw call budget} |
| Audio | 1ms | — |
| Overhead | 0.67ms | — |

### GC Policy
- Hot path: Zero allocation per frame
- Initialization: Allocation allowed
- Object pooling: Required for {projectiles / particles / UI elements / etc.}
- Collections: Pre-allocate with capacity, never resize in gameplay

### Unity-Specific Optimizations
- Canvas.enabled = false (not destroy) for hidden UI
- Single root Canvas per screen — multiple child Canvases for animated elements
- Static batching: enabled for all non-animated scenery
- Texture atlases: {one atlas per screen / feature}
```

---

## Step 8 — Architecture Decision Log

```markdown
## Architecture Decision Log

| # | Decision | Chosen | Alternatives Considered | Rationale |
|---|----------|--------|------------------------|-----------|
| 1 | DI Container | VContainer | Zenject, Manual DI | Fastest, no reflection, compile-safe |
| 2 | Async | UniTask | Coroutines, Task | Zero allocation, cancellation support |
| 3 | State Management | UniRx + Model | MVC, MVVM custom | Reactive = UI updates automatically |
| {N} | {decision} | {chosen} | {alternatives} | {why} |
```

---

## Step 9 — Validate Against GDD Pillars

For each GDD pillar, confirm the architecture supports it:

| Pillar | How Architecture Supports It | Risk |
|--------|------------------------------|------|
| {Pillar 1} | {concrete architectural choice that enables it} | {none/low/medium} |
| {Pillar 2} | ... | ... |

Flag any ❌ (architecture decision that works against a pillar).

---

## Step 10 — Save

1. Create `.output/design/` if needed.
2. Save to `.output/design/game-architecture.md`.
3. Also update `project-context.md` with the confirmed package versions and key rules.
4. Report: "Architecture saved. project-context.md updated."
5. Suggest next steps:
   - "Run `[architect] check-implementation-readiness` to validate all artifacts"
   - "Run `[game-designer] create epics and stories` if not done yet"
