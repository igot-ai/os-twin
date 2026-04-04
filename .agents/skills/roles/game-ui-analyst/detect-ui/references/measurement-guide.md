# Measurement Guide -- Canvas Unit Calibration & Validation

Accurate measurement is the foundation of usable detection JSON. This guide prevents the three most common measurement errors: Retina misdetection, raw-pixel leakage, and proportion drift.

---

## Retina Detection Checklist

Before computing `to_canvas`, determine if the screenshot is a Retina capture.

| Source Width | Likely Device Class | Scale Factor | Logical Resolution |
|---|---|---|---|
| 750 | iPhone 6/7/8 | @2x | 375 x 667 |
| 828 | iPhone XR/11 | @2x | 414 x 896 |
| 1080 | iPhone 12/13/14 | @3x | 390 x 844 |
| 1125 | iPhone X/XS/11 Pro | @3x | 375 x 812 |
| 1170 | iPhone 14/15 Pro | @3x | 390 x 844 |
| 1179 | iPhone 15 Pro | @3x | 393 x 852 |
| 1242 | iPhone 6+/7+/8+ | @3x | 414 x 736 |
| 1284 | iPhone 12/13/14 Pro Max | @3x | 428 x 926 |
| 1290 | iPhone 15 Pro Max | @3x | 430 x 932 |
| > 1500 wide | Tablet or desktop | @1x or @2x | Check aspect ratio |

**Decision tree:**

```
IF user states the scale factor explicitly
  -> Use that factor

ELSE IF source width matches a known @3x device (1080, 1125, 1170, 1179, 1242, 1284, 1290)
  -> Scale factor = 3

ELSE IF source width matches a known @2x device (750, 828)
  -> Scale factor = 2

ELSE IF source width > 1200 AND aspect ratio is ~9:19.5 (mobile portrait)
  -> Likely @3x, scale factor = 3

ELSE
  -> Scale factor = 1 (no Retina correction)
```

After determining scale factor:
```
logical_w = source_w / scale_factor
logical_h = source_h / scale_factor
scale_x = canvas_w / logical_w
scale_y = canvas_h / logical_h
```

---

## Common Mobile Reference Sizes (Canvas Units, 1080x1920)

Use this table to sanity-check detected element sizes. If a measured value falls far outside these ranges, re-measure.

### Interactive Elements

| Element | Width | Height | Notes |
|---|---|---|---|
| Primary action button | 500-800 | 100-140 | Full-width CTA |
| Secondary button | 300-500 | 80-120 | Smaller action |
| Icon button (round) | 80-120 | 80-120 | Close, settings, back |
| Tab bar button | 200-300 | 80-100 | Filter tabs |
| Toggle switch | 100-160 | 60-80 | On/off control |

### Text

| Element | font_size | Notes |
|---|---|---|
| Screen title | 60-80 | Large, bold |
| Section heading | 44-56 | Medium-bold |
| Body text | 36-44 | Regular weight |
| Button label | 36-48 | Bold, centered |
| Caption / hint | 28-36 | Small, lighter color |
| Badge / counter | 24-32 | Very small |

### Layout

| Element | Typical Size | Notes |
|---|---|---|
| Popup card | 880-1000 x 800-1400 | ~80-92% screen width |
| Top bar | stretch x 100-140 | Full-width header |
| Bottom bar | stretch x 120-160 | Bottom navigation |
| List item row | stretch x 120-180 | Scrollable list entry |
| Icon (in list) | 80-120 x 80-120 | Item or currency icon |
| Avatar | 120-200 x 120-200 | Profile picture |
| Star (rating) | 80-120 x 80-120 | Star icons in row |

### Spacing

| Context | Typical Value | Notes |
|---|---|---|
| Card padding | 30-50 | Edge to content |
| Element spacing (LayoutGroup) | 16-32 | Between siblings |
| Section spacing | 40-60 | Between groups |
| Button row spacing | 20-40 | Between buttons |

---

## Rounding Rules

- `pos` and `size`: Round to nearest integer. Example: 80.6 -> 81.
- `font_size`: Round to nearest even number. Example: 43.2 -> 44, 37.8 -> 38.
- `pivot`: Keep two decimal places. Example: [0.5, 0.5].
- `to_canvas` scale factors: Keep three decimal places. Example: 1.439.

---

## Sanity Checks (Mandatory After Step 5)

After detecting all elements, run these proportion checks:

### Check 1 -- Popup width ratio

For popup screens, the card width should be 80-92% of canvas width:
```
ratio = popup_card.size.w / canvas.w
EXPECTED: 0.80 <= ratio <= 0.92
IF outside: re-measure the popup card edges
```

### Check 2 -- LayoutGroup consistency

For any detected LayoutGroup, verify children sum:
```
horizontal: sum(child.size.w) + (N-1) * spacing ~= parent.size.w - 2*padding
vertical:   sum(child.size.h) + (N-1) * spacing ~= parent.size.h - 2*padding
TOLERANCE: +/- 20 canvas units
IF outside: re-measure children or adjust spacing estimate
```

### Check 3 -- Font size plausibility

Compare every `font_size` against the reference table above:
```
IF font_size < 20 -> probably raw pixels, not canvas units
IF font_size > 100 -> probably double-scaled (Retina not divided)
```

### Check 4 -- Element overlap check

No two sibling elements should significantly overlap (>30% area overlap) unless one is a decorative overlay. If overlap detected, one is likely a child, not a sibling.

---

## Contrastive Examples

### Example 1 -- Retina trap

Source: iPhone 14 Pro screenshot, 1170 x 2532 pixels.

**WRONG** (no Retina correction):
```json
"source_resolution": { "w": 1170, "h": 2532 },
"to_canvas": { "scale_x": 0.923, "scale_y": 0.758 }
```
This produces scale factors < 1, which will shrink all measurements. A 200px button becomes 185 canvas units instead of the correct ~554.

**CORRECT** (divide by @3x first):
```json
"source_resolution": { "w": 390, "h": 844 },
"to_canvas": { "scale_x": 2.769, "scale_y": 2.275 }
```

### Example 2 -- Text bounding box vs visual bounds

A title text "LEVEL COMPLETE" appears to span 400px in source. But the TextMeshProUGUI bounding box includes padding above/below for ascenders/descenders. The correct measurement is the full text area including that padding, not just the visible ink.

**Tip**: Measure the full height of the text container (including line spacing), not just the visible character height. For text, width should be generous enough to avoid truncation.

### Example 3 -- Sub-pixel rounding accumulation

Three stars in a row, each approximately 83.3px in source (250px total / 3):
```
canvas_unit = 83.3 * 2.769 = 230.7 -> 231 each
3 * 231 = 693 canvas units for the row
```

But the actual row container is 700 canvas units wide with 20px spacing:
```
Expected: 3 * star_w + 2 * 20 = 700
star_w = (700 - 40) / 3 = 220
```

**Use the LayoutGroup cross-check** (Check 2) to catch this. The individual star should be 220, not 231.
