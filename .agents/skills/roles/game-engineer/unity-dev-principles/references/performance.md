# Performance & Mobile Optimization

Targets and best practices for the mobile puzzle platform.

## Targets

| Metric | Target |
|--------|--------|
| **Frame Rate** | 60 FPS |
| **Draw Calls** | < 100 per scene |
| **GC Allocations** | 0/frame in gameplay |

## Best Practices

1. **Caching**: Cache `Transform`, `Component` references in `Awake`. Never call `GetComponent` in `Update`.
2. **Material Batching**: Use material properties and GPU instancing for identical objects.
3. **Strings**: Avoid string concatenation (`+`) in `Update`. Use `StringBuilder` or cached strings.
4. **Physics**: Use `NonAlloc` variants (e.g. `Physics.RaycastNonAlloc`).

## Memory Management

- Use `Addressables` for lazy asset loading.
- Unload unused assets routinely.
- Use `UnityEngine.Pool` for all temporary collections.

## Core Rules

- **MANDATORY**: Profile first, then optimize.
- **MANDATORY**: No `FindObjectOfType` or `GameObject.Find` in gameplay loops.
- **MANDATORY**: Use `UniTask` to prevent `Task` allocations.
