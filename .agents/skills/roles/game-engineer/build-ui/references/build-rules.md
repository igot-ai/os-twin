# Build Rules -- Detection JSON to MCP Property Mapping

Detailed mapping from detection JSON fields to Unity MCP tool calls. Read this before building any node from detection JSON.

---

## Anchor Preset to RectTransform Properties

When converting a detection JSON `rect.anchor` preset string to MCP `gameobject-component-modify` properties on `RectTransform`:

| Preset | `anchorMin` | `anchorMax` | Default `pivot` |
|---|---|---|---|
| `"stretch"` | `[0, 0]` | `[1, 1]` | `[0.5, 0.5]` |
| `"top_stretch"` | `[0, 1]` | `[1, 1]` | `[0.5, 1]` |
| `"bottom_stretch"` | `[0, 0]` | `[1, 0]` | `[0.5, 0]` |
| `"middle_center"` | `[0.5, 0.5]` | `[0.5, 0.5]` | `[0.5, 0.5]` |
| `"middle_left"` | `[0, 0.5]` | `[0, 0.5]` | `[0, 0.5]` |
| `"middle_right"` | `[1, 0.5]` | `[1, 0.5]` | `[1, 0.5]` |
| `"top_left"` | `[0, 1]` | `[0, 1]` | `[0, 1]` |
| `"top_right"` | `[1, 1]` | `[1, 1]` | `[1, 1]` |
| `"top_center"` | `[0.5, 1]` | `[0.5, 1]` | `[0.5, 1]` |
| `"bottom_left"` | `[0, 0]` | `[0, 0]` | `[0, 0]` |
| `"bottom_right"` | `[1, 0]` | `[1, 0]` | `[1, 0]` |
| `"bottom_center"` | `[0.5, 0]` | `[0.5, 0]` | `[0.5, 0]` |
| Raw array `[minX, minY, maxX, maxY]` | `[minX, minY]` | `[maxX, maxY]` | Use detection JSON `pivot` |

### RectTransform MCP Call Pattern

```
gameobject-component-modify(
    target: { "instanceID": 0, "name": "<node.id>" },
    component_type: "UnityEngine.RectTransform",
    properties: {
        "m_AnchorMin": { "x": <anchorMin[0]>, "y": <anchorMin[1]> },
        "m_AnchorMax": { "x": <anchorMax[0]>, "y": <anchorMax[1]> },
        "m_Pivot": { "x": <pivot[0]>, "y": <pivot[1]> },
        "m_AnchoredPosition": { "x": <pos[0]>, "y": <pos[1]> },
        "m_SizeDelta": { "x": <size[0]>, "y": <size[1]> }
    }
)
```

For stretch anchors with `pos: [0,0]` and `size: [0,0]`, use `offsetMin` and `offsetMax` instead:
```
"m_OffsetMin": { "x": 0, "y": 0 },
"m_OffsetMax": { "x": 0, "y": 0 }
```

---

## Component Property Mapping

### Image

| Detection JSON Field | Unity Serialized Property | Notes |
|---|---|---|
| `sprite` | `m_Sprite` | Use `AssetObjectRef` with asset path |
| `color` | `m_Color` | Hex to RGBA: `{ "r": R, "g": G, "b": B, "a": A }` (0-1 range) |
| `image_type` | `m_Type` | `0`=Simple, `1`=Sliced, `2`=Tiled, `3`=Filled |
| `raycast` | `m_RaycastTarget` | `true` / `false` |
| `preserve_aspect` | `m_PreserveAspect` | `true` / `false` |
| `fill_method` | `m_FillMethod` | `0`=Horizontal, `1`=Vertical, `2`=Radial90, `3`=Radial180, `4`=Radial360 |
| `fill_amount` | `m_FillAmount` | float 0-1 |

**Image type mapping:**

| JSON `image_type` | `m_Type` value |
|---|---|
| `"Simple"` | `0` |
| `"Sliced"` | `1` |
| `"Tiled"` | `2` |
| `"Filled"` | `3` |

### RawImage

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `texture` | `m_Texture` |
| `color` | `m_Color` |
| `raycast` | `m_RaycastTarget` |
| `uv_rect` | `m_UVRect` -> `{ "x": uv[0], "y": uv[1], "width": uv[2], "height": uv[3] }` |

### TextMeshProUGUI

| Detection JSON Field | Unity Serialized Property | Notes |
|---|---|---|
| `text` | `m_text` | String content |
| `font_size` | `m_fontSize` | float, canvas units |
| `font_style` | `m_fontStyle` | `0`=Normal, `1`=Bold, `2`=Italic, `3`=Bold+Italic |
| `color` | `m_fontColor` | RGBA object (0-1) |
| `alignment` | `m_textAlignment` | See TMP alignment table below |
| `overflow` | `m_overflowMode` | `0`=Overflow, `1`=Ellipsis, `2`=Masking, `3`=Truncate, `5`=ScrollRect, `6`=Page |
| `auto_size` | `m_enableAutoSizing` | `true` / `false` |
| `raycast` | `m_RaycastTarget` | `true` / `false` |

**TMP TextAlignment mapping:**

| JSON `alignment` | `m_textAlignment` value |
|---|---|
| `"TopLeft"` | `257` |
| `"Top"` | `258` |
| `"TopRight"` | `260` |
| `"Left"` | `513` |
| `"Center"` | `514` |
| `"Right"` | `516` |
| `"BottomLeft"` | `1025` |
| `"Bottom"` | `1026` |
| `"BottomRight"` | `1028` |

**TMP fontStyle mapping:**

| JSON `font_style` | `m_fontStyle` value |
|---|---|
| `"Normal"` | `0` |
| `"Bold"` | `1` |
| `"Italic"` | `2` |
| `"Bold\|Italic"` | `3` |

### Button

| Detection JSON Field | Unity Serialized Property |
|---|---|
| (no direct properties) | Button uses `targetGraphic` auto-linked to Image on same GO |

The `on_click` field is informational only -- wiring is done in code, not here.

### Toggle

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `is_on` | `m_IsOn` |
| `toggle_group` | Wired in Step 5 (cross-reference) |

### Slider

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `min_value` | `m_MinValue` |
| `max_value` | `m_MaxValue` |
| `value` | `m_Value` |
| `whole_numbers` | `m_WholeNumbers` |
| `direction` | `m_Direction` -> `0`=LeftToRight, `1`=RightToLeft, `2`=BottomToTop, `3`=TopToBottom |

### ScrollRect

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `horizontal` | `m_Horizontal` |
| `vertical` | `m_Vertical` |
| `movement_type` | `m_MovementType` -> `0`=Unrestricted, `1`=Elastic, `2`=Clamped |
| `inertia` | `m_Inertia` |
| `viewport_id` | Wired in Step 5 (cross-reference to viewport GO) |
| `content_id` | Wired in Step 5 (cross-reference to content GO) |

### CanvasGroup

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `alpha` | `m_Alpha` |
| `interactable` | `m_Interactable` |
| `blocks_raycasts` | `m_BlocksRaycasts` |

### AspectRatioFitter

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `mode` | `m_AspectMode` -> `0`=None, `1`=WidthControlsHeight, `2`=HeightControlsWidth, `3`=FitInParent, `4`=EnvelopeParent |
| `ratio` | `m_AspectRatio` |

### HorizontalLayoutGroup / VerticalLayoutGroup

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `spacing` | `m_Spacing` |
| `padding` | `m_Padding` -> `{ "m_Left": p[0], "m_Right": p[1], "m_Top": p[2], "m_Bottom": p[3] }` |
| `child_alignment` | `m_ChildAlignment` -> see alignment enum below |
| `control_child_size` | `m_ChildControlWidth` / `m_ChildControlHeight` |
| `force_expand` | `m_ChildForceExpandWidth` / `m_ChildForceExpandHeight` |

**ChildAlignment enum:**

| JSON `child_alignment` | Value |
|---|---|
| `"UpperLeft"` | `0` |
| `"UpperCenter"` | `1` |
| `"UpperRight"` | `2` |
| `"MiddleLeft"` | `3` |
| `"MiddleCenter"` | `4` |
| `"MiddleRight"` | `5` |
| `"LowerLeft"` | `6` |
| `"LowerCenter"` | `7` |
| `"LowerRight"` | `8` |

### GridLayoutGroup

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `cell_size` | `m_CellSize` -> `{ "x": cs[0], "y": cs[1] }` |
| `spacing` | `m_Spacing` -> `{ "x": sp[0], "y": sp[1] }` |
| `start_corner` | `m_StartCorner` -> `0`=UpperLeft, `1`=UpperRight, `2`=LowerLeft, `3`=LowerRight |
| `start_axis` | `m_StartAxis` -> `0`=Horizontal, `1`=Vertical |
| `child_alignment` | `m_ChildAlignment` -> same enum as LayoutGroup |
| `constraint` | `m_Constraint` -> `0`=Flexible, `1`=FixedColumnCount, `2`=FixedRowCount |
| `constraint_count` | `m_ConstraintCount` |

### ContentSizeFitter

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `horizontal_fit` | `m_HorizontalFit` -> `0`=Unconstrained, `1`=MinSize, `2`=PreferredSize |
| `vertical_fit` | `m_VerticalFit` -> `0`=Unconstrained, `1`=MinSize, `2`=PreferredSize |

### LayoutElement

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `min_width` | `m_MinWidth` |
| `min_height` | `m_MinHeight` |
| `preferred_width` | `m_PreferredWidth` |
| `preferred_height` | `m_PreferredHeight` |
| `flexible_width` | `m_FlexibleWidth` |
| `flexible_height` | `m_FlexibleHeight` |
| `ignore_layout` | `m_IgnoreLayout` |

### Mask

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `show_mask_graphic` | `m_ShowMaskGraphic` |

### RectMask2D

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `softness` | `m_Softness` -> `{ "x": s[0], "y": s[1] }` |

### Shadow

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `effect_color` | `m_EffectColor` -> RGBA (0-1) |
| `effect_distance` | `m_EffectDistance` -> `{ "x": d[0], "y": d[1] }` |

### Outline

| Detection JSON Field | Unity Serialized Property |
|---|---|
| `effect_color` | `m_EffectColor` -> RGBA (0-1) |
| `effect_distance` | `m_EffectDistance` -> `{ "x": d[0], "y": d[1] }` |

---

## Color Conversion

Detection JSON uses hex strings (e.g., `"#FF5733"` or `"#FF573380"`). Convert to Unity RGBA:

```
#RRGGBB   -> { "r": R/255, "g": G/255, "b": B/255, "a": 1.0 }
#RRGGBBAA -> { "r": R/255, "g": G/255, "b": B/255, "a": A/255 }
```

---

## MCP Call Sequence (Per Node)

The correct order of MCP calls for each node in the detection tree:

```
1. gameobject-create         -> creates the GO, returns instanceID
2. gameobject-set-parent     -> sets parent (skip for root)
3. component-modify (RectTransform) -> position/size/anchors (RectTransform exists by default)
4. component-add (Layout*)   -> LayoutGroup, ContentSizeFitter, LayoutElement
5. component-add (Image/TMP) -> visual components
6. component-modify (Image/TMP) -> set visual properties
7. component-add (Button/Toggle/...) -> interaction components
8. component-modify (Button/Toggle/...) -> set interaction properties
9. component-add (Shadow/Outline) -> effects
10. component-modify (Shadow/Outline) -> set effect properties
11. component-add (CanvasGroup/AspectRatioFitter) -> utility
12. component-modify (CanvasGroup/AspectRatioFitter) -> set utility properties
```

Always create children AFTER the parent is fully configured. Process the tree depth-first: configure parent node completely, then recurse into children in array order (index 0 first = back-most).

---

## Sprite Reference Pattern

When a detection JSON component has a `sprite` field with a valid asset path:

```
gameobject-component-modify(
    target: { "instanceID": 0, "name": "<node.id>" },
    component_type: "UnityEngine.UI.Image",
    properties: {
        "m_Sprite": { "instanceID": 0, "assetPath": "<sprite_path>" }
    }
)
```

When the sprite is in `missing_assets[]` (not found on disk):

```
gameobject-component-modify(
    target: { "instanceID": 0, "name": "<node.id>" },
    component_type: "UnityEngine.UI.Image",
    properties: {
        "m_Sprite": null,
        "m_Color": { "r": <color_hint_r>, "g": <color_hint_g>, "b": <color_hint_b>, "a": 1.0 }
    }
)
```
