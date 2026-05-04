---
name: build-anim
description: Build Unity UI animations from a reference video and an animation detection JSON. Analyses the JSON for keyframe data (position, scale, opacity, timing), identifies animated object categories (tiles, effects, text pop-ups, particles), writes PrimeTween-based C# scripts with UniTask async orchestration, wires them to scene GameObjects via MCP tools, and validates in Play Mode. Trigger on 'build animation', 'implement animation from video', 'animate this UI', 'set up animations', 'wire up animation scripts', 'create animation system', or when the user provides an animation detection JSON and a reference video. Also invoke proactively when the user has run detect-anim and has the JSON output but hasn't yet built the runtime scripts."
argument-hint: <animation_detection_json_path> <reference_video_path> [gdd_path] [scene_name]
---

**Quick Start:** Read animation_clips JSON (v6.1.0) from `unity-animation-analyzer` -> classify objects by category -> write PrimeTween + UniTask C# scripts -> wire to scene via MCP -> validate in Play Mode.

> [!IMPORTANT]
> **This project uses PrimeTween (v1.3.7) for all animation.** Do NOT use coroutines, DOTween, or manual `while(elapsed < duration)` loops. Use `Tween.*` / `Sequence.Create()` / `await seq.ToUniTask()`.

---

## Inputs

Parse `$ARGUMENTS` as:
- `$0` -- `animation_detection.json` path (output of `unity-animation-analyzer`)
- `$1` -- reference video path (.mp4 / .mov) -- visual timing reference
- `$2` -- (optional) GDD / design doc path
- `$3` -- (optional) scene name (defaults to active scene)

---

## Step 1 -- Read & Validate Inputs

### 1.1 -- Validate the detection JSON

Read `$0` and check `"schema"` field:
- `"6.1.0"` -- proceed normally
- `"6.0.0"` -- proceed with caution: `source_category` and `path_validated` fields may be missing. Treat `object_category` as the animation role enum. Log a warning.
- Other or missing -- stop and ask the user to re-run `unity-animation-analyzer`

### 1.2 -- Extract key data

- `easing_library` -- shared easing with `prime_tween_ease` mappings
- `animated_objects[]` -- each has: id, object_category, tracks[], relationships[], target
- `animation_sequences[]` -- ordered step flows (may be absent)
- If `animation_sequences` is missing, generate a flat sequence from `animated_objects` grouped by trigger value

### 1.3 -- Resolve unvalidated target paths

If any `target.path_validated: false` entries exist:
1. Use `gameobject-find` to search for the object by name
2. If found, update the path and mark validated
3. If not found, create the GameObject (Step 5)
4. Log all resolutions

### 1.4 -- Determine FeatureName

The `{FeatureName}` placeholder is used for namespace and file placement. Determine it from:
1. The scene name if it maps to a known feature (e.g., `GameScene` -> `Gameplay`, `RefillPopup` -> `Refill`)
2. The `meta.scene` field in the JSON
3. The detection JSON filename (e.g., `refill_popup_detect.json` -> `Refill`)
4. Ask the user if ambiguous

### 1.5 -- Inspect the scene hierarchy

Use MCP tools to understand the current scene:

```
scene-list-opened -> scene-get-data -> gameobject-find
```

Map: root canvas, repeated object groups, containers, existing components.

If MCP tools unavailable, generate scripts only (no scene wiring). Document manual wiring steps in the output.

---

## Step 2 -- Classify Animated Objects

Group `animated_objects[]` by `object_category`:

| `object_category` | Script Pattern | Sharing Rule |
|---|---|---|
| `"interactive_element"` | Data component + PrimeTween animator | Same category + similar animation_type -> share one class |
| `"container"` | Controller with PrimeTween sequences | Usually unique per container |
| `"effect"` | PrimeTween alpha/scale effect | Shared if same animation_type |
| `"text_feedback"` | PrimeTween punch scale + fade | Shared across text popups |
| `"overlay"` | Just RectTransform (no script needed) | N/A |

Objects with the same `object_category` and similar `animation_type` can share a single script class. Objects with distinct lifecycles need separate classes.

---

## Step 3 -- Write C# Scripts

### 3.1 -- Script placement

Place scripts alongside the feature:
- Path: `Assets/Game/Scripts/Features/{FeatureName}/Animation/`
- Namespace: `Game.Features.{FeatureName}.Animation`

### 3.2 -- Core PrimeTween patterns

Map detection JSON fields to PrimeTween API:

```csharp
// Scale (tap_feedback, popup_enter/exit, pulse)
Tween.Scale(transform, endValue, duration, ease: Ease.InOutQuad);

// Fade (fade_in, fade_out, overlay)
Tween.Alpha(canvasGroup, endValue, duration, ease: Ease.OutQuad);

// Position (trajectory, slide)
Tween.UIAnchoredPosition(rect, endValue, duration, ease: Ease.OutQuad);

// Punch (juicy feedback)
Tween.PunchScale(transform, strength, duration, frequency: 10);

// Sequence composition
Sequence.Create()
    .Chain(tween1)         // sequential
    .Group(tween2)         // parallel with previous
    .ChainDelay(0.3f);     // wait
```

### 3.3 -- Easing mapping

Map directly from the JSON `easing_library.prime_tween_ease` field:

| JSON `easing` | `PrimeTween.Ease` |
|---|---|
| `"linear"` | `Ease.Linear` |
| `"ease_in"` | `Ease.InQuad` |
| `"ease_out"` | `Ease.OutQuad` |
| `"ease_in_out"` | `Ease.InOutQuad` |
| `"spring"` | `Ease.OutBack` |
| `"constant"` | Set value directly (no tween) |

### 3.4 -- Worked example: JSON object -> C# code

Given this detection JSON entry:
```json
{
  "id": "btn_refill_tap",
  "object_category": "interactive_element",
  "animation_type": "tap_feedback",
  "tracks": [{
    "component": "RectTransform", "property": "localScale",
    "keyframes": [
      { "time_sec": 0.00, "values": [1.0, 1.0, 1.0], "easing": "ease_in_out" },
      { "time_sec": 0.15, "values": [0.95, 0.95, 1.0], "easing": "ease_in_out" },
      { "time_sec": 0.30, "values": [1.0, 1.0, 1.0] }
    ]
  }],
  "total_duration_sec": 0.30
}
```

Generate:
```csharp
public Tween PlayTapFeedback()
{
    return Sequence.Create()
        .Chain(Tween.Scale(transform, new Vector3(0.95f, 0.95f, 1f), 0.15f, ease: Ease.InOutQuad))
        .Chain(Tween.Scale(transform, Vector3.one, 0.15f, ease: Ease.InOutQuad));
}
```

Decision: PrimeTween (not Animator) because this is a one-shot, data-driven, code-triggered feedback animation.

### 3.5 -- Mandatory patterns

- **Visibility**: Use `CanvasGroup.alpha = 0` to hide (never `SetActive(false)` -- tweens won't play on inactive GOs)
- **Lifecycle**: Add `OnDestroy() { Tween.StopAll(onTarget: this); }` to every script
- **Callbacks**: Use static delegate pattern for zero-alloc (see `references/code-templates.md`)
- **Cleanup**: `CompositeDisposable` + `.AddTo(compositeDisposable)` for UniRx
- **DI**: Use `[Inject] Construct()` for VContainer injection, not `Awake()`
- **Designer-tweakable**: Use `TweenSettings<T>` for timing designers may adjust

### 3.6 -- Compile check

After writing each script:
1. `assets-refresh` to trigger compilation
2. `console-get-logs` for compile errors
3. Fix errors before proceeding

For complete code templates, read `references/code-templates.md`.

---

## Step 4 -- Create Supporting GameObjects

From Step 2, identify GOs that need to be created:

| Category | GO Setup |
|---|---|
| Overlay layer | Stretch-anchored RectTransform + CanvasGroup |
| Effect holders | GO with CanvasGroup (alpha=0, blocksRaycasts=false) |
| Text feedback | GO with TMP_Text + CanvasGroup (alpha=0) |

Follow uGUI 2.0 patterns from `unity-ui`:
- Canvas: ScaleWithScreenSize, 1080x1920, Match 0.5
- Stretch anchoring for overlays
- Center anchoring for popups

Use `gameobject-create` + `gameobject-component-add` via MCP. For complex RectTransform setup, use `script-execute`.

---

## Step 5 -- Wire Scripts to Scene

### 5.1 -- Add scripts to GameObjects

Use `gameobject-component-add` or `script-execute` for batch operations.

### 5.2 -- Set inspector references

Wire cross-references using `script-execute`. Always call `EditorUtility.SetDirty()` after modifying components.

### 5.3 -- PrimeTween vs Animator decision

| Criterion | PrimeTween (default) | Animator via MCP |
|---|---|---|
| One-shot feedback, data-driven | Yes | No |
| Runtime-computed values | Yes | No |
| Complex state machine | No | Yes |
| Designer-editable curves | No | Yes |

For Animator Controller creation workflow, read `references/mcp-workflow.md`.

### 5.4 -- Verify EventSystem

Unity UI requires an EventSystem for Button clicks. Check for its presence. If the project uses the new Input System, use `InputSystemUIInputModule`.

### 5.5 -- Save scene

```
scene-save
```

---

## Step 6 -- Play Mode Validation (MANDATORY)

> [!IMPORTANT]
> Do NOT skip. Scene-time wiring errors (null refs, inactive GOs, missing EventSystem) are only caught at runtime.

1. Enter Play Mode (`editor-application-set-state -> isPlaying = true`)
2. Check startup logs: `console-get-logs (lastMinutes=1, logTypeFilter=Error)`
   - NullReferenceException -> missing inspector refs
   - PrimeTween warnings -> capacity exceeded or target destroyed
   - Input System mismatch -> wrong InputModule
3. Capture Game View screenshot to confirm visual correctness
4. Exit Play Mode

### Fix & re-test loop

If errors found: fix root cause -> `assets-refresh` -> re-enter Play Mode -> re-check -> repeat until zero errors.

---

## Step 7 -- Code Review

Trigger `unity-code-review` on all new/modified `.cs` files.

Review checklist:
- **PrimeTween**: zero-alloc callbacks, `Tween.StopAll` cleanup, no coroutines
- **UniTask**: CancellationToken propagation, no fire-and-forget
- **VContainer**: `Construct()` + `[Inject]`, not service-locator
- **UniRx**: `CompositeDisposable` + `.AddTo()`
- **Mobile**: no per-frame GC allocations
- **Naming**: PascalCase public, _camelCase private, English comments
- **Access modifiers**: always explicit

Fix all Critical findings. Document Warning exceptions.

---

## Common Pitfalls

| # | Problem | Fix |
|---|---|---|
| 1 | Effect GO uses `SetActive(false)` -- tweens don't play | Use `CanvasGroup.alpha = 0` to hide. Keep GO always active |
| 2 | Button clicks don't fire | Add EventSystem + correct InputModule |
| 3 | `StandaloneInputModule` throws with new Input System | Use `InputSystemUIInputModule` instead |
| 4 | Blocked elements still appear clickable | Set `Button.interactable = false` for covered elements |
| 5 | Inspector refs lost after script-execute | Call `EditorUtility.SetDirty()` then `scene-save` |
| 6 | PrimeTween capacity exceeded (many simultaneous tweens) | Call `PrimeTween.SetTweensCapacity(256)` in bootstrap |
| 7 | Tween on destroyed object | `Tween.StopAll(onTarget: this)` in `OnDestroy()` |

---

## Input Validation & Recovery

| Problem | Action |
|---|---|
| Schema version != 6.1.0 or 6.0.0 | Stop. Ask user to re-analyze with `unity-animation-analyzer` |
| `target.path` doesn't match scene | Use `gameobject-find` with partial name. Create GO if not found |
| No `animation_sequences` | Generate flat sequence from `animated_objects` triggers |
| MCP tools unavailable | Generate scripts only. Document manual wiring steps |
| Empty `animated_objects[]` | Stop. Nothing to build. Suggest re-running analyzer |

---

## Execution Checklist

- [ ] Validate schema version (6.1.0 or 6.0.0)
- [ ] Resolve `{FeatureName}` from scene/JSON/user
- [ ] Classify animated_objects by object_category
- [ ] Resolve unvalidated target paths via MCP
- [ ] Write C# scripts: PrimeTween + UniTask, VContainer DI
- [ ] Scripts at `Assets/Game/Scripts/Features/{FeatureName}/Animation/`
- [ ] Namespace: `Game.Features.{FeatureName}.Animation`
- [ ] Compile check -- zero errors
- [ ] Create supporting GameObjects (overlay, effects, text)
- [ ] Wire scripts to GameObjects with inspector refs
- [ ] Verify EventSystem present
- [ ] `scene-save`
- [ ] **Play Mode test** -- zero runtime errors
- [ ] Code review via `unity-code-review`
- [ ] All Critical findings resolved

---

## Output

- PrimeTween + UniTask C# scripts under `Assets/Game/Scripts/Features/{FeatureName}/Animation/`
- Scene GameObjects wired with scripts and correct references
- Scene saved with EventSystem, supporting GOs, and all wiring complete
- Zero compile and zero runtime errors confirmed

---

## References

| File | Content | When to read |
|---|---|---|
| `references/code-templates.md` | C# templates: controller, element animator, effect, text, patterns | When writing scripts |
| `references/mcp-workflow.md` | MCP tool workflows for AnimationClips, Animators, scene wiring | When creating Animator controllers or wiring scene |

---

## Related Skills

| Need | Skill                |
|---|----------------------|
| PrimeTween API, Sequences, Animator workflow | `unity-ui-animation` |
| Create/modify AnimationClips and Animators via MCP | `develop-unity-ui`   |
| uGUI 2.0 hierarchy, Canvas, RectTransform | `unity-ui`           |
| Reactive data binding, UniRx | `unity-ui-reactive`  |
| UI particle effects | `unity-ui-particle`  |
| Code quality review | `unity-code-review`  |
| Extract animation data from video | `detec-anim` |

---

## Project Conventions

- **Animation**: PrimeTween v1.3.7 -- no coroutines, no DOTween
- **Async**: `async UniTask` + `await seq.ToUniTask()` -- no `System.Threading.Tasks`
- **DI**: VContainer -- `Construct()` + `[Inject]`, not `Awake()` for injection
- **Cleanup**: `CompositeDisposable` + `.AddTo()` for UniRx; `Tween.StopAll(onTarget: this)` in `OnDestroy()`
- **Namespaces**: `Game.Features.{FeatureName}.Animation`
- **Naming**: PascalCase public, _camelCase private, ALL_CAPS constants
- **Comments**: English only
- **Access modifiers**: always explicit
- **Reactive state**: `ReactiveProperty<T>`, never plain fields
- **Editor-only**: `#if UNITY_EDITOR`
- **Canvas**: 1080x1920, ScaleWithScreenSize, Match 0.5
