# UniRx & Reactive Programming

State management and event-driven architecture using UniRx.

## Core Concepts

1. **State**: Use `ReactiveProperty<T>` for mutable state that UI/Views listen to.
2. **Events**: Use `Subject<T>` for transient events (e.g. "Snake Escaped").
3. **Lifecycle**: Use `CompositeDisposable` to track and clean up subscriptions.
4. **Binding**: Use `.Subscribe()` with `.AddTo(disposable)` or `.AddTo(this)` for MonoBehaviours.

## Typical Pattern

```csharp
public class GameplayModel : IDisposable
{
    // State
    public ReactiveProperty<int> Score { get; } = new(0);
    public ReactiveProperty<int> Lives { get; } = new(3);

    // Events
    public Subject<Vector2Int> OnCollision { get; } = new();

    private CompositeDisposable mDisposables = new();

    public void HandleInput()
    {
        // Emit event
        OnCollision.OnNext(Vector2Int.zero);
        
        // Update state
        Score.Value += 10;
    }

    public void Dispose() => mDisposables.Dispose();
}
```

## Subscription Pattern

```csharp
private void Start()
{
    mModel.Score
        .Subscribe(score => mScoreText.text = score.ToString())
        .AddTo(this);

    mModel.OnCollision
        .Subscribe(pos => PlayCollisionEffect(pos))
        .AddTo(this);
}
```

## Key Rules

- **MANDATORY**: Always add `.AddTo(disposable)` to prevent leaks.
- **MANDATORY**: MonoBehaviours should unsubscribe in `OnDisable` or use `AddTo(this)` which cleans up in `OnDestroy`.
- **PREFER**: `IReadOnlyReactiveProperty<T>` for public exposure.
