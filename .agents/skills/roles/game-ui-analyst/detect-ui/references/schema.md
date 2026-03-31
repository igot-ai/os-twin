# UI Detection JSON Schema -- v5.0.0

This is the authoritative field reference for `*_detection.json` files produced by `unity-ui-analyzer`.

---

## Schema Changelog

| Version | Changes |
|---|---|
| **5.0.0** | Added flat `objects[]` array for animation-analyzer. Added `meta.to_canvas`. Added 12 new component types. Added `unity_type_name` on all components. Defined `screens[].type` enum. Clarified `missing_assets[].size` units. |
| 4.0.0 | Initial nested-tree schema with background classification. |

---

## Root Structure

```jsonc
{
  "schema": "5.0.0",

  "meta": {
    "source_image": "path/to/screenshot.png",
    "source_resolution": { "w": 750, "h": 1334 },    // actual image pixel dimensions
    "to_canvas": { "scale_x": 1.44, "scale_y": 1.439 }, // source_px * scale = canvas_units
    "background": {
      "type": "full_screen_sprite",    // see Background Type enum
      "sprite": "Assets/UI/Background/bg.png",  // non-null only when type="full_screen_sprite"
      "fit": "preserve_aspect",        // "preserve_aspect"|"stretch"|null
      "note": "One-line builder note."
    }
  },

  "canvas": {
    "w": 1080,
    "h": 1920,
    "scale_mode": "ScaleWithScreenSize",
    "match": 0.5,
    "render_mode": "ScreenSpaceOverlay"
  },

  "screens": [
    {
      "id": "screen_snake_case_id",
      "description": "One sentence: what this screen is and when it appears.",
      "type": "popup",                // see Screen Type enum
      "variant": null,
      "source_image": "<same as meta.source_image>",
      "background_override": null,    // same shape as meta.background; for per-variant BG only
      "missing_assets": [],           // see Missing Assets
      "objects": [],                  // FLAT list of all detected objects (for animation-analyzer)
      "root": { }                     // single root Node -- the Canvas GameObject (nested tree)
    }
  ]
}
```

### `meta.to_canvas` -- Conversion Factors

Computed as:
```
scale_x = canvas.w / source_resolution.w
scale_y = canvas.h / source_resolution.h
```

All `rect.pos` and `rect.size` values in the tree are already in canvas units. The `to_canvas` factors are provided so downstream consumers (e.g., `unity-animation-analyzer`) can convert pixel-space bounding boxes to canvas space.

### Background Type Enum

| Value | Meaning | Builder action |
|---|---|---|
| `"full_screen_sprite"` | Real sprite background | `Background` GO with stretch Image + AspectRatioFitter(EnvelopeParent) |
| `"gameplay_scene_passthrough"` | Gameplay visible behind popup | Comment only -- nothing created |
| `"render_texture"` | Canvas uses ScreenSpaceCamera with RenderTexture | Comment: `canvas.renderMode = ScreenSpaceCamera` |
| `"dim_overlay"` | Semi-transparent overlay on gameplay | `DimOverlay` GO with Image(color=#000000, alpha ~0.5) |
| `"none"` | No background | Nothing |

### Screen Type Enum

| Value | Typical usage |
|---|---|
| `"gameplay"` | In-game HUD overlay |
| `"popup"` | Modal dialog, reward popup |
| `"hud"` | Persistent game HUD |
| `"menu"` | Main menu, pause menu |
| `"level_complete"` | Win/complete screen |
| `"level_fail"` | Lose/fail screen |
| `"shop"` | Store, purchase screen |
| `"settings"` | Settings, options |
| `"loading"` | Loading screen |
| `"onboarding"` | First-time tutorial |

Use `snake_case`. If none fit, use the closest match.

---

## Node (Recursive -- Every GameObject)

```jsonc
{
  "id": "snake_case_id",       // -> GameObject.name
  "note": "One builder-hint sentence.",

  "rect": {
    "anchor": "middle_center", // named preset string OR [minX,minY,maxX,maxY] floats
    "pivot": [0.5, 0.5],      // [x, y]
    "pos": [0.0, 0.0],        // anchoredPosition [x, y] in canvas units
    "size": [200.0, 200.0]    // sizeDelta [w, h] in canvas units
                               // For stretch anchors: pos=[0,0] size=[0,0] means full-fill
  },

  "components": [ /* Component objects */ ],

  "children": [ /* Nodes, index 0 = back (lowest z-order) */ ]
}
```

### Anchor Preset Table

| Preset | anchorMin | anchorMax | Typical use |
|---|---|---|---|
| `"stretch"` | [0,0] | [1,1] | Full-parent fill, overlays |
| `"top_stretch"` | [0,1] | [1,1] | Top bar (pivot y=1) |
| `"bottom_stretch"` | [0,0] | [1,0] | Bottom bar (pivot y=0) |
| `"middle_center"` | [0.5,0.5] | [0.5,0.5] | Centered element |
| `"middle_left"` | [0,0.5] | [0,0.5] | Left-anchored |
| `"middle_right"` | [1,0.5] | [1,0.5] | Right-anchored |
| `"top_left"` | [0,1] | [0,1] | Top-left corner |
| `"top_right"` | [1,1] | [1,1] | Top-right corner |
| `"bottom_left"` | [0,0] | [0,0] | Bottom-left corner |
| `"bottom_right"` | [1,0] | [1,0] | Bottom-right corner |
| `"bottom_center"` | [0.5,0] | [0.5,0] | Bottom-center |

For non-preset anchors use raw array: `"anchor": [minX, minY, maxX, maxY]`

---

## Flat `objects[]` Array

Each screen has an `objects[]` array -- a flattened view of all nodes for consumers that need flat iteration (e.g., `unity-animation-analyzer`). Generated from the node tree in Step 7 of the workflow.

```jsonc
{
  "id": "btn_refill_green",
  "category": "UI/Button",           // derived from primary component type
  "bounding_box": [370, 1410, 710, 1570],  // [x1,y1,x2,y2] in source pixels
  "normalized_bbox": [0.343, 0.734, 0.657, 0.818],  // [x1,y1,x2,y2] normalized 0-1
  "canvas_position": { "x": 0, "y": -410 },  // anchoredPosition in canvas units
  "canvas_size": { "w": 340, "h": 160 },     // sizeDelta in canvas units
  "tree_path": "root/popup_card/btn_refill_green"  // dot-path in the node tree
}
```

**Category derivation rules:**
- Node has `Button` component -> `"UI/Button"`
- Node has `TextMeshProUGUI` -> `"UI/Text"`
- Node has `Image` with sprite -> `"UI/Image"`
- Node has `Image` without sprite (solid color) -> `"UI/Panel"`
- Node has `ScrollRect` -> `"UI/ScrollView"`
- Node has `Toggle` -> `"UI/Toggle"`
- Node has `Slider` -> `"UI/Slider"`
- Node has `RawImage` -> `"UI/RawImage"`
- Node has only children (container) -> `"UI/Container"`
- Node has `CanvasGroup` only -> `"UI/Group"`

**Bounding box computation:**
```
x1 = (canvas_pos_x - canvas_size_w/2) / to_canvas.scale_x
y1 = (canvas_h - (canvas_pos_y + canvas_size_h/2)) / to_canvas.scale_y
x2 = x1 + canvas_size_w / to_canvas.scale_x
y2 = y1 + canvas_size_h / to_canvas.scale_y
```

---

## Component Types

Each component includes a `unity_type_name` field for direct use with `gameobject-component-add`.

### Image
```jsonc
{
  "type": "Image",
  "unity_type_name": "UnityEngine.UI.Image",
  "sprite": "Assets/UI/Gameplay/btn.png",  // null for solid-color
  "color": "#FFFFFF",          // omit if white
  "image_type": "Simple",     // "Simple"|"Sliced"|"Filled"|"Tiled"
  "raycast": false,           // true ONLY on interactive roots (Button parents)
  "preserve_aspect": false,   // true for non-resizable icons
  "fill_method": null,        // "Horizontal"|"Vertical"|"Radial360"|... (Filled only)
  "fill_amount": null          // float 0-1 (Filled only)
}
```

> **Rule:** Use `preserve_aspect: true` only for fixed-size containers where you accept letterboxing. Use `AspectRatioFitter` when the RectTransform size must match the sprite's native ratio.

### RawImage
```jsonc
{
  "type": "RawImage",
  "unity_type_name": "UnityEngine.UI.RawImage",
  "texture": "Assets/UI/Textures/preview.png",  // raw texture path
  "color": "#FFFFFF",
  "raycast": false,
  "uv_rect": [0, 0, 1, 1]    // [x, y, w, h] -- default full texture
}
```

### TextMeshProUGUI
```jsonc
{
  "type": "TextMeshProUGUI",
  "unity_type_name": "TMPro.TextMeshProUGUI",
  "text": "Label text",
  "font_size": 56,             // canvas units (NOT source pixels)
  "font_style": "Bold",       // "Normal"|"Bold"|"Italic"|"Bold|Italic"
  "color": "#FFFFFF",
  "alignment": "Center",      // TMP TextAlignmentOptions name
  "overflow": "Overflow",     // TMP TextOverflowModes; default "Overflow"
  "auto_size": false,
  "raycast": false             // always false unless this text is interactive
}
```

### Button
```jsonc
{
  "type": "Button",
  "unity_type_name": "UnityEngine.UI.Button",
  "on_click": "intent_string"  // e.g. "navigate_main_menu", "open_shop"
}
```

### Toggle
```jsonc
{
  "type": "Toggle",
  "unity_type_name": "UnityEngine.UI.Toggle",
  "is_on": true,              // default state
  "toggle_group": null,        // id of ToggleGroup parent node, or null
  "on_value_changed": "intent_string"
}
```

### Slider
```jsonc
{
  "type": "Slider",
  "unity_type_name": "UnityEngine.UI.Slider",
  "min_value": 0.0,
  "max_value": 1.0,
  "value": 0.5,
  "whole_numbers": false,
  "direction": "LeftToRight",  // "LeftToRight"|"RightToLeft"|"BottomToTop"|"TopToBottom"
  "on_value_changed": "intent_string"
}
```

### ScrollRect
```jsonc
{
  "type": "ScrollRect",
  "unity_type_name": "UnityEngine.UI.ScrollRect",
  "horizontal": false,
  "vertical": true,
  "movement_type": "Elastic",  // "Unrestricted"|"Elastic"|"Clamped"
  "inertia": true,
  "viewport_id": "viewport",   // id of the child node acting as viewport
  "content_id": "content"      // id of the child node acting as content container
}
```

### InputField (TMP)
```jsonc
{
  "type": "TMP_InputField",
  "unity_type_name": "TMPro.TMP_InputField",
  "content_type": "Standard",  // "Standard"|"Integer"|"Decimal"|"Alphanumeric"|"Name"|"Email"|"Password"|"Pin"
  "placeholder_text": "Enter name...",
  "character_limit": 0,        // 0 = unlimited
  "on_end_edit": "intent_string"
}
```

### Dropdown (TMP)
```jsonc
{
  "type": "TMP_Dropdown",
  "unity_type_name": "TMPro.TMP_Dropdown",
  "options": ["Option A", "Option B", "Option C"],
  "value": 0,                  // selected index
  "on_value_changed": "intent_string"
}
```

### CanvasGroup
```jsonc
{
  "type": "CanvasGroup",
  "unity_type_name": "UnityEngine.CanvasGroup",
  "alpha": 1.0,
  "interactable": true,
  "blocks_raycasts": true
}
```

### AspectRatioFitter
```jsonc
{
  "type": "AspectRatioFitter",
  "unity_type_name": "UnityEngine.UI.AspectRatioFitter",
  "mode": "EnvelopeParent",    // "WidthControlsHeight"|"HeightControlsWidth"|"FitInParent"|"EnvelopeParent"
  "ratio": 1.0                 // sprite.width / sprite.height
}
```

### Mask
```jsonc
{
  "type": "Mask",
  "unity_type_name": "UnityEngine.UI.Mask",
  "show_mask_graphic": true    // whether the mask's Image is visible
}
```

### RectMask2D
```jsonc
{
  "type": "RectMask2D",
  "unity_type_name": "UnityEngine.UI.RectMask2D",
  "softness": [0, 0]          // [x, y] feathered edge softness
}
```

### HorizontalLayoutGroup / VerticalLayoutGroup
```jsonc
{
  "type": "HorizontalLayoutGroup",  // or "VerticalLayoutGroup"
  "unity_type_name": "UnityEngine.UI.HorizontalLayoutGroup",
  "spacing": 20.0,
  "padding": [0, 0, 0, 0],    // [left, right, top, bottom]
  "child_alignment": "MiddleCenter",
  "control_child_size": [true, true],   // [width, height]
  "force_expand": [false, false]        // [width, height]
}
```

### GridLayoutGroup
```jsonc
{
  "type": "GridLayoutGroup",
  "unity_type_name": "UnityEngine.UI.GridLayoutGroup",
  "cell_size": [100.0, 100.0],
  "spacing": [8.0, 8.0],
  "start_corner": "UpperLeft",
  "start_axis": "Horizontal",
  "child_alignment": "UpperLeft",
  "constraint": "FixedColumnCount",  // "Flexible"|"FixedColumnCount"|"FixedRowCount"
  "constraint_count": 4
}
```

### ContentSizeFitter
```jsonc
{
  "type": "ContentSizeFitter",
  "unity_type_name": "UnityEngine.UI.ContentSizeFitter",
  "horizontal_fit": "Unconstrained",  // "Unconstrained"|"MinSize"|"PreferredSize"
  "vertical_fit": "PreferredSize"
}
```

### LayoutElement
```jsonc
{
  "type": "LayoutElement",
  "unity_type_name": "UnityEngine.UI.LayoutElement",
  "min_width": -1,             // -1 = not set
  "min_height": -1,
  "preferred_width": -1,
  "preferred_height": -1,
  "flexible_width": -1,
  "flexible_height": -1,
  "ignore_layout": false
}
```

### Shadow
```jsonc
{
  "type": "Shadow",
  "unity_type_name": "UnityEngine.UI.Shadow",
  "effect_color": "#00000080",
  "effect_distance": [1.0, -1.0]  // [x, y] offset
}
```

### Outline
```jsonc
{
  "type": "Outline",
  "unity_type_name": "UnityEngine.UI.Outline",
  "effect_color": "#000000",
  "effect_distance": [1.0, -1.0]
}
```

---

## Missing Assets

Inside `screens[i].missing_assets[]`:

```jsonc
{
  "id": "badge_bonus_heart",
  "description": "Small red heart badge for +N values.",
  "needed_by": ["refill_bonus_badge"],   // node ids that reference this asset
  "size": [90, 90],                       // canvas units (same space as rect.size)
  "color_hint": "#e63946",
  "priority": "HIGH"                      // "HIGH"|"MEDIUM"|"LOW"
}
```

> **Important:** `size` is in **canvas units**, not source pixels.

---

## Background Override (Variant Use-Case Only)

Use only when a specific screen variant needs a different background than `meta.background`. Same shape as `meta.background`.

```jsonc
"background_override": {
  "type": "full_screen_sprite",
  "sprite": "Assets/UI/Background/bg_coin_variant.png",
  "fit": "preserve_aspect",
  "note": "Coin variant uses gold-tinted background."
}
```

---

## Validation Checklist

### Meta & Canvas
- [ ] `"schema": "5.0.0"` at root
- [ ] `meta.source_resolution` matches actual image pixel dimensions
- [ ] `meta.to_canvas.scale_x` == `canvas.w / source_resolution.w`
- [ ] `meta.to_canvas.scale_y` == `canvas.h / source_resolution.h`
- [ ] `meta.background.type` is one of the five enum values
- [ ] `meta.background.sprite` is non-null only when `type = "full_screen_sprite"`
- [ ] `meta.background.fit` is `"preserve_aspect"` or `"stretch"` when `type = "full_screen_sprite"`, else null

### Node Tree
- [ ] Root node has no explicit `Canvas` component -- builder adds Canvas + CanvasScaler from `canvas` block
- [ ] Every `rect.anchor` is a valid named preset string or a 4-element float array
- [ ] All `pos` and `size` values are in canvas units, not source pixels
- [ ] `font_size` in `TextMeshProUGUI` is in canvas units
- [ ] `children` order is back -> front (index 0 = furthest back)
- [ ] No duplicate `id` values anywhere in the tree

### Components
- [ ] Every `Image` with `image_type = "Sliced"` is for a resizable container or button
- [ ] Every `Button` component appears on the SAME node as its `Image` (not on a child icon)
- [ ] `raycast: true` set ONLY on interactive roots (Button/Toggle/Slider parents), false everywhere else
- [ ] Nodes inside a LayoutGroup use `anchor: "middle_center"` (layout overrides anchors at runtime)
- [ ] `GridLayoutGroup` nodes have all required fields (`cell_size`, `constraint_count`)
- [ ] `ScrollRect` nodes have valid `viewport_id` and `content_id` referencing child node IDs
- [ ] `Image.preserve_aspect` and `AspectRatioFitter` are NOT both on the same node
- [ ] Every `Button` node with an Image has `raycast: true` on that Image

### Assets
- [ ] Every non-null `sprite` path exists on disk OR has a `missing_assets` entry
- [ ] Every `missing_assets[].needed_by` ID exists in the node tree
- [ ] `missing_assets[].size` values are in canvas units

### Flat Objects Array
- [ ] `screens[].objects[]` contains one entry per leaf/meaningful node
- [ ] Each object's `bounding_box` is in source pixel coordinates
- [ ] Each object's `normalized_bbox` values are in 0-1 range
- [ ] Each object's `category` follows the category derivation rules
- [ ] Each object's `tree_path` matches an actual node path in the tree

---

## Mandatory Component Notes

These are project conventions from `unity-ui` -- the analyzer should emit hints for the builder:

| Component | When required | Note in JSON |
|---|---|---|
| `LocalizeUIText` | Every `TextMeshProUGUI` node | Add `"note": "Add LocalizeUIText for localization."` |
| `UIAnimationBehaviour` | Screen root if animated | Add `"note": "Add UIAnimationBehaviour for transitions."` |
| `CanvasGroup` | Any node that will fade/animate alpha | Add CanvasGroup component to the node |
| `UIParticle` | Any ParticleSystem inside Canvas | Add `"note": "Wrap in UIParticle for canvas rendering."` |

---

## Builder Integration -- MCP Tool Mapping

The detection JSON maps directly to `unity-editor` MCP tools:

| JSON field | MCP tool | Parameter |
|---|---|---|
| Node `id` | `gameobject-create` | `name` |
| Node `children` | `gameobject-set-parent` | child -> parent |
| Component `unity_type_name` | `gameobject-component-add` | `componentNames[]` |
| Component fields | `gameobject-component-modify` | `componentDiff` (SerializedMember) |
| `missing_assets[].sprite` path | `assets-find` | search query |
| Node tree path | `gameobject-find` | `path` in GameObjectRef |
