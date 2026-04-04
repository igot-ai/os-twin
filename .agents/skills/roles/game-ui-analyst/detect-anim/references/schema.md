# Animation Clips JSON Schema — v6.1.0

This is the reference for the output JSON produced by `unity-animation-analyzer`.
The builder skill (`unity-animation-builder`) consumes this format.

---

## Root Structure

```jsonc
{
  "schema": "6.1.0",
  "meta": { ... },
  "easing_library": { ... },
  "animated_objects": [ ... ],
  "animation_sequences": [ ... ],
  "scene_wiring": { ... },
  "track_matching": { ... }
}
```

---

## `meta`

| Field | Type | Required | Description |
|---|---|---|---|
| `scene` | string | Yes | Active scene name. If MCP unavailable, use `"UNKNOWN"` |
| `scene_path` | string | Yes | Scene asset path. If MCP unavailable, use `"UNKNOWN"` |
| `source_video` | string | Yes | Path to the source video file |
| `detection_json` | string | Yes | Path to the detection JSON used |
| `canvas` | object | Yes | Canvas configuration (see below) |
| `generated_at` | string | Yes | ISO 8601 timestamp |
| `phase1_quality` | string | No | `"normal"`, `"no_tracks"`, `"high_noise"`, `"precomputed"` |
| `scene_validation` | string | No | `"validated"`, `"partial"`, `"skipped"` |

### `canvas` object

```json
{
  "w": 1080,
  "h": 1920,
  "scale_mode": "ScaleWithScreenSize",
  "match": 0.5,
  "render_mode": "ScreenSpaceOverlay"
}
```

---

## `easing_library`

Shared easing functions. Each entry maps a JSON easing name to formulas and PrimeTween enum.

```json
{
  "linear":      { "formula": "t",                           "csharp": "t",                                                              "prime_tween_ease": "Ease.Linear" },
  "ease_in":     { "formula": "t^2",                         "csharp": "t * t",                                                          "prime_tween_ease": "Ease.InQuad" },
  "ease_out":    { "formula": "1 - (1-t)^2",                 "csharp": "1f - (1f - t) * (1f - t)",                                       "prime_tween_ease": "Ease.OutQuad" },
  "ease_in_out": { "formula": "t<0.5 ? 2t^2 : 1-(−2t+2)^2/2","csharp": "t < 0.5f ? 2f * t * t : 1f - Mathf.Pow(-2f * t + 2f, 2f) / 2f","prime_tween_ease": "Ease.InOutQuad" },
  "spring":      { "formula": "overshoot then settle",       "csharp": "<custom per-object>",                                            "prime_tween_ease": "Ease.OutBack" },
  "constant":    { "formula": "step function",               "csharp": "1f",                                                             "prime_tween_ease": null }
}
```

---

## `animated_objects[]`

Each entry represents one semantic object that is animated (or inferred to be present).

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier (from detection JSON or generated) |
| `display_name` | string | Yes | Human-readable name |
| `source_category` | string | Yes | Raw category from detection JSON (e.g., `"UI/Button"`) |
| `object_category` | string | Yes | Animation behavior role (see enum table below) |
| `motion_type` | string | Yes | Physical motion observed (see enum table) |
| `animation_type` | string | Yes | Semantic animation intent (see enum table) |
| `trigger` | string | Yes | What starts this animation (see enum table) |
| `description` | string | Yes | Short description of the animation |
| `target` | object | Yes | Scene target info (see below) |
| `tracks[]` | array | Yes | Keyframe tracks (see below) |
| `total_duration_sec` | float | Yes | Must equal last keyframe `time_sec` in longest track |
| `motion_summary` | string | Yes | **Detailed** explanation of visible motion (multi-sentence) |
| `relationships[]` | array | Yes | Relationships to other objects (can be `[]`) |
| `source_evidence` | object | Yes | Match evidence (see below) |

### `target` object

| Field | Type | Description |
|---|---|---|
| `path` | string | Scene hierarchy path (e.g., `"UI_Root/PopupCard/BtnRefill"`) |
| `path_validated` | boolean | `true` if verified via MCP, `false` if best-guess |
| `apply_to` | string | `"single"` or `"group"` |
| `required_components` | string[] | Unity components needed |
| `initial_state` | object | Starting values (scale, alpha, position) |

### `tracks[]` entries

| Field | Type | Description |
|---|---|---|
| `component` | string | Unity component type (see Component Reference below) |
| `property` | string | Animatable property (see Component Reference) |
| `channels` | string[] | Optional: `["x","y","z"]` for multi-channel properties |
| `keyframes[]` | array | Time-value pairs with easing |

### `keyframes[]` entries

| Field | Type | Description |
|---|---|---|
| `time_sec` | float | Time relative to clip start (monotonically increasing) |
| `value` | float | Single-channel value |
| `values` | float[] | Multi-channel values (use instead of `value` for vector properties) |
| `easing` | string | Easing function name (from `easing_library`) |

### `relationships[]` entries

| Field | Type | Description |
|---|---|---|
| `type` | string | Relationship type (see enum table) |
| `target_object_id` | string | ID of the related animated object |
| `explanation` | string | Detailed explanation of the relationship |

### `source_evidence` object

| Field | Type | Description |
|---|---|---|
| `track_ids` | string[] | Physical CV track IDs (empty `[]` if inferred) |
| `match_confidence` | float | 0.0-1.0 confidence score |
| `match_reason` | string | **Detailed** multi-sentence explanation |
| `visual_evidence` | string[] | Concrete visual cues observed |
| `presence_status` | string | See status enum below |

---

## `animation_sequences[]`

Optional ordered step flows linking animated objects.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique sequence identifier |
| `display_name` | string | Human-readable name |
| `trigger` | string | What starts this sequence |
| `description` | string | Short description |
| `steps[]` | array | Ordered animation steps |

### `steps[]` entries

| Field | Type | Description |
|---|---|---|
| `order` | int | Step order (1-based) |
| `animation_id` | string | Must reference a valid `animated_objects[].id` |
| `parallel` | boolean | Whether this step runs parallel with others at same order |
| `parallel_count` | int | Optional: how many parallel instances |

---

## `track_matching`

Accounting section that ensures every track and every detection object is represented.

| Field | Type | Description |
|---|---|---|
| `matched_tracks[]` | array | `{ track_id, object_id, confidence }` |
| `unmatched_tracks[]` | array | `{ track_id, reason }` — CV tracks with no semantic match |
| `inferred_objects[]` | array | `{ object_id, reason }` — detection objects with no CV track |
| `not_in_clip[]` | array | `{ object_id, reason }` — detection objects absent from video |

---

## Enum Tables

### `object_category` — Animation Behavior Role

Choose based on the object's animation role, not its UI widget type:

| Value | Description | Typical Script Pattern |
|---|---|---|
| `"interactive_element"` | Tappable object that triggers animation (tile, card, button) | Data component + Animator component |
| `"container"` | Manages a group of slots/positions (rack, hand, grid) | Controller component (insert, match, shift) |
| `"effect"` | Visual feedback on an action (particles, sparkle, burst) | Effect component (CanvasGroup-driven) |
| `"text_feedback"` | Text that pops in/out ("Awesome!", "Combo!", score) | Text animator (scale pop + fade) |
| `"overlay"` | Full-screen or regional layer for rendering/dimming | RectTransform + CanvasGroup, minimal script |

### `motion_type` — Physical Motion Observed

| Value | When |
|---|---|
| `"static"` | No meaningful movement detected |
| `"translation"` | Object moves position (dx/dy) |
| `"scale"` | Object changes size (pulse, grow, shrink) |
| `"rotation"` | Object rotates |
| `"fade"` | Object changes opacity (appear/disappear) |
| `"compound"` | Multiple motion types combined |

### `animation_type` — Semantic Animation Intent

| Value | When |
|---|---|
| `"none"` | No meaningful animation |
| `"pulse"` | Scale pop (1 -> 1.15 -> 1) -- idle highlight |
| `"tap_feedback"` | Button press dip (1 -> 0.95 -> 1) |
| `"popup_enter"` | Popup scale-in or fade-in from hidden |
| `"popup_exit"` | Popup scale-out or fade-out |
| `"fill"` | Visual fill change (empty -> filled, sprite swap) |
| `"fade_in"` | Opacity 0 -> 1 |
| `"fade_out"` | Opacity 1 -> 0 |
| `"trajectory"` | Object flies along a path |
| `"bounce"` | Spring/overshoot animation |
| `"shatter"` | Destructive expansion + fade |
| `"slide"` | Lateral slide to fill gaps |
| `"compound"` | Multiple animation types combined |

### `trigger` — What Starts the Animation

| Value | When |
|---|---|
| `"auto_on_open"` | Plays when the screen/popup appears |
| `"auto_on_close"` | Plays when the screen/popup dismisses |
| `"on_tap:<object_id>"` | Plays when user taps the named object |
| `"on_event:<event_name>"` | Plays on a game event |
| `"on_sequence_complete:<sequence_id>"` | Chains after another sequence |
| `"manual"` | Only triggered via code |

### `relationship` types — Ordered by Priority

| Value | Priority | When |
|---|---|---|
| `"moves_to"` | 1 | Object travels toward target |
| `"moves_from"` | 1 | Object originates from target |
| `"transitions_into"` | 1 | Object morphs/transitions into target |
| `"causes_state_change"` | 2 | Object's arrival changes target's visual state |
| `"fills"` | 2 | Object fills or completes target |
| `"activates"` | 2 | Object triggers target's animation |
| `"attached_to"` | 3 | Object is visually attached to target |
| `"contained_in"` | 3 | Object is inside target |
| `"aligned_with"` | 4 | Object is spatially aligned |
| `"paired_with"` | 4 | Object is visually paired |
| `"overlaps"` | 4 | Object overlaps target |

### `presence_status`

| Value | Description |
|---|---|
| `"tracked"` | Matched to a single stable CV track |
| `"tracked_merged"` | Matched to multiple fragmented tracks merged sequentially |
| `"inferred_static"` | Visible but no CV track (uniform color, too small, etc.) |
| `"inferred_attached"` | Moves with parent, no independent track |
| `"uncertain_visible"` | Appears visible but evidence is poor |

### `match_confidence` ranges

| Range | Meaning |
|---|---|
| 0.95-1.00 | Very strong match, clear visual evidence and/or stable tracking |
| 0.80-0.94 | Strong match, minor ambiguity but likely correct |
| 0.60-0.79 | Moderate match, some uncertainty, partial tracking, or inference |
| 0.40-0.59 | Weak but still best available match |
| < 0.40 | Highly uncertain; use only if visible but evidence is poor |

---

## Track -> Animation Property Mapping

| CV track observation | Unity property to animate |
|---|---|
| Position displacement (dx, dy) | `RectTransform.m_AnchoredPosition.x/y` |
| Scale change (sx, sy) | `RectTransform.localScale.x/y/z` |
| Object appears/disappears | `CanvasGroup.m_Alpha` or `Image.m_Color.a` |
| Object bbox shrinks to 0 then gone | `localScale` + `m_Alpha` (popup dismiss) |
| Bbox grows from 0 | `localScale` (popup appear) |
| Object stays put but bbox pulses | `localScale` (tap feedback or pulse) |
| No CV track but visible in first, gone in last | `CanvasGroup.m_Alpha` fade |
| Sprite visual change (CV can't detect) | `Image.m_Sprite` (note: requires `SetObjectReferenceCurve`) |
| Parent has LayoutGroup + children fly | `LayoutGroup.m_Enabled` disable track at fly start |

---

## Component & Property Reference

| Component | Properties |
|---|---|
| `RectTransform` | `localScale.x/y/z`, `m_AnchoredPosition.x/y`, `localRotation.z` |
| `CanvasGroup` | `m_Alpha` |
| `Image` | `m_Color.r/g/b/a`, `m_Sprite` (object ref) |
| `HorizontalLayoutGroup` | `m_Enabled` |
| `VerticalLayoutGroup` | `m_Enabled` |
| `GameObject` | `m_IsActive` |

---

## Easing Values Reference

| Value | When to use | PrimeTween `Ease` |
|---|---|---|
| `"linear"` | Constant-speed movement | `Ease.Linear` |
| `"constant"` | Step/instant change (bool, sprite swap) | N/A (set value directly) |
| `"ease_in"` | Slow start -> fast end | `Ease.InQuad` |
| `"ease_out"` | Fast start -> slow end (landing, settling) | `Ease.OutQuad` |
| `"ease_in_out"` | Smooth acceleration + deceleration (most UI) | `Ease.InOutQuad` |
| `"spring"` | Overshoots target, settles back (bouncy popup) | `Ease.OutBack` |

### Quantitative Easing Selection Heuristics

Instead of guessing, use the displacement curve shape from CV data:

| Displacement Curve Shape | Easing |
|---|---|
| Speed roughly constant across all frames | `"linear"` |
| Speed highest in first 30% of frames, then decays | `"ease_out"` |
| Speed ramps from near-zero in first 30%, then constant | `"ease_in"` |
| Speed ramps 0 -> peak -> 0 symmetrically | `"ease_in_out"` |
| Position overshoots target value then settles back | `"spring"` |
| Value jumps instantly between frames (no interpolation) | `"constant"` |
| First and last thirds are flat with central change | Add hold keyframes at flat regions |

---

## Validation Checklist

Before writing output, verify:

- [ ] `"schema": "6.1.0"` at root
- [ ] `meta` contains all required fields
- [ ] `meta.scene` is real scene name or `"UNKNOWN"` (never hallucinated)
- [ ] `easing_library` defines all easing functions used in keyframes
- [ ] Every `animated_objects[].id` is unique
- [ ] Every `target.path` is validated (`path_validated: true`) or marked `path_validated: false`
- [ ] `total_duration_sec` equals the last keyframe `time_sec` in the longest track
- [ ] Keyframe `time_sec` values are monotonically increasing within each track
- [ ] No track has more than 6 keyframes
- [ ] Every object has both `source_category` (raw) and `object_category` (enum)
- [ ] Every object has `motion_type` and `animation_type` from allowed enums
- [ ] Every object has `motion_summary` (detailed, multi-sentence)
- [ ] Every object has `relationships[]` (can be `[]`)
- [ ] Every object has complete `source_evidence`
- [ ] `presence_status` is a valid enum value
- [ ] `animation_sequences[].steps[].animation_id` references valid object IDs
- [ ] Repeated sibling objects are output separately (not collapsed)
- [ ] Jitter < 5px is not turned into false translation keyframes
- [ ] Static objects: no position in keyframes (only scale/opacity/rotation)
- [ ] Moving objects: position in keyframes describing real trajectory
- [ ] Transfer animations: both `moves_to` and `causes_state_change`/`fills` relationships
- [ ] Every detection JSON object is in `animated_objects`, `track_matching.inferred_objects`, or `track_matching.not_in_clip`
- [ ] Unmatched CV tracks are listed in `track_matching.unmatched_tracks`
