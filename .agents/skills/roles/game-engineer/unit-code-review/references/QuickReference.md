# C# Refactoring Quick Reference

## Before/After Code Snippets

### 1. Property Definition

**Before:**
```csharp
private int score = 0;
public int GetScore() { return score; }
```

**After:**
```csharp
private int _score = 0;
public int Score => _score;
```

---

### 2. Async Operations

**Before:**
```csharp
private IEnumerator MoveCoroutine()
{
    yield return new WaitForSeconds(1f);
    OnMove?.Invoke();
}
```

**After:**
```csharp
public async UniTask MoveAsync()
{
    await UniTask.Delay(TimeSpan.FromSeconds(1f));
    GameReset.OnNext(Unit.Default);
}

// Usage
await MoveAsync().Forget();
```

---

### 3. Exception Handling

**Before:**
```csharp
try { score += amount; } catch { Debug.LogError("Error"); }
```

**After:**
```csharp
try { _score += amount; Score.Value = _score; }
catch (ArgumentOutOfRangeException ex) { Debug.LogError($"Invalid amount: {ex}"); }
```

---

### 4. Null Safety

**Before:**
```csharp
private Rigidbody rb;
rb = GetComponent<Rigidbody>();
```

**After:**
```csharp
[SerializeField] private Rigidbody _rb;
if (_rb == null) _rb = GetComponent<Rigidbody>();
```

---

### 5. Subscription Cleanup

**Before:**
```csharp
private void Update()
{
    if (Input.GetKeyDown(KeyCode.A)) AddScore(10);
}
```

**After:**
```csharp
private CompositeDisposable _disposable = new();

private async UniTask Start()
{
    this.UpdateAsObservable()
        .Where(_ => Input.GetKeyDown(KeyCode.A))
        .Subscribe(_ => AddScore(10))
        .AddTo(_disposable);
}

private void OnDestroy() => _disposable.Dispose();
```

---

### 6. Constructor Injection

**Before:**
```csharp
public void Initialize() { /* manual setup */ }
```

**After:**
```csharp
private readonly IStats _stats;

public PlayerController(IStats stats)
{
    _stats = stats;
    _maxHealth = stats.MaxHealth;
}
```

---

### 7. Constants

**Before:**
```csharp
if (health > 3) { achievements.Add("Survivor"); }
```

**After:**
```csharp
[SerializeField] private int _maxHealth = 3;
if (health > 0 && health <= _maxHealth)
```

---

### 8. Documentation

**Before:**
```csharp
public void ResetGame() { score = 0; }
```

**After:**
```csharp
/// <summary>Resets all game state and achievements.</summary>
public void ResetGame()
{
    _score = 0;
    achievements.Clear();
    GameReset.OnNext(Unit.Default);
}
```

---

## Common Patterns

### Reactive Pattern
```csharp
// Property for two-way binding
public readonly ReactiveProperty<float> TimeRemaining = new(30f);

// Event for one-way notifications
public readonly ISubject<Unit> GameFinished = new Subject<Unit>();

// Subscribe with cleanup
TimeRemaining.Subscribe(value => Debug.Log(value))
    .AddTo(compositeDisposable);
```

### Null Object Pattern
```csharp
private IPlayerStats _playerStats = null;

private void Awake()
{
    _playerStats ??= new PlayerStats();
}
```

### Strategy Pattern
```csharp
private readonly IPlayerStats _playerStats;

public PlayerController(IPlayerStats playerStats)
{
    _playerStats = playerStats ?? throw new ArgumentNullException(nameof(playerStats));
}
```

---

## Checklist for Refactoring

- [ ] Fields use `_camelCase` with underscore prefix
- [ ] Public properties use `PascalCase`
- [ ] Async code uses UniTask instead of coroutines
- [ ] Exception handling is specific, not generic
- [ ] Dependencies are injectable via constructor
- [ ] Events use UniRx (ReactiveProperty/ISubject)
- [ ] Subscriptions are properly disposed
- [ ] Magic numbers are extracted to constants
- [ ] Code is documented with XML comments
- [ ] Code follows Unity lifecycle patterns
- [ ] Null checks are defensive
- [ ] UI updates use reactive properties

---

## Performance Metrics

### Before (Bad)
- ❌ Coroutine overhead
- ❌ Manual event subscription
- ❌ Generic exception handling
- ❌ Runtime component lookups
- ❌ Memory leaks from unmanaged subscriptions

### After (Good)
- ✅ UniTask async/await efficiency
- ✅ Automatic subscription management
- ✅ Specific exception handling
- ✅ Cached component references
- ✅ Properly disposed subscriptions

---

## Learning Resources

- [UniRx Documentation](https://pokebyte.github.io/UniRx/)
- [UniTask Documentation](https://cyoshimat.hatenablog.com/entry/unisave/unisave)
- [VContainer Documentation](https://vcontainer.dev/)
- [C# Coding Conventions](https://docs.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions)
