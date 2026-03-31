# Component Type Decision Tree

When a visual element could map to multiple Unity component types, use this decision tree to pick the correct one.

---

## Interactive Elements

### Button vs Clickable Image

```
Does the element trigger an action when tapped?
  YES -> Does it have visual press feedback (color change, scale, highlight)?
    YES -> Button + Image (raycast: true)
    NO  -> Is it text-only (no background panel)?
      YES -> Button + TextMeshProUGUI (raycast: true on text node)
      NO  -> Button + Image (raycast: true)
  NO  -> Image only (raycast: false)
```

### Toggle vs Button Group

```
Is there a group of options where the user selects one?
  YES -> Can only ONE be active at a time?
    YES -> Toggle + ToggleGroup (radio button pattern)
    NO  -> Can MULTIPLE be active simultaneously?
      YES -> Independent Toggle components (checkbox pattern)
      NO  -> Buttons (each triggers a separate action)
  NO  -> Is it a single on/off control?
    YES -> Toggle (standalone checkbox or switch)
    NO  -> Button
```

### Progress Bar vs Slider

```
Is the bar user-adjustable (drag handle visible)?
  YES -> Slider component (with handle, fill, and track children)
  NO  -> Is the fill level dynamic (changes at runtime)?
    YES -> Does it represent a bounded 0-1 value (health, XP, loading)?
      YES -> Image with image_type: "Filled" (fill_method: "Horizontal", fill_amount: current)
      NO  -> Image with image_type: "Filled" (the script controls fill_amount)
    NO  -> Plain Image (static decoration)
```

---

## Display Elements

### Star Ratings

```
Row of identical star-shaped icons:
  -> Each star: Image node
  -> Container: HorizontalLayoutGroup
  -> Note: "Filled vs empty state controlled at runtime."
  -> If exactly 3 or 5 stars: common rating pattern
  -> Each uses same sprite; filled/unfilled is a color or sprite swap
```

### Currency / Resource Display

```
Icon next to a number:
  -> Container node with HorizontalLayoutGroup (spacing: 8-16)
    -> Image child (icon, preserve_aspect: true, raycast: false)
    -> TextMeshProUGUI child (number, raycast: false)
  -> Note: "Dynamic text -- update via script. Add LocalizeUIText."
```

### Countdown Timer / Animated Counter

```
Text that shows a changing number or time:
  -> TextMeshProUGUI
  -> Note: "Dynamic text -- update via script. Add LocalizeUIText."
  -> Do NOT use Slider or progress bar unless there is also a visual bar
```

### Avatar / Profile Image

```
Is the image loaded from a URL or user-generated?
  YES -> RawImage (runtime texture assignment)
  NO  -> Is it a fixed sprite from the asset bundle?
    YES -> Image (preserve_aspect: true)
    NO  -> RawImage (safer default for unknown sources)
```

---

## Structural Elements

### Card / Panel with Rounded Corners

```
Does the panel have visible rounded corners or a border?
  YES -> Image with image_type: "Sliced" (9-slice sprite)
  NO  -> Is it a solid-color rectangle?
    YES -> Image with sprite: null, color: "<detected_color>"
    NO  -> Image with appropriate sprite
```

### Separator / Divider Line

```
Is there a thin horizontal or vertical line between sections?
  -> Image node
  -> size: [stretch_width, 2-4] for horizontal, [2-4, stretch_height] for vertical
  -> sprite: null, color: detected color (usually light gray)
  -> raycast: false
  -> anchor: "top_stretch" or "bottom_stretch" depending on position within parent
```

### Scroll Indicator / Dot Pagination

```
Row of small dots (one highlighted):
  -> Container with HorizontalLayoutGroup
  -> Each dot: Image node (size: 16-24 x 16-24)
  -> Active dot has different color or sprite
  -> Note: "Pagination indicator -- active dot controlled at runtime."
```

### Notification Badge / Counter Bubble

```
Small circle with a number, overlapping another element:
  -> Image child of the element it sits on (not a sibling)
  -> position: offset toward top-right corner of parent
  -> size: 36-56 x 36-56
  -> TextMeshProUGUI child for the number
  -> Note: "Badge visibility controlled at runtime."
```

---

## Completeness Check

After detecting all elements in Step 5, perform this check:

1. **Count visible elements**: Scan the screenshot and count every distinct visual element (icons, text labels, buttons, dividers, badges, background panels, decorative elements).
2. **Count tree nodes**: Count all leaf nodes and intermediate nodes with visual components in your detection tree.
3. **Compare**: If the screenshot count exceeds the tree count by more than 2:
   - Re-scan for commonly missed elements:
     - Thin separator lines between sections
     - Small dots or status indicators
     - Subtle shadows or decorative underlines
     - Badge/notification counters on icons
     - Partially transparent overlay elements
     - Scroll indicators or pagination dots
   - Add any missed elements to the tree
4. **Log**: Add a note to the root node if any elements were added in this pass: `"note": "Completeness check: added N missed elements."`
