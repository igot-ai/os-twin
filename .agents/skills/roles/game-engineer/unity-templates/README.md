# C# Templates

Code templates for creating new features following the project's architecture.

## Usage

1. Copy the templates you need into your feature folder under `Assets/Game/Scripts/{Feature}/`
2. Replace all `{Feature}` placeholders with your feature name (e.g., `Puzzle`)
3. Replace all `{feature}` (lowercase) placeholders accordingly (e.g., `puzzle`)
4. Remove or customize TODO comments
5. Register your classes in the appropriate DI scope (GlobalScope or GameplayScope)

## Template Selection Guide

| Complexity | Templates to Copy |
|------------|-------------------|
| **Minimal logic** | `FeatureGameLogic`, `FeatureEvents`, `EFeatureState` |
| **Logic + view** | Above + `FeatureController`, `FeatureController.Debug`, `FeatureView`, `FeatureConfig`, `FeatureModel` |
| **With UI screen** | Above + `FeatureUI`, `FeatureUIModel` |
| **Service pattern** | `IFeatureService`, `FeatureInstaller`, `FeatureConfig` |
| **Data model** | `FeatureData` |

## File Mapping

| Template | Target Path |
|----------|-------------|
| `FeatureGameLogic.cs.txt` | `{Feature}/Logic/{Feature}GameLogic.cs` |
| `FeatureEvents.cs.txt` | `{Feature}/Logic/{Feature}Events.cs` |
| `FeatureModel.cs.txt` | `{Feature}/Models/{Feature}Model.cs` |
| `FeatureData.cs.txt` | `{Feature}/Data/{Feature}Data.cs` |
| `EFeatureState.cs.txt` | `{Feature}/Enums/E{Feature}State.cs` |
| `FeatureController.cs.txt` | `{Feature}/{Feature}Controller.cs` |
| `FeatureController.Debug.cs.txt` | `{Feature}/{Feature}Controller.Debug.cs` |
| `FeatureView.cs.txt` | `{Feature}/Views/{Feature}View.cs` |
| `FeatureConfig.cs.txt` | `{Feature}/Config/{Feature}Config.cs` |
| `FeatureInstaller.cs.txt` | `{Feature}/{Feature}Installer.cs` |
| `FeatureUI.cs.txt` | `{Feature}/UI/Views/{Feature}UI.cs` |
| `FeatureUIModel.cs.txt` | `{Feature}/UI/Models/{Feature}UIModel.cs` |
| `IFeatureService.cs.txt` | `{Feature}/Interfaces/I{Feature}Service.cs` |

## DI Registration

After creating files, register in the appropriate scope:

### GameplayScope (per-gameplay lifetime)
```csharp
// In GameplayScope.Configure():
builder.RegisterInstance(_{feature}Config).AsSelf();
builder.RegisterInstance(_{feature}Controller).AsSelf();
builder.Register<{Feature}Model>(Lifetime.Scoped).AsSelf();
```

### GlobalScope (singleton lifetime)
```csharp
// In GlobalScope.Configure():
new {Feature}Installer(_{feature}Config).Install(builder);
```

## Architecture Reference

See `.agent/architecture/ARCHITECTURE.md` for the full architecture guide including:
- Class responsibilities
- Reactive state rules
- Async patterns
- Naming conventions
- Skill coverage map
