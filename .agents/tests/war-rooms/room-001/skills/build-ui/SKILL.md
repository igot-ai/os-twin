---
name: build-ui
description: Build Unity UI prefabs from detection JSON (schema 5.0.0) via MCP tools. Consumes output from unity-ui-analyzer and creates a complete GameObject hierarchy with components, properties, and placeholder assets. Triggers on 'build UI from JSON', 'prefab from detection', 'build prefab from screenshot', 'construct UI', 'detection JSON to prefab', 'create UI from detection', 'build from detection JSON', 'JSON to prefab', 'build detected UI'. Use this skill whenever the user has a _detection.json file and wants to create a Unity prefab from it -- even if they just say 'build this' or 'turn this into a prefab' after running detect-ui."
tags: []

---

**Quick Start:** Parse detection JSON -> validate schema 5.0.0 -> plan build (count nodes, missing assets) -> create hierarchy depth-first via MCP -> apply project conventions -> validate via screenshot -> save prefab.

**Required skills:** This skill uses `develop-unity-ui` MCP tools for all GameObject/component operations and follows `unity-ui` conventions for hierarchy structure.

---

## Inputs

Parse `$ARGUMENTS` as:
- `$0` -- detection JSON file path (required)
- `$1` -- prefab save path (optional, default: `Assets/Game/Prefabs/UI/<screen_id>.prefab`)

---

## Step 1 -- Parse and Validate Detection JSON

Read the detection JSON file. Validate:
- `schema` field equals `"5.0.0"` -- abort with error if not
- `screens[]` has at least one entry
- `screens[0].root` exists and has `children[]`
- `meta.to_canvas` has `scale_x` and `scale_y`
- `canvas` block has `w`, `h`, `scale_mode`

Print a build plan summary:

```
Build Plan
----------
Screen:        <screens[0].id>
Type:          <screens[0].type>
Total nodes:   <count all nodes in tree recursively>
Missing assets: <missing_assets.length>
Background:    <meta.background.type>
Prefab path:   <$1 or default>
```

---

## Step 2 -- Prepare the Scene

1. Open or confirm the target scene is loaded (use `scene-list-opened`).
2. Find or create a Canvas root for building:
   - If a Canvas named `UI_<ScreenId>` exists, use it (clear children first with confirmation).
   - Otherwise, `gameobject-create` a new Canvas.

---

## Step 3 -- Create Background (if needed)

Based on `meta.background.type`, create the background layer before the main content:

| `type` | Action |
|---|---|
| `"full_screen_sprite"` | Create `Background` GO with stretch anchor, add Image (sprite from `meta.background.sprite`), add AspectRatioFitter (mode: EnvelopeParent) |
| `"dim_overlay"` | Create `DimOverlay` GO with stretch anchor, add Image (color: #00000080), set raycast: true |
| `"gameplay_scene_passthrough"` | Skip -- add comment note to root |
| `"render_texture"` | Skip -- add comment note about ScreenSpaceCamera |
| `"none"` | Skip |

---

## Step 4 -- Build Hierarchy (Depth-First)

Walk the `root` node tree depth-first. For each node:

### 4.1 Create GameObject
```
gameobject-create(name: node.id)
```

### 4.2 Set Parent
```
gameobject-set-parent(child: node.id, parent: parent_node.id)
```
Preserve sibling order (children array index 0 = first child = back, last = front).

### 4.3 Configure RectTransform

Convert the `rect` block to RectTransform properties using the anchor preset table in `references/build-rules.md`.

```
gameobject-component-modify(target: node.id, component: "RectTransform", properties: {
    anchorMin, anchorMax, pivot, anchoredPosition, sizeDelta
})
```

### 4.4 Add Components

For each component in `node.components[]`:

1. **Add the component:**
   ```
   gameobject-component-add(target: node.id, type: component.unity_type_name)
   ```

2. **Set component properties:**
   Map detection JSON fields to Unity serialized property paths using the mapping table in `references/build-rules.md`.
   ```
   gameobject-component-modify(target: node.id, component: component.unity_type_name, properties: {...})
   ```

### 4.5 Handle Missing Sprites

When a component references a sprite path that is in `missing_assets[]`:
1. Keep the Image component but set sprite to null.
2. Set the Image color to `missing_assets[].color_hint` so the placeholder is visible.
3. Log: `"[PLACEHOLDER] <node.id>: missing <asset_id> -- <description>"`

### 4.6 Component Order

Add components in this order (when multiple exist on one node):
1. Layout components (HorizontalLayoutGroup, VerticalLayoutGroup, GridLayoutGroup, ContentSizeFitter, LayoutElement)
2. Visual components (Image, RawImage, TextMeshProUGUI, Mask, RectMask2D)
3. Interaction components (Button, Toggle, Slider, ScrollRect, TMP_InputField, TMP_Dropdown)
4. Effect components (Shadow, Outline)
5. Utility components (CanvasGroup, AspectRatioFitter)

---

## Step 5 -- Wire Cross-References

After the full tree is built, wire components that reference other nodes:

| Component | Property | Value |
|---|---|---|
| ScrollRect | `viewport` | Reference to child node with `viewport_id` |
| ScrollRect | `content` | Reference to child node with `content_id` |
| Toggle | `graphic` | Reference to checkmark child Image |
| Slider | `fillRect` | Reference to fill child RectTransform |
| Slider | `handleRect` | Reference to handle child RectTransform |

Use `gameobject-component-modify` with instance ID references from `gameobject-find`.

---

## Step 6 -- Apply Project Conventions

After the tree is fully built, apply mandatory project conventions:

### 6.1 LocalizeUIText
Add `LocalizeUIText` component to every node that has a `TextMeshProUGUI` component.
```
gameobject-component-add(target: text_node.id, type: "Game.UI.LocalizeUIText")
```

### 6.2 UIAnimationBehaviour
If `screens[0].type` is `popup`, `level_complete`, `level_fail`, or `onboarding`, add `UIAnimationBehaviour` to the screen root.
```
gameobject-component-add(target: root.id, type: "Game.UI.UIAnimationBehaviour")
```

### 6.3 Raycast Optimization
Verify that `raycast: false` is set on all non-interactive elements. Only Button backgrounds, Toggle backgrounds, Slider handles, and ScrollRect viewports should have raycast enabled.

### 6.4 SafeArea
If any node has a note mentioning "SafeArea", add the project's SafeArea component to that node.

---

## Step 7 -- Validate

### Visual Validation
Take a screenshot of the built hierarchy using `screenshot-game-view` and compare layout with the source image referenced in `meta.source_image`.

### Structural Validation Checklist
- [ ] All nodes from detection JSON tree are present as GameObjects
- [ ] Parent-child relationships match the tree structure
- [ ] Every TextMeshProUGUI node has a LocalizeUIText sibling component
- [ ] Interactive elements have raycast:true, non-interactive have raycast:false
- [ ] Missing assets produce visible placeholders (colored rectangles)
- [ ] No Unity console errors (check via `console-get-logs`)

### Validation Summary
Print:
```
Build Complete
--------------
GameObjects created: <N>
Components added:    <N>
Missing assets:      <N> (placeholders created)
Console errors:      <N>
Screenshot:          <path>
```

---

## Step 8 -- Save Prefab

Save the built hierarchy as a prefab:
```
assets-prefab-create(source: root_gameobject, path: prefab_save_path)
```

Default path: `Assets/Game/Prefabs/UI/<screens[0].id>.prefab`

---

## Failure Modes

| Symptom | Action |
|---|---|
| Schema version != 5.0.0 | Abort with error. Do not attempt to parse older schemas. |
| MCP tool call fails | Retry once. If still failing, log the failed node and continue with remaining nodes. |
| Missing unity_type_name | Skip the component. Log warning. |
| Component-add fails (type not found) | Log warning, continue. Check for typos in unity_type_name. |
| Canvas not found in scene | Create a new Canvas with project-standard settings (1080x1920, ScaleWithScreenSize, Match 0.5). |
| Prefab save fails | Save the scene instead and log the hierarchy path for manual prefab extraction. |

---

## References

| File | Content | When to read |
|---|---|---|
| `references/build-rules.md` | Anchor-to-RectTransform mapping, component property mapping, MCP call patterns | Before building any node |
| `references/example-build-log.md` | Worked example: detection JSON -> MCP call sequence | First time using this skill |

---

## Related Skills

| Need | Skill                   |
|---|-------------------------|
| Generate detection JSON from screenshot | `detect-ui`             |
| MCP tool schemas and patterns | `develop-unity-ui`      |
| uGUI hierarchy conventions | `unity-ui`              |
| Animate the built UI | `unity-ui-animation`    |
| Add visual effects | `unity-ui-effect`       |
| Wire reactive data binding | `unity-ui-reactive`     |
| Localization setup | `unity-ui-localization` |
| Performance optimization | `unity-ui-perf`         |

---

## Project Conventions

- **Canvas**: 1080x1920, ScaleWithScreenSize, Match 0.5, ScreenSpaceOverlay
- **Namespaces**: All game code under `Game.*`
- **Mandatory**: `LocalizeUIText` on every TMP text node
- **Mandatory**: `UIAnimationBehaviour` on animated screen roots (popup, level_complete, level_fail)
- **Performance**: Disable raycast on non-interactive elements
- **Clipping**: Prefer `RectMask2D` over `Mask` for scroll views
- **No UI Toolkit**: uGUI Prefabs only
