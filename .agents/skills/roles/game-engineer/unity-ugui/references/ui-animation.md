# UI Animation Guide

Comprehensive guide to animating UI elements using Unity Animator, PrimeTween, and UniTask.

---

## When to Use What — Decision Guide

> [!IMPORTANT]
> Choose the right animation approach based on the use case. Do NOT mix approaches for the same element.

| Scenario | Recommended Tool | Rationale |
|---|---|---|
| **Selectable state transitions** (Button hover, press, disabled) | **Unity Animator** | Built into UGUI Selectable; auto-generates states. Designer-friendly. |
| **Screen open/close transitions** with complex multi-property animation | **Unity Animator** | State machine with blending. Reusable across screens. Designer-tweakable. |
| **Simple show/hide** (fade, slide, scale) | **PrimeTween** | One line of code. Zero allocation. No asset files needed. |
| **Data-driven animations** (score counters, health bars, progress) | **PrimeTween** | Animate numeric values directly. `Tween.Custom()` for anything. |
| **Juicy feedback** (button punch, shake, bounce) | **PrimeTween** | Built-in `Shake`, `Punch`. Easy to trigger from code events. |
| **Complex sequenced animations** (onboarding flows, tutorials) | **PrimeTween Sequence** | `Chain` / `Group` / `Insert` compose complex timelines in code. |
| **Looping ambient animations** (idle pulse, breathing, floating) | **PrimeTween** | `cycles: -1` with `CycleMode.Yoyo`. Lightweight, no Animator overhead. |
| **Animations needing designer iteration** (complex curves, precise timing) | **Unity Animator** | Animation window gives visual curve editing. Easier for non-programmers. |
| **Multi-step async sequences** (load → animate → transition) | **UniTask** with PrimeTween | `await Tween.X().ToUniTask()` or PrimeTween async/await. |

### Rules of Thumb

1. **Prefer PrimeTween** for any animation that can be described in 1–3 lines of code.
2. **Use Animator** when animations involve complex state machines, multiple layers, or need visual curve editing by designers.
3. **Never use legacy `Animation` component** — it's incompatible with UGUI transition system.
4. **Replace manual UniTask tween loops** (the `while (elapsed < duration)` pattern) with PrimeTween — it's allocation-free and handles edge cases (time scale, pause, cleanup).

---

## 1. PrimeTween (Code-Based Animation)

High-performance, allocation-free tween library. Create animations in one line of code.

### 1.1 Installation

PrimeTween is available via Unity Package Manager:
```
package-add → https://github.com/nicoplv/PrimeTween.git
```
Or import from [Asset Store](https://assetstore.unity.com/packages/slug/252960).

### 1.2 Core API — UI Animations

```csharp
using PrimeTween;

// === Fade ===
Tween.Alpha(canvasGroup, endValue: 1f, duration: 0.3f, ease: Ease.OutQuad);
Tween.Alpha(canvasGroup, endValue: 0f, duration: 0.3f);

// === Position (RectTransform) ===
Tween.UIAnchoredPosition(rectTransform, endValue: Vector2.zero, duration: 0.5f);
Tween.UIAnchoredPositionY(rectTransform, endValue: 0f, duration: 0.4f, ease: Ease.OutBack);

// === Scale ===
Tween.Scale(transform, endValue: 1f, duration: 0.3f, ease: Ease.OutBack);
Tween.Scale(transform, startValue: 0f, endValue: 1f, duration: 0.3f);

// === Rotation ===
Tween.Rotation(transform, endValue: Quaternion.identity, duration: 0.5f);
Tween.LocalEulerAngles(transform, startValue: Vector3.zero, endValue: new Vector3(0, 0, 360), duration: 1f);

// === Color (Image) ===
Tween.Color(image, endValue: Color.red, duration: 0.3f);

// === Custom (animate anything) ===
Tween.Custom(0f, 100f, duration: 1f, onValueChange: val => scoreText.SetText("{0}", (int)val));
```

### 1.3 Window Show/Hide Pattern

The most common UI animation — replaces manual coroutine/UniTask loops:

```csharp
using PrimeTween;
using UnityEngine;

public class UIPanel : MonoBehaviour
{
    [SerializeField] private RectTransform _panelRect;
    [SerializeField] private CanvasGroup _canvasGroup;
    [SerializeField] private TweenSettings<float> _fadeSettings;      // Tweak in Inspector
    [SerializeField] private TweenSettings<float> _slideSettings;     // Tweak in Inspector

    public void SetVisible(bool isVisible)
    {
        if (isVisible) gameObject.SetActive(true);

        // Fade alpha
        Tween.Alpha(_canvasGroup, _fadeSettings.WithDirection(toEndValue: isVisible));

        // Slide Y position
        Tween.UIAnchoredPositionY(_panelRect, _slideSettings.WithDirection(toEndValue: isVisible))
            .OnComplete(target: this, static (target) =>
            {
                if (target._canvasGroup.alpha <= 0f)
                    target.gameObject.SetActive(false);
            });

        _canvasGroup.interactable = isVisible;
        _canvasGroup.blocksRaycasts = isVisible;
    }
}
```

> [!TIP]
> Use `TweenSettings<T>` as serialized fields to let designers tweak start/end values, duration, and easing from the Inspector without code changes. Use `WithDirection(bool)` to toggle between open/close.

### 1.4 Juicy Feedback (Shake & Punch)

```csharp
// Button press punch effect
Tween.PunchScale(buttonTransform, strength: new Vector3(0.1f, 0.1f, 0), duration: 0.3f, frequency: 10);

// Camera shake on damage
Tween.ShakeLocalPosition(cameraTransform, strength: new Vector3(0.3f, 0.3f, 0), duration: 0.4f, frequency: 15);

// Shake a UI element
Tween.ShakeLocalPosition(uiRectTransform, strength: new Vector3(10f, 5f, 0), duration: 0.5f, frequency: 12);
```

### 1.5 Sequences

Compose complex multi-step animations:

```csharp
// Sequential: scale up → wait → fade out
Sequence.Create()
    .Chain(Tween.Scale(transform, endValue: 1.2f, duration: 0.2f, ease: Ease.OutBack))
    .ChainDelay(0.5f)
    .Chain(Tween.Alpha(canvasGroup, endValue: 0f, duration: 0.3f));

// Parallel: fade + slide simultaneously
Sequence.Create()
    .Group(Tween.Alpha(canvasGroup, endValue: 1f, duration: 0.3f))
    .Group(Tween.UIAnchoredPositionY(rectTransform, endValue: 0f, duration: 0.3f, ease: Ease.OutQuad));

// Complex: parallel intro → sequential items → callback
Sequence.Create()
    .Group(Tween.Alpha(canvasGroup, 1f, 0.3f))
    .Group(Tween.Scale(transform, 1f, 0.3f, ease: Ease.OutBack))
    .ChainDelay(0.1f)
    .Chain(Tween.UIAnchoredPositionX(item1, 0f, 0.2f))
    .Chain(Tween.UIAnchoredPositionX(item2, 0f, 0.2f))
    .Chain(Tween.UIAnchoredPositionX(item3, 0f, 0.2f))
    .ChainCallback(() => Debug.Log("All items revealed"));
```

### 1.6 Looping & Cycles

```csharp
// Infinite pulse (breathing effect)
Tween.Scale(transform, endValue: 1.05f, duration: 0.8f, cycles: -1, cycleMode: CycleMode.Yoyo);

// Bounce 3 times
Tween.UIAnchoredPositionY(rect, endValue: -20f, duration: 0.15f, cycles: 3, cycleMode: CycleMode.Yoyo);

// Stop a looping tween gracefully at endValue
tween.SetRemainingCycles(stopAtEndValue: true);
```

### 1.7 Controlling Tweens

```csharp
Tween tween = Tween.Scale(transform, 1.5f, 1f);

tween.Stop();               // Stop immediately at current value
tween.Complete();            // Jump to endValue instantly
tween.isPaused = true;       // Pause
tween.timeScale = 2f;        // Speed up
tween.progress = 0.5f;       // Jump to midpoint

Tween.StopAll(onTarget: transform);     // Stop all tweens on this target
Tween.CompleteAll(onTarget: transform);  // Complete all tweens on this target
```

### 1.8 Zero-Allocation Callbacks

```csharp
// GOOD: Zero allocation — pass target explicitly
Tween.Alpha(canvasGroup, 0f, 0.3f)
    .OnComplete(target: this, static (target) => target.OnFadeComplete());

Tween.Custom(this, 0f, 100f, 1f, static (target, val) => target._scoreText.SetText("{0}", (int)val));

// BAD: Allocates — captures 'this' in closure
Tween.Alpha(canvasGroup, 0f, 0.3f)
    .OnComplete(() => OnFadeComplete()); // delegate allocation!
```

### 1.9 Async/Await Integration

PrimeTween can be awaited natively (no UniTask dependency for simple cases):

```csharp
async void ShowScreenAsync()
{
    gameObject.SetActive(true);
    await Tween.Alpha(canvasGroup, 1f, 0.3f);
    await Tween.Scale(transform, 1f, 0.3f, ease: Ease.OutBack);
    // Screen is now fully visible
    canvasGroup.interactable = true;
}
```

> [!NOTE]
> While PrimeTween itself is allocation-free, C# `async/await` still allocates a small state machine. For **hot code paths** (called every frame or very frequently), prefer `Sequence` over `async/await`.

---

## 2. Unity Animator (State-Machine Animation)

### 2.1 Selectable Transition Animation

UGUI interaction components (Button, Toggle, Slider, etc.) support four transition modes. The **Animation** mode is the most powerful.

#### Setup Steps (via unity-editor tools)

```
1. gameobject-component-add    → Add Button (or other Selectable) to target
2. gameobject-component-modify → Set "transition" field to "Animation" (value: 3)
3. animator-create             → Create .controller at Assets/Game/Animations/UI/{Name}ButtonAnimator.controller
4. animation-create            → Create 4 clips: Normal.anim, Highlighted.anim, Pressed.anim, Disabled.anim
5. animator-modify             → Add states (Normal, Highlighted, Pressed, Disabled) and assign clips
6. gameobject-component-add    → Add Animator to the Button GameObject
7. gameobject-component-modify → Assign the controller to the Animator
```

#### Animation Clip Examples

**Highlighted.anim** — Scale button up:
```
animation-modify:
  - type: "setCurve"
    relativePath: ""
    propertyName: "m_LocalScale.x"
    typeName: "UnityEngine.Transform"
    keys: [{ time: 0, value: 1.1 }]
  - type: "setCurve"
    relativePath: ""
    propertyName: "m_LocalScale.y"
    typeName: "UnityEngine.Transform"
    keys: [{ time: 0, value: 1.1 }]
```

**Pressed.anim** — Scale button down:
```
keys: [{ time: 0, value: 0.95 }]
```

> [!NOTE]
> Transition blending between states is handled by the Animator automatically.
> Multiple buttons can share the same Animator Controller for consistent behavior.

### 2.2 Screen Transition Pattern (Open/Close)

The standard UGUI pattern for transitioning between UI screens using Animator.

#### Architecture

```
UI_Root (ScreenManager script)
  ├── UI_MainMenu (Animator, CanvasGroup) [Open/Closed states]
  ├── UI_Settings (Animator, CanvasGroup) [Open/Closed states]
  └── UI_Credits  (Animator, CanvasGroup) [Open/Closed states]
```

#### Animator Controller Setup

**Parameters:**
- `Open` (bool): Controls screen visibility

**States:**
- `Open`: Screen is visible (CanvasGroup.alpha = 1, RectTransform at final position)
- `Closed`: Screen is hidden (CanvasGroup.alpha = 0, optionally offset position)

**Transitions:**
- `Open → Closed`: Condition `Open == false`, no exit time
- `Closed → Open`: Condition `Open == true`, no exit time

#### unity-editor Tool Workflow

```
1. animator-create → Assets/Game/Animations/UI/Screens/{ScreenName}ScreenAnimator.controller

2. animator-modify → Add parameter "Open" (bool)
                   → Add state "Open" with motion Open.anim
                   → Add state "Closed" with motion Closed.anim  
                   → Set "Closed" as default state
                   → Add transition Open→Closed (condition: Open=false, hasExitTime=false)
                   → Add transition Closed→Open (condition: Open=true, hasExitTime=false)

3. animation-create → Open.anim, Closed.anim

4. animation-modify (Open.anim):
   - setCurve: CanvasGroup.m_Alpha → { time: 0, value: 1 }
   - setCurve: RectTransform.m_AnchoredPosition.y → { time: 0, value: 0 }

5. animation-modify (Closed.anim):
   - setCurve: CanvasGroup.m_Alpha → { time: 0, value: 0 }
   - setCurve: RectTransform.m_AnchoredPosition.y → { time: 0, value: -100 }

6. gameobject-component-add → Attach Animator + CanvasGroup to screen root
7. gameobject-component-modify → Assign controller to Animator
```

#### ScreenManager Script Pattern

```csharp
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System.Collections;

public class ScreenManager : MonoBehaviour
{
    [SerializeField] private Animator initiallyOpen;
    
    private Animator m_Open;
    private int m_OpenParameterId;
    private GameObject m_PreviouslySelected;
    
    const string k_OpenTransitionName = "Open";
    const string k_ClosedStateName = "Closed";

    private void OnEnable()
    {
        m_OpenParameterId = Animator.StringToHash(k_OpenTransitionName);
        if (initiallyOpen != null)
            OpenPanel(initiallyOpen);
    }

    public void OpenPanel(Animator anim)
    {
        if (m_Open == anim) return;
        
        anim.gameObject.SetActive(true);
        var newPreviouslySelected = EventSystem.current.currentSelectedGameObject;
        anim.transform.SetAsLastSibling();
        
        CloseCurrent();
        
        m_PreviouslySelected = newPreviouslySelected;
        m_Open = anim;
        m_Open.SetBool(m_OpenParameterId, true);
        
        var selectable = anim.GetComponentInChildren<Selectable>(true);
        if (selectable != null && selectable.IsActive() && selectable.IsInteractable())
            EventSystem.current.SetSelectedGameObject(selectable.gameObject);
    }

    public void CloseCurrent()
    {
        if (m_Open == null) return;
        
        m_Open.SetBool(m_OpenParameterId, false);
        EventSystem.current.SetSelectedGameObject(m_PreviouslySelected);
        StartCoroutine(DisablePanelDelayed(m_Open));
        m_Open = null;
    }

    private IEnumerator DisablePanelDelayed(Animator anim)
    {
        bool closedStateReached = false;
        bool wantToClose = true;
        while (!closedStateReached && wantToClose)
        {
            if (!anim.IsInTransition(0))
                closedStateReached = anim.GetCurrentAnimatorStateInfo(0).IsName(k_ClosedStateName);
            wantToClose = !anim.GetBool(m_OpenParameterId);
            yield return new WaitForEndOfFrame();
        }
        if (wantToClose)
            anim.gameObject.SetActive(false);
    }
}
```

---

## 3. UniTask (Async Multi-Step Orchestration)

Use UniTask to orchestrate high-level flows that mix PrimeTween, Animator, data loading, and logic:

```csharp
public async UniTask TransitionToGameplayAsync(CanvasGroup menuGroup, CanvasGroup gameplayGroup)
{
    // 1. Hide menu (PrimeTween)
    menuGroup.interactable = false;
    await Tween.Alpha(menuGroup, 0f, 0.3f);
    menuGroup.gameObject.SetActive(false);

    // 2. Load data
    await GameDataService.LoadLevelAsync();

    // 3. Show gameplay UI (PrimeTween)
    gameplayGroup.gameObject.SetActive(true);
    gameplayGroup.alpha = 0f;
    await Tween.Alpha(gameplayGroup, 1f, 0.3f);
    gameplayGroup.interactable = true;
}
```

> [!TIP]
> Use `CanvasGroup.interactable = false` and `blocksRaycasts = false` during transitions to prevent input during animation.

---

## 4. Performance Notes

| Approach | GC Alloc | CPU Cost | Asset Files |
|---|---|---|---|
| **PrimeTween** | Zero (with static delegates) | Very low | None |
| **PrimeTween async/await** | Small (C# state machine) | Very low | None |
| **Unity Animator** | Zero | Medium (state machine eval) | .controller + .anim |
| **UniTask manual loop** | Small (state machine) | Low | None |

**Recommendations:**
- For **hot paths** (per-frame): Use PrimeTween `Sequence` with static callbacks.
- For **one-off transitions**: PrimeTween async/await or Sequence.
- For **designer-editable** complex animations: Unity Animator.
- Call `PrimeTweenConfig.SetTweensCapacity(N)` at startup to pre-allocate (check max via PrimeTweenManager Inspector).
