# C# 9.0 and .NET Standard 2.1

Unity 6 supports C# 9.0 and targets .NET Standard 2.1. When you see older patterns,
flag them as `[C#9]` or `[NETSTANDARD]` Info items and show the modern equivalent.

---

## C# 9.0 Language Features

### Target-typed `new` expressions
When the type is already clear from context, `new()` is cleaner than repeating the type:

```csharp
// Before C# 9
private CompositeDisposable _disposables = new CompositeDisposable();
private List<int> _ids = new List<int>();

// C# 9
private CompositeDisposable _disposables = new();
private List<int> _ids = new();
```

### Init-only properties
Allows properties to be set at construction time but be read-only afterward. Great for immutable data objects and ScriptableObject-like configs:

```csharp
// Before
public class LevelData {
    public int Id { get; set; }         // mutable everywhere
    public string Name { get; set; }
}

// C# 9 — immutable after object initializer
public class LevelData {
    public int Id { get; init; }
    public string Name { get; init; }
}
var data = new LevelData { Id = 1, Name = "Level 1" }; // OK
data.Id = 2; // Compile error — good!
```

### Records
Records are immutable value-semantic reference types. Perfect for data transfer objects, event payloads, and model snapshots in Unity:

```csharp
// Before — verbose class with manual equality
public class TouchData {
    public Vector2 Position { get; }
    public float Time { get; }
    public TouchData(Vector2 pos, float time) { Position = pos; Time = time; }
    public override bool Equals(object obj) { ... } // tedious
}

// C# 9 record — concise, value equality built-in
public record TouchData(Vector2 Position, float Time);

// With expressions for mutation-style copying
var movedTouch = originalTouch with { Position = newPos };
```

Records work well for UniRx event payloads and immutable game state snapshots.

### Pattern matching improvements

**Relational patterns:**
```csharp
// Before
if (lives >= 1 && lives <= 3) { ... }

// C# 9
if (lives is >= 1 and <= 3) { ... }
```

**Logical patterns:**
```csharp
// Before
if (state == EGameState.Idle || state == EGameState.Playing) { ... }

// C# 9
if (state is EGameState.Idle or EGameState.Playing) { ... }
```

**Type patterns in switch:**
```csharp
// C# 9 switch expression
string Describe(IBoosterStrategy booster) => booster switch {
    HintBooster b => $"Hint for snake {b.TargetSnakeId}",
    RulerBooster   => "Show ruler overlay",
    null           => throw new ArgumentNullException(nameof(booster)),
    _              => "Unknown booster"
};
```

### Covariant return types
Overrides can return a more derived type than the base class declared:

```csharp
public abstract class BaseView {
    public abstract BaseModel GetModel();
}

// C# 9 — no cast needed
public class SnakeView : BaseView {
    public override SnakeModel GetModel() { ... } // more specific than BaseModel
}
```

### `static` anonymous functions
Lambdas that don't capture `this` or local variables can be marked `static` to prevent accidental captures:

```csharp
// Explicit that no capture happens — slightly cheaper allocation
_observable.Subscribe(static x => Debug.Log(x)).AddTo(_disposables);
```

---

## .NET Standard 2.1 APIs

### `Span<T>` and `Memory<T>` for buffer operations
Use for high-performance, allocation-free buffer operations (parsing level data, etc.):

```csharp
// Avoid creating intermediate arrays
ReadOnlySpan<char> line = rawText.AsSpan(start, length);
```

Not suitable for async methods or when you need to store across frames — use `Memory<T>` for those cases.

### Range and Index operators
```csharp
int[] arr = { 1, 2, 3, 4, 5 };

// Before
var last = arr[arr.Length - 1];
var slice = arr.Skip(1).Take(3).ToArray();

// .NET Standard 2.1
var last = arr[^1];
var slice = arr[1..4]; // indices 1, 2, 3
```

### `IAsyncEnumerable<T>` with `await foreach`
```csharp
// For streaming async data (e.g., loading level chunks)
async IAsyncEnumerable<LevelChunk> LoadChunksAsync() {
    foreach (var chunk in _chunks) {
        await UniTask.Yield();
        yield return chunk;
    }
}

// Consumer
await foreach (var chunk in LoadChunksAsync()) {
    ProcessChunk(chunk);
}
```

### `HashCode` helper
```csharp
// Before — manual GetHashCode
public override int GetHashCode() => Id.GetHashCode() ^ Name.GetHashCode() * 17;

// .NET Standard 2.1
public override int GetHashCode() => HashCode.Combine(Id, Name);
```

### `string.IsNullOrEmpty` → `string.IsNullOrWhiteSpace`
Prefer `IsNullOrWhiteSpace` when empty-but-spaces strings should be treated as empty.

### Nullable reference types (`?`)
Unity 6 projects can enable `<Nullable>enable</Nullable>` in the .csproj to get compiler warnings for potential null dereferences. If the project has NRTs enabled, flag places where `!` (null-forgiving) is used excessively or where nullable annotations are missing.

---

## What NOT to flag

- `async void` — Unity event functions (`Start`, `OnEnable`, etc.) that are async are fine as `async void` since they're called by the engine, not awaited.
- `foreach` over `List<T>` — this does not box in C# 9 and is perfectly fine in non-hot paths.
- Old `var x = new List<int>()` — this is still valid and only flag as Info if there are many occurrences.
