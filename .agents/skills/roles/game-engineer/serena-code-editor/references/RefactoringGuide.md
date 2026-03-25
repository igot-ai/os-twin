# C# Code Refactoring Guide

This document details the improvements made in the refactoring example and provides guidelines for C# best practices.

## Overview

The refactoring transforms an anti-pattern code example into modern C# code following Unity and C# best practices.

## Key Improvements

### 1. Property vs Field Naming

**Bad:**
```csharp
private int score = 0;
public int GetScore() { return score; }
```

**Good:**
```csharp
private int _score = 0;  // Private fields use _prefix
public int Score => _score;  // Public properties with PascalCase
```

**Why:** Uses the C# convention for private fields and proper encapsulation.

### 2. Reactive Properties

**Bad:**
```csharp
public event Action OnMove;
private bool isMoving = false;

// Manual subscription
OnMove?.Invoke();
```

**Good:**
```csharp
private bool _isMoving = false;
public readonly ReactiveProperty<bool> IsMoving = new();

// Automatic UI binding
IsMoving.Subscribe(value => Debug.Log(value));
```

**Why:** UniRx's ReactiveProperty provides:
- Built-in change notifications
- Two-way binding support
- Automatic disposal
- Thread-safe operations

### 3. Async/Await Pattern

**Bad:**
```csharp
private IEnumerator MovePlayerCoroutine()
{
    yield return new WaitForSeconds(1f);
    isMoving = true;
    OnMove?.Invoke();
}

// Usage
StartCoroutine(MovePlayerCoroutine());
```

**Good:**
```csharp
public async UniTask MovePlayerAsync()
{
    await UniTask.Yield();
    await UniTask.Delay(TimeSpan.FromSeconds(1f), cancellationToken: this.GetCancellationTokenOnDestroy());
    _isMoving = true;
    await UniTask.Yield();
    GameReset.OnNext(Unit.Default);
}

// Usage
await MovePlayerAsync().Forget();
```

**Why:**
- UniTask is async/await compatible
- Better cancellation support
- No frame dependency
- More predictable timing

### 4. Exception Handling

**Bad:**
```csharp
try
{
    score += amount;
    if (score >= 100) {
        achievements.Add("First100Points");
        OnAchievementUnlocked?.Invoke("First100Points");
    }
}
catch (Exception)
{
    // Generic catch - no logging!
    Debug.LogError("Error adding score");
}
```

**Good:**
```csharp
try
{
    _score += amount;
    Score.Value = _score;

    if (_score >= 100) {
        UnlockAchievement("First100Points");
    }
}
catch (ArgumentOutOfRangeException ex)
{
    UnityEngine.Debug.LogError($"Invalid score amount: {ex.Message}");
    throw;  // Re-throw for caller to handle
}
catch (Exception ex)
{
    UnityEngine.Debug.LogError($"Unexpected error adding score: {ex}");
}
```

**Why:**
- Specific exception types
- Proper logging with context
- Re-throw for unexpected errors
- Don't silently fail

### 5. Constructor Injection

**Bad:**
```csharp
public void Initialize()
{
    // Does nothing but wastes space
}
```

**Good:**
```csharp
private readonly IPlayerStats _playerStats;

private PlayerController(IPlayerStats playerStats)
{
    _playerStats = playerStats;
    _maxHealth = playerStats.MaxHealth;
}
```

**Why:**
- VContainer's DI provides objects via constructor
- Makes dependencies explicit
- Easier to test
- Better for dependency lifecycle

### 6. IDisposable Management

**Bad:**
```csharp
private void OnDestroy()
{
    // Cleanup but not using CompositeDisposable pattern
}
```

**Good:**
```csharp
private CompositeDisposable _compositeDisposable = new();

private async UniTask Start()
{
    this.UpdateAsObservable()
        .Where(_ => Input.GetButtonDown("Jump"))
        .Subscribe(async _ => await MovePlayerAsync())
        .AddTo(_compositeDisposable);  // Automatic cleanup
}

private void OnDestroy()
{
    _compositeDisposable?.Dispose();  // Explicit cleanup
}
```

**Why:**
- CompositeDisposable ensures all subscriptions are disposed
- Prevents memory leaks from lingering subscriptions
- Follows Unity's lifecycle patterns

### 7. Null Safety

**Bad:**
```csharp
private Rigidbody rb;
private GameObject playerObject;

private void Awake()
{
    playerObject = GameObject.FindWithTag("Player");
    rb = playerObject.GetComponent<Rigidbody>();
}
```

**Good:**
```csharp
[SerializeField] private Rigidbody _rb;
[SerializeField] private Transform _playerTransform;

private void Awake()
{
    if (_rb == null) _rb = GetComponent<Rigidbody>();
    if (_playerTransform == null) _playerTransform = transform;

    // Cache references immediately
    _playerObject = gameObject;
}
```

**Why:**
- Unity Inspector allows assignment
- Defensive null checks
- Faster than runtime lookups
- Clearer dependencies

### 8. Constants and Configuration

**Bad:**
```csharp
public void HealPlayer(int healthAmount)
{
    if (healthAmount > 3)
    {
        achievements.Add("Survivor");
    }
}
```

**Good:**
```csharp
[SerializeField] private int _maxHealth = 3;
[SerializeField] private int _achievementThreshold = 100;

public void HealPlayer(int healthAmount)
{
    if (healthAmount > 0 && healthAmount <= _maxHealth)
    {
        _healthParticle?.Play();
        UnityEngine.Debug.Log($"Player healed with {healthAmount} HP");
    }
}
```

**Why:**
- Configurable values in Inspector
- Clear meaning through names
- Prevents magic numbers
- Can be tested

### 9. Documentation

**Bad:**
```csharp
public void ResetGame()
{
    score = 0;
    achievements.Clear();
    isMoving = false;
}
```

**Good:**
```csharp
/// <summary>
/// Resets all game state and achievements.
/// </summary>
/// <remarks>
/// Emits GameReset event for external subscribers.
/// </remarks>
public void ResetGame()
{
    _score = 0;
    _achievements.Clear();
    _isMoving = false;
    Score.Value = 0;
    GameReset.OnNext(Unit.Default);
}
```

**Why:**
- Self-documenting code
- Better IDE support
- Easier onboarding
- External API documentation

### 10. Try/Except Best Practices

**Bad:**
```csharp
public void UnlockAchievement(string achievementId)
{
    try
    {
        if (!achievements.Contains(achievementId))
        {
            achievements.Add(achievementId);
            OnAchievementUnlocked?.Invoke(achievementId);
        }
    }
    catch (Exception)
    {
        // Silently failing
    }
}
```

**Good:**
```csharp
public void UnlockAchievement(string achievementId)
{
    try
    {
        if (_achievements.Contains(achievementId))
        {
            UnityEngine.Debug.Log($"Achievement already unlocked: {achievementId}");
            return;
        }

        _achievements.Add(achievementId);
        AchievementUnlocked.OnNext(achievementId);
        UnityEngine.Debug.Log($"Achievement unlocked: {achievementId}");
    }
    catch (Exception ex)
    {
        UnityEngine.Debug.LogError($"Failed to unlock achievement: {ex}");
    }
}
```

**Why:**
- Early return for already-achieved cases
- Success logging
- Better error handling
- Don't fail silently

## Additional Recommendations

### Naming Conventions
- Private fields: `_camelCase` (with underscore prefix)
- Properties: `PascalCase`
- Public methods: `PascalCase`
- Events: `OnEventName` (Subject<T>) or `EventName` (ReactiveProperty<T>)

### Unity Best Practices
- Use `Construct()` or constructor injection instead of `Awake()` for DI
- Use `.Forget()` for fire-and-forget async operations
- Use `this.GetCancellationTokenOnDestroy()` for async operations
- Configure services in `GlobalScope.Configure()` before use

### Error Handling
- Catch specific exceptions, not `Exception`
- Log errors with context
- Re-throw unexpected exceptions
- Never silently fail

### Code Organization
- Pure game logic in classes without MonoBehaviour
- Use interfaces for dependencies
- Extract constants and configuration
- Document public APIs

## Testing Considerations

When refactoring for testing:
1. Make dependencies injectable
2. Use interfaces for external dependencies
3. Avoid static calls
4. Mock services via DI
5. Use async/await for predictable testing

## Performance Tips

1. Use UniTask instead of coroutines for async operations
2. Cache Unity component references in Awake()
3. Use ReactiveProperty for efficient UI updates
4. Dispose subscriptions properly to avoid leaks
5. Use `AsReadOnly()` on collections when appropriate
