# Architecture & Logic Separation

Decoupling game logic from Unity's MonoBehaviour system for testability and performance.

## The Pattern

1. **Logic (Pure C#)**: Contains the rules, calculations, and data management. No `UnityEngine` basics (no `MonoBehaviour`, `Update`, `Transform`).
2. **View (MonoBehaviour)**: Handles rendering, animations, and sound. Receives state from Logic.
3. **Controller (MonoBehaviour/Logic)**: Orchestrates the flow between Logic and View.

## File Organization

- `Assets/Game/Scripts/Gameplay/Logic/` → Pure C# classes.
- `Assets/Game/Scripts/Gameplay/Views/` → Renderer MonoBehaviours.
- `Assets/Game/Scripts/Gameplay/GameplayController/` → Orchestrators.

## Example Separation

### Logic (Pure C#)
```csharp
namespace Game.Gameplay.Logic
{
    public class SnakeMovementLogic
    {
        public Vector2Int Move(Vector2Int current, Vector2Int dir)
        {
            return current + dir;
        }
    }
}
```

### View (Unity)
```csharp
public class SnakeRenderer : MonoBehaviour
{
    public void UpdatePosition(Vector3 worldPos)
    {
        transform.position = worldPos;
    }
}
```

## Benefits

- **Speed**: Pure C# logic runs faster than MonoBehaviour Update loops.
- **Testing**: Can be unit tested in milliseconds without opening the Unity Editor.
- **Decoupling**: Visuals can change without touching the game rules.

## Core Rules

- **MANDATORY**: Logic classes must not inherit from `MonoBehaviour`.
- **MANDATORY**: Use `[Inject]` to provide services to Logic classes.
- **AVOID**: Putting complex math or state transitions inside `Update()`.
