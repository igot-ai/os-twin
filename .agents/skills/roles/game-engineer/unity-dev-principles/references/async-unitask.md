# UniTask & Async Best Practices

Mandatory asynchronous programming standard for the Snake Escape project.

## Core Rules

1. **MANDATORY**: Use `UniTask` or `UniTask<T>` instead of `Task`.
2. **THREADING**: Only access Unity APIs on the Main Thread. Use `UniTask.SwitchToMainThread()` when returning from ThreadPool work.
3. **CANCELLATION**: Always use `destroyCancellationToken` in MonoBehaviours.
4. **EXTENSIONS**: Use `.WithCancellation(ct)` when awaiting Unity `AsyncOperation` (e.g. `Addressables.LoadAssetAsync`).

## Typical Pattern

```csharp
private async UniTask LoadAssets(CancellationToken ct)
{
    // Await Addressables with cancellation
    var handle = Addressables.LoadAssetAsync<GameObject>("MyPrefab");
    var prefab = await handle.ToUniTask(cancellationToken: ct);
    
    // Allocation-free delay
    await UniTask.Delay(100, cancellationToken: ct);
    
    // Thread switching for heavy math
    await UniTask.SwitchToThreadPool();
    ProcessHeavyLogic();
    await UniTask.SwitchToMainThread();
}
```

## Anti-Patterns

- **WRONG**: Using `async Task` (allocates GC).
- **WRONG**: Using `async void` (breaks exception handling). Use `UniTaskVoid`.
- **WRONG**: Forgetting `destroyCancellationToken` (tasks leak on Destroy).
