---
name: unity-ugui
description: "
tags: []
trust_level: experimental
---

---
name: unity-ugui
description: Professional Unity UI (uGUI) assistant. Masters responsive layouts, TextMeshPro, reactive UI patterns (UniRx/UniTask), UI animation via Animator + PrimeTween, TextMeshPro (merged), and the Event System. Use for building screens, HUDs, popups, or optimizing UI performance. Always uses `unity-editor` sub-skills for for all Editor operations and `unity-code-review` for script changes.
---

# Unity uGUI 2.0 Skill

> [!IMPORTANT]
> **NO UI Toolkit / UI Builder.** This project uses **uGUI (com.unity.ugui@2.0)** exclusively.
> All UI is built as **Prefabs** using GameObjects, Components, and the Scene View.
> Use `unity-editor` sub-skills for **all** Editor hierarchy and asset operations.

---

## 1. Core Concepts (com.unity.ugui@2.0)

### 1.1 Canvas

The `Canvas` component is the root of all UI. Every UI element must be a child of a Canvas.

| Render Mode | Use Case |
|---|---|
| **Screen Space - Overlay** | Default HUD / menus. Renders on top of everything. |
| **Screen Space - Camera** | UI rendered by a specific camera (supports perspective distortion). |
| **World Space** | Diegetic UI (health bars above characters, in-world panels). |

**Draw Order**: Sibling order in Hierarchy = draw order. Later children render on top.

### 1.2 Rect Transform

All UI elements use `RectTransform` instead of `Transform`. Key properties:

- **Anchors** (`anchorMin`, `anchorMax`): Define how the element stretches/positions relative to the parent. Use **Anchor Presets** for common layouts (center, stretch, corners).
- **Pivot**: Center of rotation/scaling. Set before applying Layout Groups.
- **sizeDelta**: Width/Height when anchors are NOT stretched.
- **offsetMin / offsetMax**: Distance from lower-left / upper-right anchors when stretched.
- **Resizing vs Scaling**: Always resize via width/height (not localScale) to preserve font sizes and 9-slice borders.

### 1.3 Visual Components

| Component | Purpose | Key Notes |
|---|---|---|
| **Image** | Display sprites | Supports Simple, Sliced (9-slice), Tiled, Filled modes. Use `Set Native Size` for pixel-perfect. |
| **Raw Image** | Display raw textures | Use only when no sprite border needed (e.g., render textures, video). |
| **TextMeshProUGUI** | Rich text rendering | **Merged into ugui@2.0**. Always use `TMP_Text` field type. Use `SetText()` not `.text` for numbers. |
| **Mask** | Clip children to parent shape | Restricts child rendering to parent bounds. |
| **RectMask2D** | Efficient rectangular clipping | Faster than Mask for scroll views. No stencil buffer cost. |
| **Effects** | Shadow, Outline | Apply via `Shadow` or `Outline` components. |

### 1.4 Interaction Components

All interaction components inherit from `Selectable` and share:
- **Transition modes**: None, Color Tint, Sprite Swap, **Animation** (most powerful).
- **Navigation**: Automatic, Horizontal, Vertical, Explicit, None.
- **UnityEvent callbacks** for user interactions.

| Component | Event | Notes |
|---|---|---|
| **Button** | `OnClick` | Throttle with UniRx `ThrottleFirst` to prevent double-tap. |
| **Toggle** | `OnValueChanged(bool)` | Use `ToggleGroup` for radio-button behavior. |
| **Slider** | `OnValueChanged(float)` | Horizontal or Vertical. Range: min-max. |
| **Scrollbar** | `OnValueChanged(float)` | Often paired with `ScrollRect`. |
| **Dropdown** (TMP) | `OnValueChanged(int)` | Supports text + optional image per option. |
| **InputField** (TMP) | `OnValueChanged(string)`, `OnEndEdit(string)` | Content type validation built-in. |
| **ScrollRect** | `OnValueChanged(Vector2)` | Pair with `Mask`/`RectMask2D` + content `RectTransform`. |

### 1.5 Auto Layout System

Use when elements need dynamic sizing/positioning:

| Component | Controls | Notes |
|---|---|---|
| **Layout Element** | Own min/preferred/flexible size | Override auto-calculated sizes. |
| **Content Size Fitter** | Own size based on content | `Horizontal Fit` / `Vertical Fit`: Unconstrained, Min, Preferred. |
| **Aspect Ratio Fitter** | Own aspect ratio | Modes: Width Controls Height, Height Controls Width, Fit In Parent, Envelope Parent. |
| **Horizontal Layout Group** | Child positions (horizontal) | Controls spacing, padding, child alignment, child force expand. |
| **Vertical Layout Group** | Child positions (vertical) | Same controls as Horizontal. |
| **Grid Layout Group** | Child positions (grid) | Cell size, spacing, start corner/axis, constraint. |

> [!WARNING]
> **Driven Properties**: Layout controllers lock affected RectTransform properties (read-only in Inspector). Do not fight this -- set anchors/pivots BEFORE adding Layout Groups.
> **Nesting**: Avoid nesting multiple `ContentSizeFitter` -- causes layout "jitter" and performance spikes.

### 1.6 Event System

Required in every scene with UI. Automatically created with the first Canvas.

- **EventSystem**: Manager for input routing and selection tracking.
- **Input Module** (e.g., `StandaloneInputModule`): Handles keyboard/mouse/touch input.
- **Graphic Raycaster**: On Canvas -- determines which UI element is under the pointer. Disable `Raycast Target` on non-interactive elements for performance.

### 1.7 Rich Text (TextMeshPro)

TMP supports rich text tags: `<b>`, `<i>`, `<size=N>`, `<color=#HEX>`, `<sprite name=X>`.
See [TextMeshPro Best Practices](references/text-mesh-pro.md) for full details.

---

## 2. UI Animation

### 2.1 Selectable Transition Animation

For interaction component state transitions (Normal  Highlighted  Pressed  Disabled):

1. Set **Transition** to `Animation` on the `Selectable` component.
2. Click **Auto Generate Animation** -- creates Animator Controller + 4 state clips.
3. Customize clips in the Animation window (e.g., scale button width on Highlight).
4. The Animator handles blending between states automatically.

> [!IMPORTANT]
> UI Animation is **NOT compatible with Unity's legacy animation system**. Always use the **Animator** component.

### 2.2 Screen Transitions (Open/Close Pattern)

Use the Animator-based screen transition pattern from the official UGUI documentation:

**Setup per screen:**
1. Add **Animator** component to the screen root GameObject.
2. Create an **Animator Controller** with:
   - Bool parameter: `Open`
   - Two states: `Open` and `Closed` (each with a single-keyframe clip)
   - Transition: `Open  Closed` when `Open == false`
   - Transition: `Closed  Open` when `Open == true`
3. The screen's `CanvasGroup.alpha` and/or `RectTransform` position/scale should be animated in these clips.

**ScreenManager Pattern:**
- Track the currently open screen's `Animator`.
- `OpenPanel(Animator anim)`: Activate target, call `SetBool("Open", true)`, close current.
- `CloseCurrent()`: Call `SetBool("Open", false)`, coroutine waits for `Closed` state, then `SetActive(false)`.
- Buttons call `ScreenManager.OpenPanel(targetAnimator)`.

**unity-editor tool workflow for animation setup:**
```
1. animator-create      Create .controller asset
2. animator-modify      Add "Open" bool parameter, add Open/Closed states, add transitions with conditions
3. animation-create     Create Open.anim and Closed.anim clips
4. animation-modify     Set keyframes (e.g., CanvasGroup.alpha: 01 for Open, 10 for Closed)
5. gameobject-component-add  Attach Animator to screen root
6. gameobject-component-modify  Assign the controller to the Animator
```

### 2.3 Code-Based Animation (PrimeTween)

For simple animations (fade, slide, scale, shake), use **PrimeTween** -- a high-performance, zero-allocation tween library:

```csharp
using PrimeTween;

// Fade in
Tween.Alpha(canvasGroup, endValue: 1f, duration: 0.3f, ease: Ease.OutQuad);

// Slide panel into view
Tween.UIAnchoredPositionY(rectTransform, endValue: 0f, duration: 0.4f, ease: Ease.OutBack);

// Button punch feedback
Tween.PunchScale(transform, strength: new Vector3(0.1f, 0.1f, 0), duration: 0.3f, frequency: 10);

// Sequence: parallel fade + slide, then callback
Sequence.Create()
    .Group(Tween.Alpha(canvasGroup, 1f, 0.3f))
    .Group(Tween.UIAnchoredPositionY(rect, 0f, 0.3f, ease: Ease.OutQuad))
    .ChainCallback(() => canvasGroup.interactable = true);
```

> [!TIP]
> **When to use PrimeTween vs Animator**: Use PrimeTween for any animation describable in 1-3 lines of code (fade, slide, scale, shake). Use Animator for complex state machines, multi-layer blending, or designer-editable curve animation. See [UI Animation Guide](references/ui-animation.md) for the full decision matrix.

---

## 3. Multi-Resolution Design

### 3.1 Canvas Scaler Configuration

Always use **Scale With Screen Size** mode on root Canvas:

| Property | Value | Rationale |
|---|---|---|
| **UI Scale Mode** | `ScaleWithScreenSize` | Scales entire UI proportionally. |
| **Reference Resolution** | `1080  1920` (portrait) / `1920  1080` (landscape) | Design-time target resolution. |
| **Screen Match Mode** | `MatchWidthOrHeight` | Blends width/height comparison. |
| **Match** | `0.5` | Balances landscape and portrait scaling. |

### 3.2 Anchor Strategy

- **Corner-anchored elements**: Buttons near edges should anchor to their respective corner.
- **Center-anchored elements**: Popups/modals anchor to center with fixed size.
- **Stretch-anchored elements**: Full-width headers/footers stretch horizontally, anchor top/bottom.

---

## 4. Building UI Prefabs (Workflows)

> [!IMPORTANT]
> All UI is built as **Prefabs**. Never use UI Toolkit. Use `unity-editor` sub-skills for all hierarchy operations.

### 4.1 Creating a New UI Screen

```
Step 1: Plan hierarchy using the Standard Hierarchy pattern (see Section 5.1)
Step 2: gameobject-create         Create root "UI_{ScreenName}"
Step 3: gameobject-component-add  Add Canvas, CanvasScaler, GraphicRaycaster, CanvasGroup
Step 4: gameobject-component-modify  Configure CanvasScaler (Scale With Screen Size, 10801920, Match 0.5)
Step 5: gameobject-create         Create child "Background" with Image component
Step 6: gameobject-create         Create anchor containers (UpperAnchor, LowerAnchor, etc.)
Step 7: [Add interaction/visual components as children]
Step 8: [For animated screens] Set up Animator + Controller (see Section 2.2)
Step 9: assets-prefab-create      Save as Prefab to Assets/Game/Prefabs/UI/{ScreenName}/
Step 10: scene-save               Save the scene
```

### 4.2 Creating Dynamic UI Elements

For UI elements instantiated at runtime (inventory items, list entries):

1. **Create a template Prefab** with the desired layout and components.
2. **Instantiate via script** using `Instantiate()` with `Transform.SetParent(parent, worldPositionStays: false)`.
3. **Position**: If inside a Layout Group, positioning is automatic. Otherwise, set `anchoredPosition` and `sizeDelta`.
4. **Customize**: Get child components and modify text, images, callbacks.

### 4.3 Modifying an Existing UI Prefab

```
Step 1: assets-find               Find prefab by name
Step 2: assets-prefab-open        Open for editing
Step 3: gameobject-find           Navigate hierarchy
Step 4: [Perform modifications]   Add/remove/modify components
Step 5: assets-prefab-save        Save changes
Step 6: assets-prefab-close       Exit prefab mode
```

---

## 5. Project Architecture Integration

### 5.1 Standard Hierarchy (from unity-ui)

Every UI screen MUST follow:

```
UI_{ScreenName} (Root: RectTransform, Canvas, CanvasScaler, GraphicRaycaster, UIAnimationBehaviour)
   Background (Image, CanvasGroup)
        Anchors (Layout containers)
             LeftAnchor
             RightAnchor
             UpperAnchor
             LowerAnchor
             PopupAnchor (for centered content)
```

### 5.2 Vertical Slice Architecture

Organize scripts per feature:

```
Assets/Game/Scripts/{FeatureName}/
 Logic/          # Pure C# (no MonoBehaviour)
 Models/         # ViewModels with ReactiveProperty
 Views/          # MonoBehaviour views
 Data/           # ScriptableObjects
 UI/
     {Screen}UI.cs      # MainView<TModel>
     {Screen}Model.cs   # ViewModel
     {ChildView}.cs     # Sub-components
```

### 5.3 MVC/MVP Pattern

- **View**: Inherits `MainView<TModel>` -- manages UI elements.
- **ViewModel**: Contains `ReactiveProperty<T>` state.
- **Binding**: Done in `OnSetModel()` using `UniRx.Subscribe().AddTo(compositeDisposable)`.
- **Input**: Use `OnClickAsObservable().ThrottleFirst(0.5s)`.
- **DI**: Register views/logic in `VContainer` `LifetimeScope`.

See [Reactive UI Patterns](references/reactive-ui.md) for full examples.

### 5.4 Mandatory Components

| Component | When to Use |
|---|---|
| **UIAnimationBehaviour** | Any root or panel with transitions. |
| **LocalizeUIText** | Every `TMP_Text` / `TextMeshProUGUI` component. |
| **UIParticle** | Any `ParticleSystem` inside a Canvas. |

---

## 6. Performance Guidelines

1. **Canvas Splitting**: Separate static (borders, backgrounds) and dynamic (timers, scores) canvases.
2. **Raycast Target**: Disable on ALL non-interactive `Image`/`Text` components.
3. **Sprite Atlases**: Group sprites per screen into atlases. Keep Z=0 for batching.
4. **CanvasGroup for fading**: Use `CanvasGroup.alpha` -- NOT individual Image color changes.
5. **Layout Groups**: Use sparingly. Prefer `RectTransform` anchoring for static layouts.
6. **ContentSizeFitter nesting**: NEVER nest multiple -- causes jitter and performance spikes.
7. **TextMeshPro**: Use `SetText()` with format args, not string interpolation. Update only on value change.
8. **Disable Raycaster during transitions**: Set `GraphicRaycaster.enabled = false` while animating.

See [Performance Guide](references/performance.md) for details.

---

## 7. Project Constraints

> [!CAUTION]
> - **EDITOR TOOLS ONLY**: Use `unity-editor` sub-skills for prefab/scene modifications. Never edit `.prefab` files as text.
> - **MOBILE-FIRST**: All UI must be tested for notch compatibility (Safe Area) and thermal efficiency.
> - **MANDATORY CODE REVIEW**: Trigger `unity-code-review` for any new `MonoBehaviour` or logic scripts.
> - **NO UI TOOLKIT**: Do not use UI Builder, `.uxml`, or `.uss`. uGUI Prefabs only.

---

## References

- [uGUI Patterns & Structure](references/ugui-patterns.md) -- Standard hierarchy and layout rules.
- [TextMeshPro Best Practices](references/text-mesh-pro.md) -- High-performance text rendering.
- [Reactive UI (MVC/MVP)](references/reactive-ui.md) -- MainView/ViewModel, UniRx, UniTask.
- [Architecture](references/architecture.md) -- Vertical Slide Architecture guidelines.
- [Performance](references/performance.md) -- Mobile-specific UI optimization.
- [UGUI 2.0 Component Reference](references/ugui-components.md) -- Full component property reference.
- [UI Animation Guide](references/ui-animation.md) -- Animator vs PrimeTween decision guide, code-based tweening, and screen transitions.
- [Official Docs](https://docs.unity3d.com/Packages/com.unity.ugui@2.0/manual/index.html) -- Unity UGUI 2.0 Manual.

