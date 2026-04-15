---
name: unity-dev-principles
description: Professional Unity C# coding practices. Masters UniTask, UniRx, VContainer, and Pure C# game logic. Use for all coding tasks, refactoring, bug fixing, and architecture design. Enforces project-specific rules like "mandatory code review"."
tags: []
trust_level: experimental
---

# Unity Coding - Snake Escape Project

Professional Unity C# standards for high-performance, reactive, and modular mobile games.

## Core Technology Stack

1. **Async**: [UniTask](references/async-unitask.md) (Mandatory, allocation-free).
2. **Reactive**: [UniRx](references/reactive-unirx.md) (State and events).
3. **DI**: [VContainer](references/di-vcontainer.md) (Dependency injection).
4. **Logic**: [Pure C#](references/architecture.md) (Separation from MonoBehaviour).
5. **Memory**: [Collection Pooling](references/collections-pooling.md) (UnityEngine.Pool).
6. **Testing**: [Unity Test Runner](references/testing.md) (NUnit + CLI).
7. **Editor**: [Unity Editor Orchestrator](../develop-unity-ui/SKILL.md) (Scene/Prefab manipulation).

## Mandatory Project Rules

> [!IMPORTANT]
> **ENGLISH ONLY**: All code comments and documentation must be in English.
> **CODE REVIEW**: Any change to `Assets/Game/Scripts/` must be reviewed using the `unity-code-review` subagent.

---

## Getting Started

Follow these patterns for any new implementation:

### 1. Pure C# Logic First
Keep game rules in plain C# classes. Use `ReactiveProperty<T>` for state and `Subject<T>` for events.

```csharp
public class MyGameLogic : IDisposable
{
    public ReactiveProperty<int> Score { get; } = new(0);
    public Subject<Unit> OnWin { get; } = new();

    public void ProcessAction() 
    {
        Score.Value += 10;
        if (Score.Value >= 100) OnWin.OnNext(Unit.Default);
    }

    public void Dispose() { /* Cleanup */ }
}
```

### 2. Service Registration (VContainer)
Register your logic and services in `GlobalScope` (singletons) or `GameplayScope` (per-gameplay).

```csharp
builder.Register<MyGameLogic>(Lifetime.Scoped).AsSelf();
```

### 3. Consumption via Injection
Use `[Inject]` on Construct methods or fields.

```csharp
public class MyView : MonoBehaviour
{
    private MyGameLogic mLogic;

    [Inject]
    public void Construct(MyGameLogic logic)
    {
        mLogic = logic;
        mLogic.Score.Subscribe(UpdateScoreUI).AddTo(this);
    }
}
```

## References

- [Async & UniTask](references/async-unitask.md) - High-performance async.
- [Reactive & UniRx](references/reactive-unirx.md) - State and events.
- [Dependency Injection](references/di-vcontainer.md) - VContainer patterns.
- [Architecture & Logic](references/architecture.md) - Logic/View separation.
- [Collections & Pooling](references/collections-pooling.md) - GC-free patterns.
- [Automated Testing](references/testing.md) - Test Runner and NUnit.
- [Performance Optimization](references/performance.md) - Mobile optimization.

## Integration with Global Rules

Always ensure:
- [ ] Comments are English only.
- [ ] `unity-code-review` is triggered for C# changes.
- [ ] `unit-code-review` project is activated via `activate_project`.
- [ ] **Unity Editor**: All scene, prefab, and component modifications MUST use the `develop-unity-ui` skill tools. NEVER modify `.unity` or `.prefab` files as text or via shell scripts.
