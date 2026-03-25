---
name: build-anim
description: Build Unity UI animations from a reference video and an animation_detection.json. Analyses the JSON for keyframe data (position, scale, opacity, timing), identifies animated object categories (tiles, effects, text pop-ups, particles), writes generalised C# coroutine scripts, wires them to scene GameObjects via MCP tools, and validates in Play Mode. Trigger on 'build animation', 'implement animation from video', 'animate this UI', 'set up animations', 'wire up animation scripts', 'create animation system', or when the user provides an animation_detection.json and a reference video. Also invoke proactively when the user has run detect-anim and has the JSON output but hasn't yet built the runtime scripts. Run this after detect-anim.
argument-hint: <animation_detection_json_path> <reference_video_path> [gdd_path] [scene_name]
---

# Build Animation from Detection JSON

Translate animation data from `animation_detection.json` (output of `detect-anim`) into runtime C# coroutine scripts and wire them to scene GameObjects using Unity MCP tools.

> [!IMPORTANT]
> The detection JSON and reference video are **references, not blueprints**. Generalise to cover all similar objects in the scene (e.g. all tiles, not just the one shown in the video). Base your implementation on object categories, not exact object names.

---

## Architecture

```
animation_detection.json (v6.0.0)          Reference Video
┌───────────────────────────────┐         ┌──────────────────┐
│ animated_objects[]            │         │  Visual reference │
│  ├─ id, display_name         │         │  for timing and   │
│  ├─ object_category          │ ──────→ │  motion feel      │
│  ├─ motion_type, animation_type│        └──────────────────┘
│  ├─ trigger                  │
│  ├─ target { path, apply_to, │
│  │   required_components,    │
│  │   initial_state }         │
│  ├─ tracks[]                 │
│  │   └─ component, property, │
│  │       channels, keyframes[]│
│  ├─ total_duration_sec       │
│  ├─ relationships[]          │
│  └─ source_evidence          │
│                               │
│ animation_sequences[]         │
│  └─ steps[] (ordered flow)   │
│                               │
│ easing_library               │
│  └─ named easing → C# code  │
│                               │
│ scene_wiring                 │
│  └─ overlay, slots, tiles    │
└───────────────────────────────┘
              │
              ▼
┌───────────────────────────────────────────────────────────┐
│                  Build Animation Pipeline                  │
│                                                           │
│  1. Read JSON → map animated_objects by object_category   │
│  2. Generate C# coroutine scripts per category            │
│  3. Create supporting GameObjects (overlay, effects, text)│
│  4. Wire scripts to GameObjects via MCP                   │
│  5. Save scene                                            │
│  6. Play Mode validation                                  │
└───────────────────────────────────────────────────────────┘
```

---

## Inputs

Parse `$ARGUMENTS` as:
- `$0` — `animation_detection.json` path (output of `detect-anim`)
- `$1` — reference video path (.mp4 / .mov) — visual timing reference
- `$2` — (optional) GDD / design doc path — game design context
- `$3` — (optional) scene name — target scene to animate; defaults to the active scene

---

## Step 1 — Read & Analyse Inputs

### 1.1 — Read the animation detection JSON (v6.0.0)

Read `$0` and extract:
- `"schema"` — must be `"6.0.0"` (validate this first)
- `easing_library` — shared easing functions with C# implementations
- `animated_objects[]` — each entry has: `id`, `display_name`, `object_category`, `motion_type`, `animation_type`, `trigger`, `target`, `tracks[]`, `total_duration_sec`, `relationships[]`
- `tracks[]` — each has: `component`, `property`, `channels`, `keyframes[]` (with `time_sec`, `values`/`value`, `easing`)
- `animation_sequences[]` — ordered step flows linking animated objects
- `scene_wiring` — hints for finding/creating supporting GameObjects

### 1.2 — Read the reference video (optional)

View `$1` to understand visual timing and motion feel. Use frame captures if the video tool supports it.

### 1.3 — Read the GDD (if provided)

Read `$2` to understand:
- Game mechanic context (what triggers animations)
- Interaction flow (tap → animate → result)
- Win/lose conditions that affect animation sequencing

### 1.4 — Inspect the scene hierarchy

Use MCP tools to understand the current scene structure:

```
scene-list-opened → scene-get-data → gameobject-find
```

Build a mental map of:
- **Root canvas** and its children
- **Repeated object groups** (tiles, cards, slots, hearts, stars)
- **Containers** that will need animation children (overlay layers, effect holders)
- **Existing components** (Button, Image, CanvasGroup) already on GameObjects

---

## Step 2 — Classify Animated Objects

From the JSON `animated_objects[]`, group entries by their **`object_category`** field:

| `object_category` | Description | Typical Script Pattern |
|---|---|---|
| `"interactive_element"` | Tappable object that triggers an animation sequence (tile, card, button) | Data component (type/ID) + Animator component (pickup/fly/shatter) |
| `"container"` | Manages a group of slots or positions (rack, hand, grid) | Controller component (insert, match, shift, compact) |
| `"effect"` | Visual feedback on an action (particles, sparkle, burst) | Effect component (play/stop, driven by CanvasGroup alpha) |
| `"text_feedback"` | Text that pops in/out ("Awesome!", "Combo!", score) | Text animator (scale pop, fade out, driven by CanvasGroup) |
| `"overlay"` | Full-screen or regional layer for rendering order | Just a RectTransform (stretch anchors, no script needed) |

For each animated object, note:
- Its `trigger` — what starts the animation
- Its `tracks[]` — the actual keyframe data to embed as C# constants
- Its `relationships[]` — which other objects it connects to
- Its `target` — scene path, components needed, initial state

> [!TIP]
> Not every animated object maps 1:1 to a script. Objects with the same `object_category` + similar `animation_type` can share a single script class (e.g., all tiles share one `TileAnimator` script). Separate objects that have distinct lifecycles.

---

## Step 3 — Design Script Architecture

For each behaviour category, design a C# MonoBehaviour script. Follow these principles:

### 3.1 — Generalisation rules

- **Never hardcode object names**. Use a data component (e.g. `TileData.TileType`) for identity.
- **Auto-discover objects at runtime**. Use `GetComponentsInChildren<T>()` instead of manual inspector assignment for repeated elements.
- **Inject shared references in Awake/Start**. The root controller passes shared resources (overlay layer, effect references) to child animators.
- **Use string or enum for type matching**. Allow the controller to group/match any objects of the same type without knowing what types exist.

### 3.2 — Coroutine patterns

All animations use pure C# coroutines. No DOTween, no Animator. This ensures:
- Zero external dependencies
- Full timing control from the detection JSON
- Easy modification

**Standard coroutine template:**
```csharp
private IEnumerator AnimateProperty(float duration, System.Action<float> setter, System.Func<float, float> easing)
{
    float elapsed = 0f;
    while (elapsed < duration)
    {
        float t = easing(elapsed / duration);
        setter(t);
        elapsed += Time.deltaTime;
        yield return null;
    }
    setter(1f);
}
```

### 3.3 — Visibility via CanvasGroup, not SetActive

> [!CAUTION]
> **Never use `gameObject.SetActive(false)` to hide effect/text GameObjects.** `StartCoroutine` fails on inactive GameObjects. Instead:
> - Use `CanvasGroup.alpha = 0f` + `blocksRaycasts = false` to hide
> - Use `CanvasGroup.alpha = 1f` to show
> - Keep the GameObject always active

### 3.4 — Lifecycle safety

- Add `OnDestroy() { StopAllCoroutines(); }` to every script that starts coroutines.
- Use `?.Invoke()` for all callbacks to avoid null reference exceptions.
- Disable `Button.interactable` immediately on interaction to prevent double-taps.

### 3.5 — Keyframe mapping from v6.0.0 JSON

Map JSON keyframe data directly to coroutine constants:

```
animated_objects[].tracks[].keyframes[].time_sec  →  C# const float Duration (or inline timing)
animated_objects[].tracks[].keyframes[].easing    →  Reference easing_library[name].csharp
```

Easing functions come from the JSON's `easing_library`:

```csharp
// Directly from easing_library.ease_out.csharp:
static float EaseOut(float t) => 1f - (1f - t) * (1f - t);

// Directly from easing_library.ease_in.csharp:
static float EaseIn(float t) => t * t;

// Directly from easing_library.ease_in_out.csharp:
static float EaseInOut(float t) => t < 0.5f ? 2f * t * t : 1f - Mathf.Pow(-2f * t + 2f, 2f) / 2f;

// Directly from easing_library.linear.csharp:
static float Linear(float t) => t;
```

The `animation_sequences` section tells you the execution order — use this to implement the sequencing logic in controller scripts.

---

## Step 4 — Write C# Scripts

### 4.1 — Script placement

All animation scripts go under `Assets/Game/Scripts/Animation/`.
Use a namespace matching the level/feature (e.g. `Level11.Animation`).

### 4.2 — Typical script set (adapt per project)

Based on the `object_category` values found in the JSON, write scripts. Map categories to script classes:

| `object_category` | Script | Attached To | Responsibility |
|---|---|---|---|
| `"interactive_element"` | `[Element]Data.cs` | Every interactive element | Carries type/identity for matching |
| `"interactive_element"` | `[Element]Animator.cs` | Every interactive element | Per-element animations from `tracks[]` |
| `"container"` | `[Container]Controller.cs` | Container GO | Slot management, match detection, shift/compact, orchestrate sequence |
| `"effect"` | `[Effect]Effect.cs` | Effect GO | Particle/burst animation driven by CanvasGroup |
| `"text_feedback"` | `[Feedback]TextAnimator.cs` | Text GO | Scale-pop + fade text feedback |
| (root) | `[Root]PickupController.cs` | Root canvas GO | Auto-discovers elements, wires Button.onClick, enforces accessibility |

### 4.3 — Write and compile

For each script:
1. Write the `.cs` file to `Assets/Game/Scripts/Animation/`
2. Call `assets-refresh` to trigger compilation
3. Check `console-get-logs` for compile errors
4. Fix any errors before proceeding

---

## Step 5 — Create Supporting GameObjects

Before wiring scripts, create any new GameObjects needed:

### 5.1 — Identify needed GOs

From Step 2, determine which behaviour categories need new GameObjects:
- **Overlay layer** — a stretch-anchored RectTransform for rendering animated elements above the board
- **Effect holders** — GameObjects for particle/shatter effects
- **Text feedback** — GameObjects with TextMeshProUGUI for "Awesome!" etc.

### 5.2 — Create via MCP or script-execute

Use `gameobject-create` for simple GOs. For complex setup (RectTransform stretch anchors, adding multiple components), prefer `script-execute` with a C# script:

```csharp
// Example: configure a stretch-anchored overlay
var go = GameObject.Find("UI_Root").transform.Find("AnimationLayer");
var rt = go.GetComponent<RectTransform>();
rt.anchorMin = Vector2.zero;
rt.anchorMax = Vector2.one;
rt.offsetMin = Vector2.zero;
rt.offsetMax = Vector2.zero;
```

### 5.3 — Add required components

For effects and text feedback GOs, add:
- `CanvasGroup` (for alpha-based visibility)
- `Image` (for effects that need a visual)
- `TextMeshProUGUI` (for text feedback)

Set initial `CanvasGroup.alpha = 0` so they start invisible.

---

## Step 6 — Wire Scripts to GameObjects

### 6.1 — Add scripts to GameObjects

Use `script-execute` to batch-add components and set references:

```csharp
// Add TileData + TileAnimator to all tiles
foreach (Transform tile in boardArea.transform)
{
    if (tile.GetComponent<TileData>() == null)
        tile.gameObject.AddComponent<TileData>();
    if (tile.GetComponent<TileAnimator>() == null)
        tile.gameObject.AddComponent<TileAnimator>();
}
```

### 6.2 — Set inspector references

Wire cross-references between scripts:
- Controller → Effect references
- Controller → Slot references
- Root controller → Container, AnimationLayer references

### 6.3 — Set element data

Assign type/identity values to each element's data component:
- Map element names to type strings based on the scene structure
- Group similar visual elements under the same type

### 6.4 — Verify EventSystem

> [!WARNING]
> Unity UI requires an `EventSystem` in the scene for Button clicks to work. Check for its presence and add one if missing. If the project uses the **new Input System package**, use `InputSystemUIInputModule` instead of `StandaloneInputModule`.

```csharp
if (Object.FindObjectOfType<EventSystem>() == null)
{
    var es = new GameObject("EventSystem");
    es.AddComponent<EventSystem>();
    // Check Input System: use InputSystemUIInputModule if new Input System is active
    es.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
}
```

### 6.5 — Save scene

```
scene-save
```

---

## Step 7 — Play Mode Validation (MANDATORY)

> [!IMPORTANT]
> Do NOT skip runtime validation. Scene-time wiring errors (null refs, inactive GOs, missing EventSystem) are only caught at runtime.

### 7.1 — Enter Play Mode

```
editor-application-set-state → isPlaying = true
```

### 7.2 — Check startup logs

```
console-get-logs (lastMinutes=1, logTypeFilter=Error)
```

Look for:
- **NullReferenceException** — missing inspector refs (AnimationLayer, Slots, etc.)
- **Coroutine couldn't be started** — GO is inactive (fix: use CanvasGroup, not SetActive)
- **Input System mismatch** — wrong InputModule on EventSystem
- **Missing component** — script not compiled or not added

### 7.3 — Validate interactions

Use `console-get-logs` to confirm:
- Controller registration log (e.g. `"Registered N elements. Accessible at start: M."`)
- No runtime errors appeared after startup

### 7.4 — Capture Game View

Use `screenshot-game-view` to visually confirm:
- Scene renders correctly
- UI elements are visible and positioned properly

### 7.5 — Exit Play Mode

```
editor-application-set-state → isPlaying = false
```

### 7.6 — Fix & re-test loop

If any errors found:
1. Fix the root cause in the C# script or scene wiring
2. `assets-refresh`
3. Re-enter Play Mode
4. Re-check logs
5. Repeat until zero errors

---

## Step 8 — Code Review

Trigger `unity-code-review` on all new/modified `.cs` files under `Assets/Game/Scripts/Animation/`.

Review dimensions:
- **SOLID principles** — single responsibility per script
- **Unity best practices** — lifecycle safety, coroutine cleanup
- **Mobile performance** — no per-frame GC allocations
- **Logic correctness** — match detection, slot shifting, edge cases

Fix all **Critical** findings. Document **Warning** exceptions.

---

## Common Pitfalls (lessons from real implementations)

### Pitfall 1 — SetActive vs CanvasGroup
**Problem:** Effect/text GO uses `SetActive(false)` in Awake, then `SetActive(true)` + `StartCoroutine` in Play. Unity re-triggers Awake on SetActive(true), which re-hides the GO, then StartCoroutine fails on the now-inactive GO.
**Fix:** Keep GO always active. Use `CanvasGroup.alpha = 0` to hide.

### Pitfall 2 — Missing EventSystem
**Problem:** All Button.onClick listeners registered correctly but clicks don't fire.
**Fix:** Add EventSystem + correct InputModule to scene.

### Pitfall 3 — Wrong InputModule
**Problem:** `StandaloneInputModule` throws `InvalidOperationException: You are trying to read Input using the UnityEngine.Input class, but you have switched active Input handling to Input System package`.
**Fix:** Use `InputSystemUIInputModule` when the project has the new Input System package.

### Pitfall 4 — Blocked element accessibility
**Problem:** Interactive elements have a visual overlay child (e.g. "Block") that indicates they're covered. All elements appear clickable but nothing happens.
**Fix:** Check for overlay children and set `Button.interactable = false` for blocked elements. Add debug logs to the click handler to surface silent rejections.

### Pitfall 5 — Inspector refs not serialised
**Problem:** References set via `script-execute` at Edit time may not persist if the setting code doesn't call `EditorUtility.SetDirty()` and save the scene.
**Fix:** Always call `EditorUtility.SetDirty(targetGO)` after modifying components via script-execute, then `scene-save`.

---

## Mandatory Execution Checklist

- [ ] Read animation_detection.json — verify `schema: "6.0.0"`
- [ ] Extract `animated_objects` grouped by `object_category`
- [ ] Extract `animation_sequences` for execution flow
- [ ] Extract `easing_library` for C# easing implementations
- [ ] Read GDD (if provided) for game mechanic context
- [ ] Inspect scene hierarchy — match `target.path` entries to real GameObjects
- [ ] Write C# scripts — one per behaviour category, generalised for all similar objects
- [ ] Embed timing constants from `tracks[].keyframes[]` directly into scripts
- [ ] Implement sequence logic from `animation_sequences[].steps[]`
- [ ] Compile check — zero errors
- [ ] Create supporting GameObjects per `scene_wiring` hints
- [ ] Wire scripts to GameObjects with correct inspector refs
- [ ] Verify EventSystem present with correct InputModule
- [ ] Set element data (type/ID) on all relevant GameObjects
- [ ] Save scene
- [ ] **Play Mode test** — enter Play, check logs, capture screenshot, exit
- [ ] Fix any runtime errors and re-test
- [ ] Code review via `unity-code-review`
- [ ] All Critical findings resolved

---

## Output

- C# coroutine scripts under `Assets/Game/Scripts/Animation/`
- Scene GameObjects wired with scripts and correct references
- Scene saved with EventSystem, supporting GOs, and all wiring complete
- Zero compile and zero runtime errors confirmed via Play Mode test
