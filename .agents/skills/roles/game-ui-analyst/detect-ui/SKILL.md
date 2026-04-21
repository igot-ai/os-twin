---
name: detect-ui
description: Analyse a UI reference screenshot and generate a _detection.json (schema 5.0.0). Output includes both a nested canvas-native tree for building GameObjects AND a flat objects[] array for animation-analyzer. Covers all component types (Image, Button, ScrollRect, Toggle, Slider, InputField, Mask, LayoutGroups, etc.), background classification, hierarchy detection, and sprite resolution. Triggers on 'analyse UI', 'detect UI', 'UI detection', 'generate detection JSON', 'screenshot to UI', 'parse UI screenshot', 'identify UI elements', 'UI structure from image'. Use this skill whenever the user has a screenshot of a UI screen and wants to extract structured detection data from it -- even if they just say 'what elements are in this screenshot' or 'break down this UI'."
argument-hint: <detection_image> [output_json_path] [real_bg_asset_path]
tags: []
: experimental
---
**Quick Start:** View screenshot -> classify background -> measure resolution + compute canvas scale -> detect every visible UI element (back-to-front) -> build node tree -> generate flat `objects[]` array -> validate -> emit schema 5.0.0 JSON -> hand off to builder / animation-analyzer.

---

## Inputs

Parse `$ARGUMENTS` as:
- `$0` -- detection image path (required)
- `$1` -- if ends with `.json` -> output path; if ends with `.png/.jpg` -> real background asset path
- `$2` -- output path (only when `$1` was used as background path)

Default output path: replace `$0` extension with `_detection.json`.

---

## Step 1 -- Classify the Background

Determine `meta.background` before any measurement.

```
IF user supplied $2 (explicit background asset)
  -> type = "full_screen_sprite", sprite = $2

ELSE IF $0 shows gameplay behind the popup
  IF there is a semi-transparent dark overlay between gameplay and popup
    -> type = "dim_overlay"
  ELSE (gameplay directly visible, no overlay)
    -> type = "gameplay_scene_passthrough"

ELSE IF $0 shows a RenderTexture / ScreenSpaceCamera setup (3D content behind UI)
  -> type = "render_texture"

ELSE IF $0 looks like a standalone background image (check Glob "Assets/UI/Background/*.png")
  -> type = "full_screen_sprite", sprite = best match from Glob

ELSE (just a solid colour or transparent)
  -> type = "none"
```

| `type` | Builder action |
|---|---|
| `"full_screen_sprite"` | `Background` GO -> stretch -> `Image(sprite)` + `AspectRatioFitter(EnvelopeParent)` |
| `"dim_overlay"` | `DimOverlay` GO -> stretch -> `Image(#00000080)`, `raycast: true` |
| `"gameplay_scene_passthrough"` | Comment only -- nothing created behind the popup |
| `"render_texture"` | Comment only -- `canvas.renderMode = ScreenSpaceCamera` note |
| `"none"` | Nothing |

---

## Step 2 -- Read the Image and Determine Resolution

View `$0`. Record:
- **Source resolution**: actual pixel dimensions of the image (e.g., 750 x 1334)
- **Every visible layer** from back to front -- this becomes the detection order

If the image appears to be a Retina screenshot (@2x / @3x), divide pixel dimensions by the scale factor to get logical resolution before computing canvas conversion.

---

## Step 3 -- Compute Canvas Conversion

**Reference canvas**: 1080 x 1920 (project default, `ScaleWithScreenSize`, Match 0.5).

First, check for Retina scaling using the decision tree in `references/measurement-guide.md`. If the source is @2x or @3x, divide pixel dimensions by the scale factor to get logical resolution.

Compute `meta.to_canvas`:
```
scale_x = canvas_w / logical_w    (e.g., 1080 / 390 = 2.769 for @3x iPhone 14 Pro)
scale_y = canvas_h / logical_h    (e.g., 1920 / 844 = 2.275)
```

**All measurements from this point are in canvas units, not source pixels.**

To convert a measurement from source pixels to canvas units:
```
canvas_value = source_pixels * scale_factor
```

Apply rounding rules from `references/measurement-guide.md`: integers for pos/size, even numbers for font_size.

### Mandatory Sanity Check (after Step 5)

After detecting all elements, run the 4 sanity checks from `references/measurement-guide.md`:
1. Popup width ratio (80-92% of canvas width)
2. LayoutGroup children sum consistency
3. Font size plausibility (not raw pixels, not double-scaled)
4. Sibling overlap check

---

## Step 4 -- Detect Canvas Settings

Identify the CanvasScaler reference resolution (default **1080 x 1920** if unknown). Fill the `canvas` block.

---

## Step 5 -- Detect All UI Objects, Back to Front

For each visible UI object (skip the scene background -- that's in `meta.background`):

1. **Measure** position and size in canvas units (using the scale factors from Step 3).
2. **Pick anchor**: Use an Anchor Preset name or raw `[minX, minY, maxX, maxY]` array (see `references/schema.md` for the preset table).
3. **Find sprite**: `Glob "Assets/UI/**/*.png"`. Add to `missing_assets` if absent. Do NOT invent paths.
4. **List components**: Use typed objects from `references/schema.md`. Include `unity_type_name` on each.
5. **Write a `note`**: one builder-hint sentence. Include "Add LocalizeUIText." on any text node.

### Hierarchy Detection

Apply hierarchy rules when deciding parent-child relationships:
- Fully contained element on top of another -> make it a child (HR1)
- Axis-aligned siblings with equal spacing -> wrap in LayoutGroup container (HR2)
- Grid pattern -> GridLayoutGroup (HR3)
- Interactive component always on same node as background Image (HR4)
- Max 6 levels deep (HR5)
- Partial containment (badges) -> child of attached element (HR7)
- Floating elements (tooltips, FABs) -> siblings of main content (HR8)
- Repeated clipped items -> ScrollRect pattern (HR9)
- Z-order conflicts -> higher opacity/brighter = on top (HR10)

For complete hierarchy rules and interactive component patterns (Button, Toggle, ScrollView, Slider, InputField), read `references/common-patterns.md`.

### Component Type Selection

For ambiguous elements (e.g., button vs clickable image, toggle vs button group, progress bar vs slider), consult the decision tree in `references/component-decision-tree.md`.

### Completeness Check

After detecting all elements, count visible elements in the screenshot vs nodes in the tree. If the mismatch exceeds 2, re-scan for commonly missed elements (thin dividers, dots, badges, shadows, scroll indicators). See the completeness check section in `references/component-decision-tree.md`.

---

## Step 6 -- Fill `missing_assets[]`

For every sprite referenced in a component but not found via Glob, add one entry:

```jsonc
{
  "id": "asset_snake_case_id",
  "description": "Brief description of what the asset looks like.",
  "needed_by": ["node_id_1", "node_id_2"],   // which nodes need this
  "size": [90, 90],                            // canvas units (NOT source pixels)
  "color_hint": "#e63946",
  "priority": "HIGH"                           // "HIGH"|"MEDIUM"|"LOW"
}
```

---

## Step 7 -- Generate Flat `objects[]` Array

Traverse the node tree and produce a flat list for `screens[].objects[]`. This is consumed by `unity-animation-analyzer` for track-to-object matching.

For each meaningful node (skip pure container nodes with no components):

```jsonc
{
  "id": "<node.id>",
  "category": "<derived from primary component>",
  "bounding_box": [x1, y1, x2, y2],            // source pixel coordinates
  "normalized_bbox": [x1_n, y1_n, x2_n, y2_n], // 0-1 normalized
  "canvas_position": { "x": <pos_x>, "y": <pos_y> },
  "canvas_size": { "w": <size_w>, "h": <size_h> },
  "tree_path": "root/parent/node_id"
}
```

Category derivation and bounding box computation formulas are in `references/schema.md` (Flat objects[] section).

---

## Step 8 -- Validate

Run the validation checklist from `references/schema.md`. Key checks:

- [ ] `"schema": "5.0.0"` at root
- [ ] `to_canvas` factors match `canvas / source_resolution`
- [ ] No duplicate `id` values in the tree
- [ ] Button + Image on same node, `raycast: true` only on interactive roots
- [ ] LayoutGroup children use `anchor: "middle_center"`
- [ ] `Image.preserve_aspect` and `AspectRatioFitter` NOT both on same node
- [ ] Every sprite path exists on disk OR has a `missing_assets` entry
- [ ] Every `missing_assets[].needed_by` ID exists in the tree
- [ ] `objects[]` populated with correct bounding boxes and categories
- [ ] All `pos`, `size`, `font_size` values are in canvas units

---

## Step 9 -- Write the JSON and Print Summary

Write the JSON with `"schema": "5.0.0"`.

Output summary format:
```
Saved: <output_path>

Background type  : <meta.background.type>
Background sprite: <meta.background.sprite or "none">
Screen id        : <screens[0].id>
Screen type      : <screens[0].type>
Total tree nodes : <N>  (root + all descendants)
Flat objects     : <N>
Missing assets   : <N>
```

Then print a compact node table:

| id | anchor | pos | size | components |
|----|--------|-----|------|------------|
| root | stretch | (0,0) | (0,0) | CanvasGroup |
| dim_overlay | stretch | (0,0) | (0,0) | Image |
| ... | ... | ... | ... | ... |

---

## Failure Modes

| Symptom | Action |
|---|---|
| Blurry / compressed screenshot | Estimate element bounds from dominant shapes. Add `"note": "Bounds approximate -- low-quality source."` on affected nodes. |
| Sprite Glob returns 0 results | Add ALL detected sprites to `missing_assets`. Do NOT invent paths. |
| Overlapping semi-transparent popups (two UI layers) | Emit two separate screen entries in `screens[]`. |
| Non-standard aspect ratio (tablet, foldable) | Record actual `source_resolution`. Adjust `to_canvas` scale factors accordingly. |
| Canvas resolution unknown | Default to 1080x1920. Add `"note": "Canvas resolution defaulted."` in root. |
| Retina @2x/@3x screenshot | Divide source image dimensions by scale factor before computing `to_canvas`. |
| Elements cut off at edges | Include partial elements with estimated full size. Add `"note": "Partially visible -- size estimated."`. |

---

## Output JSON Structure (schema 5.0.0)

The root structure is documented in `references/schema.md`. Key sections:
- `meta` -- source image info, `to_canvas` conversion factors, background classification
- `canvas` -- CanvasScaler settings (1080x1920 default)
- `screens[]` -- one entry per detected screen, containing:
  - `root` -- nested node tree (recursive, for builder)
  - `objects[]` -- flat array (for animation-analyzer)
  - `missing_assets[]` -- sprites not found on disk

For the complete field reference, enum tables, and validation checklist, read `references/schema.md`.
For a complete valid sample output, read `references/example-output.json`.

### Schema changes in v5.0.0 (vs 4.0.0)

- Added flat `screens[].objects[]` array for animation-analyzer compatibility
- Added `meta.to_canvas` conversion factors
- Added `dim_overlay` background type
- Added 12 new component types: ScrollRect, Mask, RectMask2D, ContentSizeFitter, LayoutElement, Toggle, Slider, TMP_InputField, TMP_Dropdown, Shadow, Outline, RawImage
- Added `unity_type_name` field on all component schemas
- Defined closed `screens[].type` enum
- Clarified `missing_assets[].size` units as canvas units
- Added `raycast` field to `TextMeshProUGUI`

---

## Handoff

### To unity-ui-builder (recommended next step)

After generating the detection JSON, ask the user if they want to build it as a Unity prefab. If yes, invoke `unity-ui-builder` with the detection JSON path as input.

The `root` tree is consumed directly to create GameObjects:
1. Walk tree depth-first
2. `gameobject-create` for each node (name = `id`)
3. `gameobject-component-add` with `unity_type_name` from each component
4. `gameobject-component-modify` to set properties
5. `gameobject-set-parent` to establish hierarchy

See `unity-ui-builder` skill for the complete build workflow.

### To unity-animation-analyzer

The `objects[]` flat array provides everything the animation-analyzer needs:
- `id` -- semantic object identifier
- `category` -- maps to `source_category` in animation clips JSON
- `bounding_box` -- used for IoU matching with CV tracks
- `normalized_bbox` -- used for proximity matching
- `canvas_position` -- used for animation keyframe derivation

The `to_canvas` factors enable pixel-to-canvas coordinate conversion.

---

## References

| File | Content | When to read |
|---|---|---|
| `references/schema.md` | Full JSON schema v5.0.0, all component types, enum tables, validation checklist | When building output JSON |
| `references/example-output.json` | Complete valid sample output (level-complete popup) | First time using this skill, or as a template |
| `references/common-patterns.md` | Hierarchy rules, interactive patterns (Button, Toggle, ScrollView, Slider, InputField), contrastive Good/Bad examples, safe area guidance | When detecting complex UI elements |

---

## Related Skills

| Need | Skill                                                            |
|---|------------------------------------------------------------------|
| Build Unity GameObjects from this JSON | `develop-unity-ui` (gameobject-create, gameobject-component-add) |
| uGUI hierarchy conventions, mandatory components | `unity-ui`                                                       |
| Animate detected elements | `unity-ui-animation` (PrimeTween, Animator)                      |
| Extract animation data from video | `detec-anim` (consumes `objects[]`)                              |
| Mobile performance optimization | `unity-ui-perf` (raycast, canvas splitting)                      |
| Visual effects (grayscale, blur, dissolve) | `unity-ui-effect` (UIEffect component)                           |
| Localization for text elements | `unity-ui-localization` (LocalizeUIText)                         |

---

## Project Conventions

- **Canvas**: 1080x1920, ScaleWithScreenSize, Match 0.5, ScreenSpaceOverlay
- **Namespaces**: All game code under `Game.*`
- **Mandatory components**: `LocalizeUIText` on every TMP text, `UIAnimationBehaviour` on animated screen roots, `UIParticle` on ParticleSystems in Canvas
- **Performance**: Disable `raycast` on non-interactive elements, prefer `RectMask2D` over `Mask` for scroll clipping
- **No UI Toolkit**: uGUI Prefabs only

