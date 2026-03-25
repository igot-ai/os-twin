---
name: detect-ui
description: Analyse a UI reference screenshot and generate a _detection.json (schema 4.0.0). Output is a nested, canvas-native tree that the add-ui workflow reads directly to build Unity GameObjects. Covers all background cases — reference-only screenshots, real background assets, gameplay-passthrough scenes, and per-variant background overrides.
argument-hint: <detection_image> [output_json_path] [real_bg_asset_path]
allowed-tools: Read, Write, Glob, Grep
---

Analyse the UI screenshot and produce a complete `*_detection.json` (schema **4.0.0**).

Parse `$ARGUMENTS` as:
- `$0` — detection image path (required)
- `$1` — if ends with `.json` → output path; if ends with `.png/.jpg` → real background asset path
- `$2` — output path (only when `$1` was used as background path)

Default output path: replace `$0` extension with `_detection.json`.

---

## Step 1 — Classify the background

Determine `meta.background` before any measurement.

```
Did the user supply $2 (explicit background asset)?
  YES → type = "full_screen_sprite", sprite = $2
  NO  → Does $0 show gameplay behind the popup?
          Real camera/board scene → type = "gameplay_scene_passthrough"
          Just a solid colour     → type = "none"
        Does $0 look like a standalone background image (check Glob "Assets/UI/Background/*.png")?
          YES → type = "full_screen_sprite", sprite = $0
          NO  → type = "none"
```

| `type` | Builder action |
|---|---|
| `"full_screen_sprite"` | `Background` GO → stretch → `Image(sprite)` + `AspectRatioFitter(EnvelopeParent)` |
| `"gameplay_scene_passthrough"` | Comment only — nothing created behind the popup |
| `"render_texture"` | Comment only — `canvas.renderMode = ScreenSpaceCamera` note |
| `"none"` | Nothing |

---

## Step 2 — Read the image

View `$0`. Note every visible layer back → front.

---

## Step 3 — Detect canvas settings

Identify the CanvasScaler reference resolution (default **1080 × 1920** if unknown).

---

## Step 4 — Detect all UI objects, back → front

For each visible UI object (skip the scene background — that's in `meta.background`):

a. Measure position and size **directly in canvas units** (reference resolution space).  
b. Pick the correct named anchor preset (see table below) or use a raw 4-float array.  
c. Find sprite with `Glob "Assets/UI/**/*.png"`. Add to `missing_assets` if absent.  
d. List all Unity components as typed objects.  
e. Write a `note` (one builder-hint sentence only).

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

> For non-preset anchors use raw array: `"anchor": [minX, minY, maxX, maxY]`

---

## Step 5 — Fill `missing_assets[]`

For every sprite not found on disk, add one entry.

---

## Step 6 — Validate

Run the checklist at the bottom.

---

## Step 7 — Write the JSON and print summary

---

## Output JSON Structure (schema 4.0.0)

```jsonc
{
  "schema": "4.0.0",

  "meta": {
    "source_image": "<$0>",
    "source_resolution": { "w": 1080, "h": 1920 },  // actual $0 pixel dimensions
    "background": {
      "type": "full_screen_sprite",  // "full_screen_sprite"|"gameplay_scene_passthrough"|"render_texture"|"none"
      "sprite": "Assets/UI/Background/bg.png",  // non-null only when type="full_screen_sprite"
      "fit":    "preserve_aspect",               // "preserve_aspect"|"stretch"|null
      "note":   "One-line builder note."
    }
  },

  "canvas": {
    "w": 1080,
    "h": 1920,
    "scale_mode":  "ScaleWithScreenSize",
    "match":       0.5,
    "render_mode": "ScreenSpaceOverlay"
  },

  "screens": [
    {
      "id":          "screen_snake_case_id",
      "description": "One sentence: what this screen is and when it appears.",
      "type":        "gameplay|popup|hud|menu|level_complete|shop|settings|...",
      "variant":     null,
      "source_image": "<same as meta.source_image>",
      "background_override": null,  // same shape as meta.background; non-null for per-variant BG only
      "missing_assets": [],         // see Missing Assets section
      "root": { }                   // single root Node — the Canvas GameObject
    }
  ]
}
```

---

## Node (recursive — every GameObject)

```jsonc
{
  "id":   "snake_case_id",   // → GameObject.name
  "note": "One builder-hint sentence.",

  "rect": {
    "anchor": "middle_center",  // named preset string OR [minX,minY,maxX,maxY] floats
    "pivot":  [0.5, 0.5],       // [x, y]
    "pos":    [0.0, 0.0],       // anchoredPosition [x, y] in canvas units
    "size":   [200.0, 200.0]    // sizeDelta [w, h] in canvas units
                                // For stretch anchors: pos=[0,0] size=[0,0] means full-fill.
  },

  "components": [ /* see Component Types */ ],

  "children": [ /* Nodes, index 0 = back (lowest z-order) */ ]
}
```

---

## Component Types

### Image
```jsonc
{
  "type": "Image",
  "sprite":          "Assets/UI/Gameplay/btn.png",  // null for solid-color generated images
  "color":           "#FFFFFF",    // omit if white
  "image_type":      "Simple",     // "Simple"|"Sliced"|"Filled"|"Tiled"
  "raycast":         false,        // true only for interactive roots (Buttons)
  "preserve_aspect": false,        // true for non-resizable icons when no nine_slice
  "fill_method":     null,         // "Horizontal"|"Vertical"|"Radial360"|... (Filled only)
  "fill_amount":     null          // float 0–1 (Filled only)
}
```

### TextMeshProUGUI
```jsonc
{
  "type":       "TextMeshProUGUI",
  "text":       "Label text",
  "font_size":  56,            // canvas units (already in canvas space, not source px)
  "font_style": "Bold",        // "Normal"|"Bold"|"Italic"|"Bold|Italic"
  "color":      "#FFFFFF",
  "alignment":  "Center",      // TMP TextAlignmentOptions name
  "overflow":   "Overflow",    // TMP TextOverflowModes; default "Overflow"
  "auto_size":  false
}
```

### Button
```jsonc
{
  "type":     "Button",
  "on_click": "intent_string"   // e.g. "navigate_main_menu", "open_shop", "booster_shuffle"
}
```

### CanvasGroup
```jsonc
{
  "type":           "CanvasGroup",
  "alpha":          1.0,
  "interactable":   true,
  "blocks_raycasts": true
}
```

### AspectRatioFitter
```jsonc
{
  "type":  "AspectRatioFitter",
  "mode":  "EnvelopeParent",   // AspectRatioFitter.AspectMode enum name
  "ratio": 1.0                 // sprite.width / sprite.height (native texture dims)
}
```

### HorizontalLayoutGroup / VerticalLayoutGroup
```jsonc
{
  "type":              "HorizontalLayoutGroup",
  "spacing":           20.0,
  "padding":           [0, 0, 0, 0],   // [left, right, top, bottom]
  "child_alignment":   "MiddleCenter",
  "control_child_size": [true, true],  // [width, height]
  "force_expand":      [false, false]  // [width, height]
}
```

### GridLayoutGroup
```jsonc
{
  "type":             "GridLayoutGroup",
  "cell_size":        [100.0, 100.0],
  "spacing":          [8.0, 8.0],
  "start_corner":     "UpperLeft",
  "start_axis":       "Horizontal",
  "child_alignment":  "UpperLeft",
  "constraint":       "FixedColumnCount",
  "constraint_count": 4
}
```

---

## `missing_assets[]` (inside `screens[i]`)

```jsonc
"missing_assets": [
  {
    "id":          "badge_bonus_heart",
    "description": "Small red heart badge for +N values.",
    "needed_by":   ["refill_bonus_badge"],
    "size":        [90, 90],
    "color_hint":  "#e63946",
    "priority":    "HIGH"
  }
]
```

---

## Background — `background_override` (variant use-case only)

Use **only** when a specific screen variant needs a different background than `meta.background`. Same shape as `meta.background`.

```jsonc
"background_override": {
  "type":   "full_screen_sprite",
  "sprite": "Assets/UI/Background/bg_coin_variant.png",
  "fit":    "preserve_aspect",
  "note":   "Coin variant uses gold-tinted background."
}
```

---

## Validation Checklist

- [ ] `meta.background.type` is one of the four enum values
- [ ] `meta.background.sprite` is non-null **only** when `type = "full_screen_sprite"`
- [ ] `meta.background.fit` is `"preserve_aspect"` or `"stretch"` when `type = "full_screen_sprite"`, else null
- [ ] Root node has no explicit `Canvas` component field — builder adds Canvas + CanvasScaler from `canvas` block
- [ ] Every `rect.anchor` is a valid named preset string or a 4-element float array
- [ ] Every `Image` component with `image_type = "Sliced"` is for a resizable container or button
- [ ] Every `Button` component appears on the SAME node as its `Image` (not on a child icon)
- [ ] `raycast: true` set ONLY on interactive roots (Button parents), false everywhere else
- [ ] Every non-null `sprite` path exists on disk OR has a `missing_assets` entry
- [ ] `children` order is back → front (index 0 = furthest back)
- [ ] All `pos` and `size` values are in canvas units, not source pixels
- [ ] `font_size` in `TextMeshProUGUI` is in canvas units

---

## Output Summary

```
✅ Saved: <output_path>

Background type  : <meta.background.type>
Background sprite: <meta.background.sprite or "none">
Screen id        : <screens[0].id>
Total nodes      : <N>   (root + all descendants)
Missing assets   : <N>
```

Compact node table:

| id | anchor | pos | size | components |
|----|--------|-----|------|------------|
| UI_Level11 | stretch | (0,0) | (0,0) | CanvasGroup |
| Background | stretch | (0,0) | (0,0) | Image, AspectRatioFitter |
| … | … | … | … | … |
