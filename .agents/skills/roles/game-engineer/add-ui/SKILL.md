---
name: Add UGUI View
description: Create a new UI screen following Vertical Slice Architecture and MVC/MVP patterns.
version: 1.1.0
category: Implementation
applicable_roles: [game-engineer, engineer, ui-designer]
tags: [engineer, implementation, ui, unity, ugui]

source: project
author: Agent OS Core
---

# Workflow: Add UI Screen
description: Create a new UI screen following Vertical Slice Architecture and MVC/MVP.

## Preconditions
- Reference screenshot (PNG/JPG) of the target UI screen is available.
- `unity-ugui` skill and `../unity-ugui/references/ui-animation.md` reference read.
- Screen purpose and data model requirements defined.

## Steps

1. **Detect**: Run `../detect-ui` skill on the reference screenshot.
   - Input: `<path/to/reference.png> [output_json_path] [real_bg_asset_path]`
   - Output: `*_detection.json` describing all UI objects, positions, assets, and background context.
   - Read the output JSON to understand the object hierarchy before proceeding.

2. **Design**: Review the `_detection.json` object list. Reference `../unity-ugui/references/ugui-components.md` to confirm component mapping per detected category.

3. **Model**: Create `[ScreenName]Model.cs` (state) using `ReactiveProperty<T>`.

4. **View**: Create `[ScreenName]View.cs` or `[ScreenName]UI.cs` inheriting from `BaseView` or equivalent.

5. **Binding**: Use UniRx/UniTask for Model-View binding in the View's `Construct()` or `Initialize()` method.

6. **Prefab**: Create the UI Prefab in the Editor using MCP tools (via `unity-editor` skill):
   - Use `assets-prefab-create` skill to create the prefab asset.
   - Use `gameobject-component-add` skill to attach components.
   - Organize hierarchy per detected `parent_id` relationships in `_detection.json` and `../unity-ugui/references/ugui-patterns.md`.

7. **DI**: Register Model, View, and optional Controller/Presenter in the appropriate `LifetimeScope`.

8. **Visual Validation** — systematic comparison of the rendered UI against the reference image:

   **8a. Capture** — use the `screenshot-game-view` skill (returns image directly to the LLM; no project file saved). If a zoomed crop of a specific zone is needed for detail, save it to `/tmp/` only — never into the project directory.

   **8b. Compare zones** — place the captured screenshot next to the reference and verify each zone:

   | Zone | What to check |
   |---|---|
   | **Every element** | Position, size, and spacing match reference proportionally |
   | **Text elements** | Visible (correct color contrast against background); not clipped; font weight matches |
   | **Image elements** | Correct sprite rendered; `Image.Type.Sliced` used only when sprite has 9-slice border data |
   | **Containers** | Correct sibling order (background `[0]`, icon `[1]`, label `[2]`); no z-fighting |
   | **Layout groups** | Buttons/icons evenly distributed; badges anchored to their parent corner |

   **8c. Diagnose invisible elements** — if anything doesn't render:
   - Verify the `RectTransform` is inside the canvas viewport via `GetWorldCorners()`.
   - Check `Image.Type`: switch `Sliced` → `Simple` for sprites without border data.
   - Check text color against its background — light text on light bg or vice versa is invisible.
   - Check sibling index — a background drawn at a higher index will occlude children.

   **8d. Fix + re-capture loop** — apply fixes, capture again with `screenshot-game-view`, repeat until all zones pass.

9. **Final Gate**: Execute `validation-and-review` workflow.

## Output
- `*_detection.json` detection file describing all UI elements.
- Functional UI prefab with components wired to `[ScreenName]View.cs`.
- Screen integrated with the `ScreenManager`.