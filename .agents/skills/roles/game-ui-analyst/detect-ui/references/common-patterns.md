# Common Patterns -- UI Detection

Hierarchy rules, interactive component patterns, contrastive examples, and project conventions for producing correct detection JSON.

---

## Hierarchy Detection Rules

When inferring the parent-child structure from a flat 2D screenshot, apply these rules in order:

### HR1 -- Containment = child

If element A is fully contained within element B's bounding box and rendered on top (closer to the viewer), make A a child of B.

### HR2 -- Axis-aligned siblings with equal spacing = LayoutGroup

If 2+ siblings share obvious axis alignment (horizontal or vertical) with consistent spacing, wrap them in a container node with a `HorizontalLayoutGroup` or `VerticalLayoutGroup`.

### HR3 -- Grid = GridLayoutGroup

If 3+ elements form a grid pattern (consistent rows AND columns), wrap in a container with `GridLayoutGroup`. Set `constraint: "FixedColumnCount"` and count the columns.

### HR4 -- Interactive root = same node as Image

Buttons, toggles, and sliders always have their interaction component on the SAME node as the background Image. Icons and labels are children.

### HR5 -- Keep depth shallow

Hierarchy depth should not exceed 6 levels from canvas root. If you find yourself nesting deeper, consider flattening. Common structure: `root > card > section > element` (4 levels).

### HR6 -- Container inference

If a visual grouping has no visible background but logically groups elements (e.g., a row of icons without a panel behind them), create an invisible container node with no Image component. Use anchor `middle_center` and size it to fit its children.

### HR7 -- Partial containment (badges and overlapping decorations)

If element A partially overlaps element B (e.g., a notification badge sitting on the corner of an icon), make A a **child** of the element it is logically attached to, not a sibling. The badge "belongs to" the icon even though it extends beyond the icon's bounding box.

```
avatar_container           <- Image (avatar photo)
  badge_notification       <- Image (red circle, offset to top-right corner)
    lbl_badge_count        <- TextMeshProUGUI ("3")
```

Do NOT make the badge a sibling of the avatar -- it would lose its visual association when the avatar moves or is hidden.

### HR8 -- Floating elements (tooltips, FABs, toasts)

Elements that appear to float above all other content (tooltips, floating action buttons, toast notifications, snackbars) should be **siblings of the main content container**, not children of any specific content element.

```
root
  dim_overlay
  popup_card               <- main content
    [children]
  tooltip_arrow            <- floating, sibling of popup_card
  fab_button               <- floating action button, sibling
```

Exception: A close button ("X") that visually sits on a popup's corner is a **child** of the popup card, not a floating sibling. It moves with the popup.

### HR9 -- Scroll view content recognition

Recognize scrollable areas by these visual clues:
- **Repeated items**: 3+ elements with identical layout but different content
- **Clipped edges**: Items cut off at the container boundary
- **Scroll indicators**: Visible scrollbar track, dots, or pagination
- **Partial visibility**: Last item in the list is only partially visible

When detected, use the ScrollRect pattern from the "Interactive Component Patterns" section: ScrollRect > viewport (RectMask2D) > content (LayoutGroup + ContentSizeFitter).

Only create 2-3 template items in the content area. Add `note: "Items instantiated at runtime."` on the content node.

### HR10 -- Z-order resolution for overlapping siblings

When two elements overlap at the same apparent level and neither is clearly a child of the other:
1. **Higher opacity / brighter color** = on top (later sibling index)
2. **Interactive element** wins over decorative element (interactive renders on top)
3. **Smaller element** on top of larger element (badge on card, not card on badge)

Children array index determines z-order: index 0 = back, last index = front.

---

## Hierarchy Verification (Post-Detection)

After building the full node tree, walk it and verify:

1. **Containment**: Every child's bounding box should be within its parent's bounding box, with these exceptions:
   - Badge/notification dots (HR7) may extend beyond parent
   - Shadow/outline effects may bleed outside
   - Elements with `note` mentioning "overflow" or "partially visible"
2. **No orphans**: Every detected visual element has a parent (except root)
3. **Depth limit**: No path from root exceeds 6 levels (HR5)
4. **LayoutGroup consistency**: All children of a LayoutGroup node use `anchor: "middle_center"` (HR2 + contrastive example 6)

---

## Standard Hierarchy Alignment

The project's `unity-ui` skill defines this mandatory screen structure:

```
UI_{ScreenName}        (Canvas, CanvasScaler, GraphicRaycaster, CanvasGroup, UIAnimationBehaviour)
  Background           (Image)
    Anchors
      LeftAnchor       (left-side elements)
      RightAnchor      (right-side elements)
      UpperAnchor      (top bar, title)
      LowerAnchor      (bottom nav, action buttons)
      PopupAnchor      (centered popup content)
```

For popup screens, the common output hierarchy is:
```
root                   (CanvasGroup -- the screen root)
  dim_overlay          (Image with #00000080 color, stretch anchor, raycast:true)
  popup_card           (Image with Sliced bg, middle_center anchor)
    [title, content, buttons as children]
```

---

## Interactive Component Patterns

### Button with icon and label

```
btn_close                  <- Image(btn_bg.png, Sliced, raycast:true) + Button
  icon_close               <- Image(ic_close.png, raycast:false, preserve_aspect:true)
  lbl_close                <- TextMeshProUGUI("Close", raycast:false)
```

The `Button` component goes on the same node as the background `Image`. The icon and label are separate children. Only the parent Image has `raycast: true`.

### Icon-only button (no label)

```
btn_settings               <- Image(btn_circle.png, raycast:true) + Button
  icon_gear                <- Image(ic_gear.png, raycast:false, preserve_aspect:true)
```

### Toggle (checkbox)

```
toggle_sound               <- Toggle(is_on:true) + Image(bg_toggle.png, raycast:true)
  checkmark                <- Image(ic_check.png, raycast:false)
```

The `Toggle` component references the `checkmark` child as its graphic. The `checkmark` node is shown/hidden by Toggle.

### Toggle group (radio buttons)

```
filter_row                 <- HorizontalLayoutGroup
  toggle_all               <- Toggle(toggle_group:"filter_row", is_on:true) + Image(bg_tab.png, raycast:true)
    lbl_all                <- TextMeshProUGUI("All", raycast:false)
  toggle_coins             <- Toggle(toggle_group:"filter_row", is_on:false) + Image(bg_tab.png, raycast:true)
    lbl_coins              <- TextMeshProUGUI("Coins", raycast:false)
```

### ScrollView

```
scroll_view                <- ScrollRect(viewport_id:"viewport", content_id:"content") + Image(optional bg)
  viewport                 <- RectMask2D, anchor:stretch, size:[0,0]
    content                <- VerticalLayoutGroup + ContentSizeFitter(vertical_fit:"PreferredSize")
      [dynamic items]      <- instantiated at runtime
```

The viewport clips children using `RectMask2D` (preferred) or `Mask + Image`. The content container uses `ContentSizeFitter` to grow as items are added. `ScrollRect.viewport_id` and `content_id` reference the child node IDs.

### Slider

```
slider_volume              <- Slider(direction:"LeftToRight", min:0, max:1, value:0.5)
  bg_track                 <- Image(slider_track.png, raycast:false), anchor:stretch
  fill_area                <- anchor:stretch, size:[0,0]
    fill                   <- Image(slider_fill.png, raycast:false)
  handle_area              <- anchor:stretch, size:[0,0]
    handle                 <- Image(slider_handle.png, raycast:true)
```

### InputField (TMP)

```
input_name                 <- TMP_InputField(content_type:"Standard", placeholder_text:"Enter name...")
  text_area                <- RectMask2D, anchor:stretch
    placeholder            <- TextMeshProUGUI("Enter name...", color:#999999, raycast:false)
    text                   <- TextMeshProUGUI("", raycast:false)
```

---

## Safe Area Handling

If the screenshot shows a device with a notch, Dynamic Island, rounded corners, or system UI overlay:

1. Add a `safe_area` container node as a child of the root.
2. Set `note: "Apply SafeArea inset (ScreenSafeArea or project equivalent)."` on the container.
3. Place popup content INSIDE the safe_area node.
4. The dim overlay should STILL be outside (beneath) safe_area -- it covers the full screen.

```
root
  dim_overlay              <- stretch, full screen
  safe_area                <- note: "Apply SafeArea inset."
    popup_card             <- content inside safe area
```

---

## Canvas Splitting Hints

When detecting elements, consider whether they are static or dynamic. Add hints in the `note` field:

| Element type | Hint |
|---|---|
| Background, decorative borders | `"Static -- can use separate static canvas."` |
| Score counters, timers, health bars | `"Dynamic -- updates frequently. Separate canvas recommended."` |
| Buttons, popups (change on interaction only) | No hint needed (default behavior) |

This helps the builder apply canvas splitting for mobile performance (see `unity-ui-perf`).

---

## Contrastive Examples (Good vs Bad)

### 1. Button component placement

**GOOD:** Button component on the root node with background Image.
```json
{ "id": "btn_play", "components": [
    { "type": "Image", "sprite": "btn_bg.png", "raycast": true },
    { "type": "Button", "on_click": "start_game" }
  ],
  "children": [
    { "id": "icon_play", "components": [{ "type": "Image", "sprite": "ic_play.png", "raycast": false }] }
  ]
}
```

**BAD:** Button on the icon child -- breaks click area.
```json
{ "id": "btn_play", "components": [
    { "type": "Image", "sprite": "btn_bg.png", "raycast": false }
  ],
  "children": [
    { "id": "icon_play", "components": [
      { "type": "Image", "sprite": "ic_play.png", "raycast": true },
      { "type": "Button", "on_click": "start_game" }
    ]}
  ]
}
```

### 2. Anchor selection for centered popups

**GOOD:** `middle_center` with explicit size.
```json
{ "id": "popup_card", "rect": { "anchor": "middle_center", "pos": [0, 0], "size": [900, 1100] } }
```

**BAD:** `stretch` with margins -- popup resizes on different devices.
```json
{ "id": "popup_card", "rect": { "anchor": "stretch", "pos": [0, 0], "size": [-180, -820] } }
```

### 3. Zero-size on non-stretch anchor

**GOOD:** Stretch anchor with `[0,0]` = full-fill parent.
```json
{ "rect": { "anchor": "stretch", "pos": [0, 0], "size": [0, 0] } }
```

**BAD:** `middle_center` with `[0,0]` = invisible zero-size element.
```json
{ "rect": { "anchor": "middle_center", "pos": [0, 0], "size": [0, 0] } }
```

### 4. Raycast target assignment

**GOOD:** Only the button's Image has raycast.
```json
{ "id": "btn_next", "components": [
    { "type": "Image", "raycast": true },
    { "type": "Button" }
  ],
  "children": [
    { "id": "lbl_next", "components": [{ "type": "TextMeshProUGUI", "raycast": false }] }
  ]
}
```

**BAD:** Every element has raycast -- wastes mobile CPU.
```json
{ "id": "btn_next", "components": [
    { "type": "Image", "raycast": true },
    { "type": "Button" }
  ],
  "children": [
    { "id": "lbl_next", "components": [{ "type": "TextMeshProUGUI", "raycast": true }] }
  ]
}
```

### 5. Font size in wrong units

If source image is 750x1334 and canvas is 1080x1920:

**GOOD:** Converted to canvas units: `font_size: 81` (56px * 1080/750 = 80.64 -> 81)
```json
{ "type": "TextMeshProUGUI", "font_size": 81 }
```

**BAD:** Raw source pixels used directly.
```json
{ "type": "TextMeshProUGUI", "font_size": 56 }
```

### 6. LayoutGroup children anchors

**GOOD:** Children inside a LayoutGroup use `middle_center` (layout overrides at runtime).
```json
{ "id": "star_1", "rect": { "anchor": "middle_center", "pos": [0, 0], "size": [120, 120] } }
```

**BAD:** Children use custom anchors that fight with the LayoutGroup.
```json
{ "id": "star_1", "rect": { "anchor": "top_left", "pos": [10, -10], "size": [120, 120] } }
```
