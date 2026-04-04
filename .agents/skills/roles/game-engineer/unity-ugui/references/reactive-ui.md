# Reactive UI Patterns

Logic-to-View binding patterns for a clean, decoupled UI architecture.

## Architecture: MVC/MVP (MainView/ViewModel) Pattern

The project uses a structured Model-View-ViewModel approach for UI:

1.  **View (`MainView<TModel>`)**: The Unity component that manages UI elements and animations.
2.  **ViewModel (`ViewModel`)**: A class (usually nested) holding reactive state and events.
3.  **Logic (Pure C#)**: Game rules that drive the ViewModel.

### Example Implementation

```csharp
using Sun.Core.UI;
using UniRx;

namespace Game.Gameplay.UI
{
    public class MyUI : MainView<MyUI.UIModel>
    {
        public class UIModel : ViewModel
        {
            public ReactiveProperty<int> Score { get; } = new(0);
            public ISubject<Unit> OnComplete { get; } = new Subject<Unit>();
        }

        [SerializeField] private TMP_Text _scoreText;

        protected override void OnSetModel(UIModel viewModel)
        {
            // Bind Model to View
            viewModel.Score
                .Subscribe(s => _scoreText.SetText("Score: {0}", s))
                .AddTo(compositeDisposable);
        }
    }
}
```

## State Binding with UniRx

Use `ReactiveProperty<T>` for state and `Subscribe` in the View's `Inject` or `Start` method.

```csharp
public class MyView : MonoBehaviour
{
    private MyLogic mLogic;

    [Inject]
    public void Construct(MyLogic logic)
    {
        mLogic = logic;
        
        // Link logic state to UI
        mLogic.CurrentHP
            .Subscribe(hp => mHpSlider.value = hp)
            .AddTo(this);
    }
}
```

## Input Handling

Transform UI events into Logic actions using `AsObservable()`.

```csharp
mStartButton.OnClickAsObservable()
    .ThrottleFirst(TimeSpan.FromSeconds(0.5f)) // Prevent double-clicks
    .Subscribe(_ => mLogic.StartGame())
    .AddTo(this);
```

## Async Sequences with UniTask

Use `UniTask` for multi-step UI sequences (animations -> data loading -> transitions).

```csharp
public async UniTask ShowSequenceAsync()
{
    await mAnimationBehaviour.PlayInAsync();
    await UniTask.Delay(500); // Small pause
    mConfirmButton.interactable = true;
}
```

## Dependency Injection (VContainer)

Register UI Views in the relevant `LifetimeScope`.

```csharp
public class GameplayScope : LifetimeScope
{
    protected override void Configure(IContainerBuilder builder)
    {
        builder.RegisterComponentInHierarchy<MyView>();
        builder.Register<MyLogic>(Lifetime.Scoped);
    }
}
```

## Code Integrity Rules

- [ ] **MANDATORY REVIEW**: Any script with `[Inject]` or `UniRx` subscriptions must pass `unity-code-review`.
- [ ] **CLEANUP**: Always use `.AddTo(this)` or `Dispose()` subscriptions to prevent memory leaks.
