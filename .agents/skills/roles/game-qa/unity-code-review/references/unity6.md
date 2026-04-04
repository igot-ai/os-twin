# Unity 6 Best Practices

## Lifecycle & MonoBehaviour

### Method execution order
Correct order: `Awake` → `OnEnable` → `Start` → `FixedUpdate` → `Update` → `LateUpdate` → `OnDisable` → `OnDestroy`

- **Awake**: Initialize private state; never rely on other objects being initialized yet.
- **Start**: Wire up inter-object dependencies that depend on other objects being Awake'd.
- **Inject ([Inject] via VContainer)**: Runs before Start. Place constructor-like initialization here for DI-injected components.
- Avoid doing heavy work in `Update()`. Prefer event-driven or reactive (UniRx) patterns.

### Common lifecycle mistakes
- Accessing injected dependencies in `Awake()` before `[Inject]` has run — move to `Start()` or a post-inject init method.
- Calling `Destroy()` inside `Update()` without guarding — can cause null refs on the same frame.
- Forgetting to call `base.OnEnable()` / `base.OnDisable()` in derived MonoBehaviours.

---

## Performance

### GetComponent / Find — never in hot paths
```csharp
// BAD — called every frame
void Update() {
    var rb = GetComponent<Rigidbody2D>();
    rb.velocity = Vector2.zero;
}

// GOOD — cached at Awake/Start
private Rigidbody2D _rb;
void Awake() => _rb = GetComponent<Rigidbody2D>();
void Update() => _rb.linearVelocity = Vector2.zero;
```

`GameObject.Find`, `FindObjectOfType`, `FindObjectsOfType` are O(n) scene scans. They're acceptable in `Awake`/`Start` once, never in `Update`.

### Avoid boxing and heap allocations in Update
- Don't use `string` concatenation in `Update()` — use `string.Format` or `StringBuilder`.
- Avoid LINQ in hot paths (allocates enumerators). Cache results or use `for` loops.
- `Debug.Log` allocates — wrap with `#if UNITY_EDITOR` or a custom debug class.

### Object Pooling
Unity 6 has a built-in `UnityEngine.Pool.ObjectPool<T>`. Use it instead of `Instantiate`/`Destroy` in hot paths:
```csharp
private readonly ObjectPool<Bullet> _bulletPool = new(
    createFunc: () => Instantiate(_bulletPrefab),
    actionOnGet: b => b.gameObject.SetActive(true),
    actionOnRelease: b => b.gameObject.SetActive(false),
    actionOnDestroy: b => Destroy(b.gameObject),
    maxSize: 50
);
```

### Physics
- Use `Physics2D.GetRayIntersection` (single result) over `RaycastAll` when you only need the first hit.
- Prefer `OverlapCircleNonAlloc` / `RaycastNonAlloc` over allocating versions in hot paths.
- Layer masks should be pre-computed constants, not recalculated each frame.

---

## Input System (Unity 6 — New Input System only)

The old `Input.GetKey`, `Input.GetAxis`, `OnMouseDown` etc. are deprecated. Unity 6 projects should use the New Input System exclusively.

```csharp
// BAD — old Input Manager
void Update() {
    if (Input.GetMouseButtonDown(0)) { ... }
}

// GOOD — New Input System with generated class or direct subscription
// (This project already generates GameInputAction correctly)
```

Actions should be enabled/disabled explicitly (`inputAction.Enable()` / `.Disable()`) and disposed on `OnDestroy`.

---

## Dependency Injection (VContainer)

This project uses VContainer. The correct patterns are:

```csharp
// GOOD — field injection via [Inject] method
[Inject]
public void Construct(IService service) { _service = service; }

// BAD — service locator anti-pattern
private IService _service;
void Awake() { _service = FindObjectOfType<ServiceImpl>(); }

// BAD — static singleton
private IService _service;
void Awake() { _service = ServiceImpl.Instance; }
```

- Register interfaces, not concrete types: `builder.Register<MyService>(Lifetime.Scoped).As<IMyService>()`
- Use `Lifetime.Scoped` for per-scene objects, `Lifetime.Singleton` for global objects.
- `RegisterInstance` for ScriptableObjects and pre-built objects.

---

## Async / UniTask

This project uses UniTask. Rules:

```csharp
// BAD — Coroutine for anything complex
IEnumerator DoWork() {
    yield return new WaitForSeconds(1f);
    DoThing();
}

// GOOD — UniTask
async UniTask DoWorkAsync(CancellationToken ct = default) {
    await UniTask.Delay(TimeSpan.FromSeconds(1f), cancellationToken: ct);
    DoThing();
}
```

- Always accept and forward `CancellationToken` in async methods so callers can cancel on `OnDestroy`.
- Use `.Forget()` only when you truly don't care about the result and exceptions; otherwise `await` or chain with `.ContinueWith`.
- UniTask exceptions are swallowed with `.Forget()` — add `.Forget(e => Debug.LogException(e))` for safety.
- Dispose `CancellationTokenSource` in `OnDestroy`.

---

## Reactive (UniRx)

This project uses UniRx. Rules:

```csharp
// BAD — not tracking subscription, causes memory leak
void Start() {
    someObservable.Subscribe(_ => DoThing());
}

// GOOD — using CompositeDisposable
private readonly CompositeDisposable _disposables = new();
void Start() {
    someObservable.Subscribe(_ => DoThing()).AddTo(_disposables);
}
void OnDestroy() {
    _disposables.Dispose();
}
```

- All subscriptions in a MonoBehaviour should use `AddTo(_disposables)` or `AddTo(this)`.
- `ReactiveProperty<T>` is preferred over mutable fields that emit events manually.
- Use `Subject<Unit>` for fire-and-forget events; `Subject<T>` for typed events.

---

## ScriptableObjects

ScriptableObjects are data containers — they should not hold runtime mutable state (data that changes during play). Use them for configuration:

```csharp
// GOOD — read-only config
[CreateAssetMenu]
public class GameConfig : ScriptableObject {
    public float MoveSpeed;
    public int MaxLives;
}

// BAD — mutable runtime state in SO (persists between play sessions in editor)
public class PlayerStats : ScriptableObject {
    public int CurrentScore; // changes at runtime — use a regular class instead
}
```

---

## Serialization

- Prefer `[SerializeField] private` fields over `public` fields for Inspector-exposed values. This keeps the public API clean.
- Use `[field: SerializeField]` for auto-property serialization in C# 9+:
  ```csharp
  [field: SerializeField] public float MoveSpeed { get; private set; }
  ```
- Do not serialize interfaces or abstract types directly — Unity can't deserialize them.
- `[Header("...")]` and `[Tooltip("...")]` make Inspector usable without reading code.

---

## Memory Management

- Unsubscribe from C# events (`+=`) in `OnDisable`/`OnDestroy` to prevent leaks.
- If a class implements `IDisposable`, it must be disposed. Use `using` or explicit `.Dispose()`.
- For large collections, prefer `List<T>.Clear()` + reuse over creating new collections.
- Avoid closures that capture `this` inside `Update`-called lambdas — they pin the object.

---

## Naming Conventions

Follow Unity's official C# style guide:
- `public`/`protected` properties and methods: `PascalCase`
- `private` fields: `_camelCase` with underscore prefix
- Constants and `static readonly`: `PascalCase`
- Interfaces: `IPascalCase`
- Enums: `EPascalCase` (this project's convention based on `EGameState`, `EBooster`, etc.)
- No Hungarian notation (avoid `bIsActive`, `iCount`)
