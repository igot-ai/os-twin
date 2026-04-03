# Code Templates for Animation Builder

PrimeTween + UniTask C# templates for common animation categories.
All templates follow project conventions: `Game.Features.{FeatureName}.Animation` namespace, VContainer DI, UniRx cleanup.

---

## Animation Controller (Root Orchestrator)

Attach to the root canvas or popup GO. Orchestrates the full animation sequence.

```csharp
using System.Threading;
using Cysharp.Threading.Tasks;
using PrimeTween;
using UnityEngine;
using VContainer;

namespace Game.Features.{FeatureName}.Animation
{
    public sealed class {Root}AnimationController : MonoBehaviour
    {
        [SerializeField] private CanvasGroup _overlayCanvasGroup;
        [SerializeField] private TweenSettings<float> _overlayFadeSettings;

        private CancellationTokenSource _cts;

        [Inject]
        public void Construct(/* injected dependencies */)
        {
            // Store injected services
        }

        private void OnEnable()
        {
            _cts = new CancellationTokenSource();
        }

        private void OnDisable()
        {
            _cts?.Cancel();
            _cts?.Dispose();
            _cts = null;
        }

        private void OnDestroy()
        {
            Tween.StopAll(onTarget: this);
        }

        /// <summary>
        /// Execute the full animation sequence.
        /// Maps to animation_sequences[].steps[] ordering from the detection JSON.
        /// </summary>
        public async UniTask PlaySequenceAsync(CancellationToken ct = default)
        {
            using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(ct, _cts.Token);
            var token = linkedCts.Token;

            // Step 1: Element tap feedback (sequential)
            await PlayTapFeedbackAsync(token);

            // Step 2: Parallel animations (e.g., heart fills with stagger)
            await UniTask.WhenAll(
                PlayFillAnimation(0, token),
                PlayFillAnimation(1, token),
                PlayFillAnimation(2, token)
            );

            // Step 3: Overlay fade out (sequential)
            await Tween.Alpha(_overlayCanvasGroup, _overlayFadeSettings)
                .ToUniTask(cancellationToken: token);
        }

        private async UniTask PlayTapFeedbackAsync(CancellationToken ct)
        {
            await Tween.PunchScale(transform,
                    strength: new Vector3(0.05f, 0.05f, 0f),
                    duration: 0.3f, frequency: 10)
                .ToUniTask(cancellationToken: ct);
        }

        private async UniTask PlayFillAnimation(int index, CancellationToken ct)
        {
            // Stagger start by index
            if (index > 0)
                await UniTask.Delay((int)(index * 150), cancellationToken: ct);

            // Implement per-element fill animation
            await UniTask.CompletedTask;
        }
    }
}
```

---

## Element Animator

Attach to each animated element (tile, card, heart, etc.). Handles per-element PrimeTween animations.

```csharp
using PrimeTween;
using UnityEngine;

namespace Game.Features.{FeatureName}.Animation
{
    [RequireComponent(typeof(CanvasGroup))]
    public sealed class {Element}Animator : MonoBehaviour
    {
        [SerializeField] private TweenSettings<float> _scalePopSettings;
        [SerializeField] private TweenSettings<float> _fadeSettings;

        private CanvasGroup _canvasGroup;
        private Transform _transform;

        private void Awake()
        {
            _canvasGroup = GetComponent<CanvasGroup>();
            _transform = transform;
        }

        /// <summary>
        /// Play a pickup animation: scale pop + fly to target + fade out.
        /// </summary>
        public Sequence PlayPickupAnimation(Vector2 targetPosition)
        {
            return Sequence.Create()
                .Chain(Tween.Scale(_transform, 1.2f, 0.1f, ease: Ease.OutBack))
                .Chain(Tween.UIAnchoredPosition(
                    (RectTransform)_transform,
                    ((RectTransform)_transform).anchoredPosition,
                    targetPosition,
                    0.4f, ease: Ease.InOutQuad))
                .Group(Tween.Alpha(_canvasGroup, 0f, 0.3f, ease: Ease.InQuad));
        }

        /// <summary>
        /// Play a simple scale pop (tap feedback, fill feedback).
        /// </summary>
        public Tween PlayScalePop(float strength = 0.15f, float duration = 0.3f)
        {
            return Tween.PunchScale(_transform,
                strength: new Vector3(strength, strength, 0f),
                duration: duration, frequency: 10);
        }

        /// <summary>
        /// Fade in or out using CanvasGroup alpha.
        /// </summary>
        public Tween PlayFade(bool visible, float duration = 0.3f)
        {
            return Tween.Alpha(_canvasGroup, visible ? 1f : 0f, duration, ease: Ease.OutQuad);
        }

        private void OnDestroy()
        {
            Tween.StopAll(onTarget: this);
        }
    }
}
```

---

## Effect Component

For visual feedback that appears briefly (sparkle, burst, text pop).

```csharp
using PrimeTween;
using UnityEngine;

namespace Game.Features.{FeatureName}.Animation
{
    [RequireComponent(typeof(CanvasGroup))]
    public sealed class {Effect}Effect : MonoBehaviour
    {
        [SerializeField] private TweenSettings<float> _fadeInSettings;
        [SerializeField] private TweenSettings<float> _scaleSettings;

        private CanvasGroup _canvasGroup;

        private void Awake()
        {
            _canvasGroup = GetComponent<CanvasGroup>();
            // Start hidden
            _canvasGroup.alpha = 0f;
            _canvasGroup.blocksRaycasts = false;
        }

        /// <summary>
        /// Show the effect with a scale-in + fade-in, then auto-hide after duration.
        /// </summary>
        public Sequence Play()
        {
            return Sequence.Create()
                // Show: fade in + scale up simultaneously
                .Group(Tween.Alpha(_canvasGroup, 1f, 0.15f, ease: Ease.OutQuad))
                .Group(Tween.Scale(transform, new Vector3(0.5f, 0.5f, 1f), Vector3.one,
                    0.2f, ease: Ease.OutBack))
                // Hold
                .ChainDelay(0.5f)
                // Hide: fade out
                .Chain(Tween.Alpha(_canvasGroup, 0f, 0.3f, ease: Ease.InQuad));
        }

        private void OnDestroy()
        {
            Tween.StopAll(onTarget: this);
        }
    }
}
```

---

## Text Feedback Animator

For floating text that pops in with a scale punch then fades out ("Awesome!", "+3", score).

```csharp
using PrimeTween;
using UnityEngine;
using TMPro;

namespace Game.Features.{FeatureName}.Animation
{
    [RequireComponent(typeof(CanvasGroup))]
    public sealed class {Feedback}TextAnimator : MonoBehaviour
    {
        [SerializeField] private TMP_Text _text;
        [SerializeField] private TweenSettings<float> _fadeSettings;

        private CanvasGroup _canvasGroup;

        private void Awake()
        {
            _canvasGroup = GetComponent<CanvasGroup>();
            _canvasGroup.alpha = 0f;
        }

        /// <summary>
        /// Show text with pop-in animation, hold, then fade out.
        /// </summary>
        public Sequence Play(string message)
        {
            _text.SetText(message);
            transform.localScale = Vector3.zero;

            return Sequence.Create()
                // Pop in: scale from 0 to 1 with overshoot
                .Group(Tween.Scale(transform, Vector3.one, 0.25f, ease: Ease.OutBack))
                .Group(Tween.Alpha(_canvasGroup, 1f, 0.15f))
                // Hold
                .ChainDelay(0.8f)
                // Fade out + float up
                .Group(Tween.Alpha(_canvasGroup, 0f, 0.3f, ease: Ease.InQuad))
                .Group(Tween.UIAnchoredPositionY(
                    (RectTransform)transform,
                    ((RectTransform)transform).anchoredPosition.y + 50f,
                    0.3f, ease: Ease.InQuad));
        }

        private void OnDestroy()
        {
            Tween.StopAll(onTarget: this);
        }
    }
}
```

---

## Designer-Tweakable Settings Pattern

Use `TweenSettings<T>` for any animation timing that should be inspector-editable:

```csharp
[SerializeField] private TweenSettings<float> _fadeSettings;
[SerializeField] private TweenSettings<float> _scaleSettings;

public void SetVisible(bool isVisible)
{
    Tween.Alpha(_canvasGroup, _fadeSettings.WithDirection(toEndValue: isVisible));
    Tween.Scale(transform, _scaleSettings.WithDirection(toEndValue: isVisible));
}
```

---

## Zero-Allocation Callback Pattern

```csharp
// GOOD: static delegate + explicit target (zero alloc)
Tween.Alpha(canvasGroup, 0f, 0.3f)
    .OnComplete(target: this, static (target) => target.OnFadeComplete());

// BAD: closure captures 'this' -> allocation every call
Tween.Alpha(canvasGroup, 0f, 0.3f)
    .OnComplete(() => OnFadeComplete());
```

---

## Sequence Composition Patterns

### Sequential: one after another

```csharp
Sequence.Create()
    .Chain(Tween.Scale(transform, 1.2f, 0.2f, ease: Ease.OutBack))
    .ChainDelay(0.5f)
    .Chain(Tween.Alpha(canvasGroup, 0f, 0.3f));
```

### Parallel: multiple at same time

```csharp
Sequence.Create()
    .Group(Tween.Alpha(canvasGroup, 1f, 0.3f))
    .Group(Tween.UIAnchoredPositionY(rect, 0f, 0.3f, ease: Ease.OutQuad));
```

### Mixed: sequential steps with parallel sub-animations

```csharp
Sequence.Create()
    // Step 1: fade in + slide up (parallel)
    .Group(Tween.Alpha(canvasGroup, 1f, 0.3f))
    .Group(Tween.UIAnchoredPositionY(rect, 0f, 0.3f, ease: Ease.OutQuad))
    // Step 2: wait
    .ChainDelay(0.5f)
    // Step 3: scale pop (sequential after delay)
    .Chain(Tween.PunchScale(transform, new Vector3(0.1f, 0.1f, 0f), 0.3f));
```

### Async orchestration with UniTask

```csharp
public async UniTask PlayFullSequenceAsync(CancellationToken ct)
{
    // Sequential step: await the sequence
    var seq = Sequence.Create()
        .Chain(Tween.Scale(transform, 1.2f, 0.2f, ease: Ease.OutBack))
        .Chain(Tween.Alpha(canvasGroup, 0f, 0.3f));
    await seq.ToUniTask(cancellationToken: ct);

    // Parallel step: multiple UniTasks
    await UniTask.WhenAll(
        PlayElement(0, ct),
        PlayElement(1, ct),
        PlayElement(2, ct)
    );
}
```
