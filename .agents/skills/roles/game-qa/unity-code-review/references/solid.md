# SOLID Principles in Unity C#

## S — Single Responsibility Principle

A class should have one reason to change. In Unity, this is the most commonly violated principle because MonoBehaviours tend to accumulate responsibilities.

### Warning signs
- A MonoBehaviour handles UI, game logic, audio, AND analytics in the same class.
- A class name contains "Manager" and does more than manage one thing.
- A class has 10+ injected dependencies — strong signal it's doing too much.

### Common violations and fixes

```csharp
// BAD — PlayerController handles movement, sound, and analytics
public class PlayerController : MonoBehaviour {
    public void Move(Vector2 dir) {
        transform.position += (Vector3)dir;
        _audioService.Play(EAudioClip.Move);
        Analytics.Track("player_moved");
    }
}

// GOOD — separate concerns
public class PlayerMovement : MonoBehaviour {
    public void Move(Vector2 dir) => transform.position += (Vector3)dir;
}
// Side effects handled by a dedicated observer/controller
```

In this project, `GameplayController` is a good example of an orchestrator — it's acceptable for it to coordinate multiple systems as long as it *delegates* rather than *implements* each concern.

---

## O — Open/Closed Principle

Classes should be open for extension, closed for modification. In Unity, this usually means preferring composition over inheritance, and using interfaces/abstract classes to define contracts.

### Warning signs
- Adding a new booster type requires editing a switch/if-else chain in the core controller.
- A method has a growing list of `if (type == X)` branches.

### Common violations and fixes

```csharp
// BAD — closed to extension without modification
void ActivateBooster(EBooster type) {
    if (type == EBooster.Hint) { ... }
    else if (type == EBooster.Ruler) { ... }
    // Adding a new booster means editing this method
}

// GOOD — open to extension via strategy/interface
public interface IBoosterStrategy {
    void Activate();
}
// New booster = new class implementing IBoosterStrategy, no existing code changes
```

---

## L — Liskov Substitution Principle

Subtypes must be substitutable for their base types without breaking the program. In Unity, this is violated when an override silently does nothing or changes the contract.

### Warning signs
- An override throws `NotImplementedException` or `NotSupportedException`.
- A derived MonoBehaviour overrides `Start()` or `Update()` and forgets to call `base.Start()`.
- A derived class weakens postconditions (returns null where base guarantees non-null).

### Common violations and fixes

```csharp
// BAD — derived class violates the contract
public class SilentAudioService : IAudioService {
    public void Play(EAudioClip clip) {
        // silently does nothing — callers can't tell if audio played
    }
}

// GOOD — explicitly communicates intent
public class NullAudioService : IAudioService {
    public void Play(EAudioClip clip) { /* intentional no-op for tests */ }
}
// Or better: use the Null Object Pattern explicitly named as such
```

---

## I — Interface Segregation Principle

Clients should not depend on methods they don't use. Keep interfaces small and focused.

### Warning signs
- An interface has 10+ methods; most implementations leave half of them empty.
- A class is forced to implement interface methods that are irrelevant to its purpose.

### Common violations and fixes

```csharp
// BAD — fat interface
public interface IGameService {
    void PlayAudio(EAudioClip clip);
    void TriggerHaptic(HapticType type);
    void TrackAnalytics(string eventName);
    void SaveData(string key, object value);
}

// GOOD — segregated interfaces
public interface IAudioService { void Play(EAudioClip clip); }
public interface IHapticService { void Trigger(HapticType type); }
public interface IAnalyticsService { void Track(string eventName); }
```

The project already uses `IAudioService` and `IHapticService` separately — good pattern to continue.

---

## D — Dependency Inversion Principle

Depend on abstractions, not concretions. High-level modules should not depend on low-level modules. In Unity, this is best enforced via DI containers (VContainer in this project).

### Warning signs
- Direct `new ConcreteService()` inside a class that should receive dependencies.
- `GetComponent<ConcreteType>()` instead of `GetComponent<IInterface>()`.
- Accessing `ServiceLocator.Instance.Get<X>()` or static singletons from within logic classes.
- Concrete type parameters in `[Inject]` methods where an interface would suffice.

### Common violations and fixes

```csharp
// BAD — depends on concrete type, hard to test or swap
public class GameplayController : MonoBehaviour {
    private AudioManager _audio = new AudioManager();
}

// GOOD — depends on abstraction, injected by VContainer
public class GameplayController : MonoBehaviour {
    private IAudioService _audio;

    [Inject]
    public void Construct(IAudioService audio) => _audio = audio;
}
```

When reviewing `LifetimeScope`-derived classes (VContainer registration), check that concrete implementations are registered against their interfaces: `.As<IInterface>()`, not just `.AsSelf()` unless the concrete type IS the intended API surface.
