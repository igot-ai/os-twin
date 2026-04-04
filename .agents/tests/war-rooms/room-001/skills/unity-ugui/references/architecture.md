# Vertical Slice Architecture

The Snake Escape project follows a **Vertical Slice Architecture** to maximize modularity and simplify feature replacement.

## Core Principle

Group all components of a feature (Logic, Models, Views, Data, UI) in the same directory structure, rather than grouping them by technical type (all scripts in one folder, all prefabs in another).

## Directory Structure

When creating a new feature or screen, organize it as follows:

```
Assets/Game/Scripts/{FeatureName}/
├── Logic/          # Pure C# game rules (testable, no MonoBehaviour)
├── Models/         # Reactive state (ViewModels, Data models)
├── Views/          # MonoBehaviour visual representations
├── Data/           # ScriptableObjects or JSON data structures
└── Enums/          # Feature-specific enums
```

## UI Vertical Slices

UI screens should also follow this pattern in the `Gameplay/UI/` directory:

```
Assets/Game/Scripts/Gameplay/UI/{ScreenName}/
├── {ScreenName}UI.cs      # The MainView (Inherits from MainView<TModel>)
├── {ScreenName}Model.cs   # The ViewModel
└── {ChildView}.cs         # Specific sub-views or components
```

## Benefits

1.  **Locality of Change**: When modifying a feature, all related files are in one place.
2.  **Scalability**: New features can be added without bloating global directories.
3.  **Replacement**: Replacing a feature (e.g., swapping gameplay logic) is as simple as replacing its vertical slice folder.
