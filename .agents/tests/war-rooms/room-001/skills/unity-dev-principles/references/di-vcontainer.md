# VContainer Dependency Injection

Centralized service and dependency management for the Snake Escape project.

## Scopes

1. **GlobalScope**: Persistent services (Managers, SDK wrappers).
2. **GameplayScope**: Transient services (Logic, Models, Views).

## Registration Patterns

```csharp
public class GlobalScope : LifetimeScope
{
    protected override void Configure(IContainerBuilder builder)
    {
        // Singletons
        builder.Register<AudioService>(Lifetime.Singleton).AsImplementedInterfaces();
        builder.Register<LevelManager>(Lifetime.Singleton).AsSelf();
    }
}
```

## Injection Patterns

### [CORRECT] Constructor/Method Injection
```csharp
public class MyService
{
    private readonly IAudioService mAudio;

    [Inject]
    public MyService(IAudioService audio) => mAudio = audio;
}

public class MyMonoBehaviour : MonoBehaviour
{
    private IAudioService mAudio;

    [Inject]
    public void Construct(IAudioService audio) => mAudio = audio;
}
```

## Best Practices

- **MANDATORY**: Do not use `FindObjectOfType` or `GetComponent` for services. Let VContainer inject them.
- **MANDATORY**: Register by interface (`AsImplementedInterfaces`) for better mockability in tests.
- **AVOID**: Using `Lifetime.Singleton` for object-specific logic; use `Lifetime.Scoped`.
