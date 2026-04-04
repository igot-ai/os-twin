# Project Coding Standards: Snake Escape

Mandatory patterns and strict rules for the Snake Escape project. These take precedence over generic Unity best practices.

## Mandatory Rules

### 1. English Only [ENGLISH-ONLY]
- **Rule**: All code, comments, documentation, and string literals (where applicable) must be in English. If the user requests is not in English, translate the request internally to English, perform the review in English, and then translate the response back to the user's language.

### 2. Pure C# Logic Separation [UI-LOGIC-SEP]
- **Rule**: Game logic must be decoupled from MonoBehaviours.
- **Pattern**: 
    - Logic Classes: Pure C#, no `UnityEngine` inheritance.
    - View Classes: `MonoBehaviour`, handles visuals and sound.
    - Controller: Orchestrates flow.
- **Injected**: Use `[Inject]` for dependency injection in logic classes.

## Technology Stack Standards

### 1. Asynchronous: UniTask [ASYNC]
- **Rule**: Use `UniTask` or `UniTask<T>` instead of `Task`.
- **Reason**: Allocation-free async performance in Unity.
- **Check**: Look for `destroyCancellationToken` usage in MonoBehaviours.

### 2. Reactive: UniRx [REACTIVE]
- **Rule**: Use `ReactiveProperty<T>` for state and `Subject<T>` for events.
- **Check**: Ensure all subscriptions use `.AddTo(this)` or a `CompositeDisposable`.

### 3. Dependency Injection: VContainer [DI]
- **Rule**: Prefer constructor or method injection over `FindObjectOfType` or `GetComponent`.
- **Check**: Look for `[Inject]` attributes on `Construct` methods.

### 4. Memory: Collection Pooling [POOLING]
- **Rule**: Use `UnityEngine.Pool` (e.g., `ListPool<T>.Get(out list)`) for temporary collections in hot paths (Update/FixedUpdate).
- **Avoid**: `new List<T>()` or `.ToList()` in performance-critical loops.

## Testing Standards

- **Rule**: All pure C# logic must have corresponding `EditMode` tests.
- **Rule**: High-level integration tests should use `PlayMode`.
