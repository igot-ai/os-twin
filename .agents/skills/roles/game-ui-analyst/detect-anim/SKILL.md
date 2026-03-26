---
name: detect-anim
description: Analyse a screen-recorded video of a Unity UI animation (popup appear, heart refill, level complete, etc.) and generate animation_clips JSON with per-object keyframe tracks. Uses a 2-phase pipeline — Python/OpenCV extracts motion data, then Claude performs semantic analysis matching tracks to objects from a _detection.json. Run this after /detect-ui.
argument-hint: <video_path> <detection_json_path> [output_json_path]
allowed-tools: Read, Write, Glob, Grep, Bash
---

Analyse the screen-recorded UI animation video and produce animation clip tracks.

Parse `$ARGUMENTS` as:
- `$0` — video file path (.mov / .mp4) — a screen recording of the UI animation
- `$1` — detection JSON path (output of `/detect-ui`) — provides the semantic object list
- `$2` — output JSON path (optional; default: detection JSON path with `_anim.json` suffix)

---

## Architecture — Two Phases

This skill is split into two phases, mirroring the physical_motion pipeline:

```
Phase 1 — Python/OpenCV (Bash)          Phase 2 — Claude (semantic analysis)
┌──────────────────────────┐            ┌──────────────────────────────┐
│ extract_motion.py        │            │ Agent reads:                 │
│  1. Extract frames       │            │  • motion_data.json          │
│  2. Detect motion        │  ────→     │  • annotated_*.png           │
│  3. Segment blobs        │  output    │  • detection JSON            │
│  4. Track centroids      │  dir       │  • first/last raw frames     │
│  5. Compute transforms   │            │                              │
│  6. Save annotated PNGs  │            │ Agent produces:              │
│     + motion_data.json   │            │  • animation_clips JSON      │
└──────────────────────────┘            └──────────────────────────────┘
```

**Why two phases?** OpenCV does the pixel-level work (motion detection, tracking) much
better than vision-only analysis. Claude does the semantic reasoning (matching tracks to
UI objects, determining easing, inferring static elements) much better than a fixed algorithm.

---

## Phase 1 — Run the CV Pipeline

Run the Python script via Bash. The script lives in `${CLAUDE_SKILL_DIR}/scripts/`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/extract_motion.py" \
    "$0" \
    "/tmp/detect_anim_out" \
    --threshold 30 \
    --min-area 500 \
    --max-keyframes 20
```

This produces in `/tmp/detect_anim_out/`:
- `motion_data.json` — transforms, track summaries, video info
- `annotated_NNNN.png` — keyframe images with red bounding boxes and track IDs
- `frame_first.png` — raw first frame (before any animation)
- `frame_last.png` — raw last frame (after animation)

Read the terminal output for a quick summary of tracks found.

If the script fails (missing `cv2`), install: `pip install opencv-python-headless numpy`

---

## Phase 2 — Semantic Analysis (You, the agent)

### Step 2.1 — Read all inputs

Read these files (in parallel if possible):
1. `/tmp/detect_anim_out/motion_data.json` — CV motion data
2. `$1` — detection JSON (object list from `/detect-ui`)
3. `/tmp/detect_anim_out/frame_first.png` — view the starting state
4. `/tmp/detect_anim_out/frame_last.png` — view the ending state
5. A few `annotated_*.png` files — view tracked bounding boxes

### Step 2.2 — Understand what you're looking at

From `motion_data.json` extract:
- `video_info.fps` → needed for time calculations
- `video_info.duration_sec` → total clip length
- `video_info.resolution` → pixel dimensions
- `track_summary[]` → quick overview of each track's displacement, scale change, timing
- `transforms{}` → raw per-frame position/scale deltas per track

From the detection JSON extract:
- `screens[0].objects[]` → the semantic object list (every UI element with id, category, bounding_box, canvas_position)
- `meta.to_canvas` → coordinate conversion for matching pixel positions to Unity canvas units

### Step 2.3 — Match physical tracks to semantic objects

**CRITICAL: Work semantic-object-first, not track-first.**

For **each expected semantic object** from the detection JSON, determine:
1. Whether the object is visually present in the video
2. Whether it has meaningful visible motion
3. Which physical track or tracks support it
4. Whether any missing tracking should be inferred from visual evidence

Then for each track in `track_summary`, determine which `objects[].id` it corresponds to:

**Matching strategy (ordered by priority):**
1. **Position overlap** — does the track's `start_bbox` overlap with any object's `bounding_box`?
2. **Normalized center** — is the track's `normalized_start_center` close to an object's `normalized_bbox` center?
3. **Size similarity** — does the track's bbox size match an object's bounding_box size?
4. **Motion hints** — does the track's `motion_type_hint` align with what that object should do?
5. **Visual evidence** — look at the annotated frames to confirm the match

**Rules:**
- One track can map to one object (1:1 or many:1 if merged)
- Multiple tracks for the same object → merge them sequentially
- Objects with no matching track → classify as `"inferred_static"` (they exist but don't move)
- Tracks with no matching object → classify as `"unmatched"` and note in output

### Step 2.4 — Build animation clips

For each matched object, generate an animation clip entry. Structure your keyframes by:
1. Reading the track's transform data (position, scale per frame)
2. Converting frame indices to time: `time_sec = frame_idx / fps`
3. **Reducing keyframes** to 2-4 per object:
   - Start state
   - Peak motion / key state change
   - End state
4. Determining easing from the motion curve shape:
   - Linear movement → `"linear"`
   - Slow start → `"ease_in"`
   - Slow end → `"ease_out"`
   - Slow start & end → `"ease_in_out"`
   - Instant change → `"constant"` (for sprite swaps, enable/disable)

### Step 2.5 — Handle objects without tracks (static or inferred)

Not every object will have a CV track. For these:
- **Dim overlay**: Infer alpha animation from first/last frame comparison (visible → gone)
- **Popup card**: If it appears or disappears, infer scale/alpha animation
- **Text labels**: Usually animate with their parent (popup_child)
- **Static containers**: May not move at all — skip or emit empty track
- **Sprite swaps**: CV can't detect these — infer from context (e.g., hearts fill → sprite changes)

---

## Semantic Analysis Rules (MUST follow all 18 rules)

These rules govern how you reason about the CV data. They are your priority system.

Your priority order:
1. **Coverage of visible objects** — never drop a visible animated object
2. **Correct semantic matching** — assign the right identity
3. **Accurate motion reconstruction** — keyframes reflect real motion
4. **Unity-compatible animation output** — valid component/property paths

### Rule 1 — Do Not Drop Visible Motion Objects

If a semantic object is visually present and shows any meaningful motion, it **must** be included in the output.

This applies even when:
- The track is noisy
- The object is partially occluded
- The object only animates briefly
- The motion is mostly scale or opacity
- The object is a child element of a larger UI object

If these are visible and animated, do not collapse, absorb, or omit them.

### Rule 2 — Semantic Coverage Requirement

Maximize coverage of the expected semantic objects that are visually present.

For each expected semantic object:
- If clearly visible → output it
- If weakly tracked but clearly visible → output it as inferred
- If attached to a parent object but visually distinct → output it separately
- If repeated as siblings → output each visible sibling separately

Only omit objects that are truly not visible.

### Rule 3 — Repeated Sibling Objects

If multiple semantic objects are visually distinct but similar in appearance and arranged as siblings in a group, do **not** collapse them into one entry.

Example: `heart_empty_0`, `heart_empty_1`, `heart_empty_2` — if each heart is visible, output each heart separately.

### Rule 4 — Attached Child Objects

If a small object is visually attached to a larger parent object but has its own semantic ID from the detection JSON, output it as a separate object when it is visually distinct.

Examples: bonus badge on a button, icon attached to a title bar, small heart badge on refill button.

Do not absorb attached child objects into their parent if they exist in the expected semantic object list.

### Rule 5 — Track Merging

If multiple CV tracks correspond to the same semantic object (fragmented tracking), merge their motion sequentially into one animation timeline.

Example: `track_2 → track_5 → track_8` may represent the same object across time.

The final output must contain only **one animation entry per semantic object**.

### Rule 6 — Infer Visible Objects Even Without Strong Tracks

If an object is clearly visible but lacks a stable independent track, still output it.

Use:
- Visual evidence from annotated frames
- Relative location to known objects
- Parent-child relationship from detection JSON
- Nearby known objects
- Frame appearance over time (first vs last frame)

Mark such objects with `presence_status: "inferred_static"` or `"inferred_attached"` instead of dropping them.

### Rule 7 — Ignore Tracking Jitter

Tracking data may contain noise. If movement distance between frames is **less than 5 pixels**, treat the movement as jitter unless there is strong visual evidence of real motion.

Do not generate fake translation keyframes from jitter.

### Rule 8 — Static vs Moving Object Rule

**Static objects** (UI buttons, panels, icons, text):
- Position should remain constant
- Define position once in the track's context, not in every keyframe
- Keyframes should animate only scale, opacity, or rotation if visible
- If no meaningful animation exists, the track can have minimal keyframes

**Moving objects** (flying hearts, floating items, touch indicators, particles):
- Position must be included in keyframes
- Keyframes should describe actual motion trajectory
- Use `m_AnchoredPosition` for position animation

### Rule 9 — Keyframe Reduction

Do **not** output every frame from the CV data. Instead, summarize motion using keyframes representing:
- Animation start
- Peak motion / peak scale / key state change
- Animation end

Most animations should contain **2 to 4 keyframes**. Maximum 6.

### Rule 10 — Timeline Rule

Each object's animation must track:
- When it starts in the video timeline (`start_time_sec` in `source_evidence`)
- Its duration

Keyframe `time_sec` values are relative to the **clip start** (not the object's individual start).

Constraint: `total_duration_sec` must equal the last keyframe `time_sec` in the longest track.

### Rule 11 — Loop Type

Use one of the following playback modes:
- `false` → animation plays once (default for most UI)
- `true` → animation repeats continuously (idle loops, pulsing effects)

### Rule 12 — Unity Transform Compatibility

Animations must target real Unity component properties. Each track must specify:
- `component` — the Unity component type (`RectTransform`, `CanvasGroup`, `Image`, etc.)
- `property` — the animatable property (`localScale`, `m_AnchoredPosition`, `m_Alpha`, etc.)
- `keyframes[]` — with `time_sec`, `values`/`value`, and `easing`

### Rule 13 — Motion Validation

If detected motion contradicts expected object behavior, assume tracking error and correct it using semantic reasoning.

Examples of tracking errors:
- A static UI icon suddenly jumps across the screen
- A button appears to teleport
- A small badge gets confused with the parent button

In such cases:
- Keep the object position constant
- Preserve real visible scale/fade motion if present
- Do not invent false translation

### Rule 14 — Match Evidence (REQUIRED for every track)

Every track in the output must include `source_evidence` with:

**`track_ids`** — list of physical tracking IDs that support this semantic object.
- Include all track IDs that directly correspond to the object
- If multiple fragmented tracks belong to the same object, include all in temporal order
- If no stable track exists, use `[]`

**`match_confidence`** — float 0.0–1.0:
- `0.95–1.00` → very strong match, clear visual evidence and/or stable tracking
- `0.80–0.94` → strong match, minor ambiguity but likely correct
- `0.60–0.79` → moderate match, some uncertainty, partial tracking, or inference
- `0.40–0.59` → weak but still best available match
- Below `0.40` → highly uncertain; use only if the object is visible but evidence is poor

**`match_reason`** — use a **detailed explanation**, not a short phrase. Must describe:
- Why this semantic object was selected
- Which visual features support the match
- The object's relative position in the UI
- Nearby related objects that help confirm the identity
- Whether the match was directly tracked or partly inferred
- Any ambiguity, overlap, or uncertainty

Example: *"This object is matched as `refill_bonus_badge` because it appears as a small red heart-shaped badge attached to the top-right area of the green refill button, contains the '+3' text, and remains visually distinct from the parent button even though no stable independent track was produced."*

**`visual_evidence`** — list of concrete visual cues observed in the video/frames:
- Color, shape, icon/symbol, text content
- Relative position on screen, size
- Attachment to a parent object
- Containment inside a panel or container
- Distinctive visual state changes

Good: `"large green rounded rectangular button at the bottom center of the popup"`
Bad: `"important gameplay object"` or `"probably the refill button"`

**`presence_status`** — one of:
- `tracked` — matched to a single stable CV track
- `tracked_merged` — matched to multiple fragmented tracks merged sequentially
- `inferred_static` — visible but no CV track (uniform color, too small, etc.)
- `inferred_attached` — moves with parent, no independent track
- `uncertain_visible` — appears visible but evidence is poor

### Rule 15 — Motion Semantics (REQUIRED for every track)

Every track must include semantic motion metadata:

**`object_category`** — copied directly from the detection JSON's `category` field (e.g. `"UI/Button"`, `"UI/Icon"`, `"UI/Overlay"`). Do NOT invent new values.

**`motion_type`** — the physical motion type observed (see enum table below)

**`animation_type`** — the semantic animation intent (see enum table below)

**`motion_summary`** — **detailed explanation** of the actual visible motion:
- The actual visible motion behavior
- Whether the motion is real or likely tracking noise
- Whether the object changes position, scale, opacity, rotation, or visual state
- Whether the animation is brief, continuous, sequential, or inferred
- How the motion should be interpreted for Unity reconstruction
- Any important relationship to other objects

Example: *"The object remains attached to the refill button without meaningful independent translation. Its visible behavior is primarily static, with any apparent motion likely caused by parent-button tracking jitter rather than real object movement."*

**`relationships`** — list of meaningful visual relationships between this object and other semantic objects:

```json
[
  {
    "type": "<relationship type>",
    "target_object_id": "<semantic object id>",
    "relationship_explanation": "<detailed explanation of the visible relationship>"
  }
]
```

**Relationship priority order** (prefer higher priority when multiple apply):
1. **Motion-to-target**: `moves_to`, `moves_from`, `transitions_into`
2. **State-change/effect**: `causes_state_change`, `fills`, `activates`
3. **Structural**: `attached_to`, `contained_in`
4. **Secondary layout**: `aligned_with`, `paired_with`, `overlaps`

Do **not** use only a weak layout relationship like `aligned_with` if a stronger motion or state-change relationship is clearly visible.

### Rule 16 — Special Rule for UI State Animations

Some UI elements do not move positionally but still animate meaningfully through:
- Fill changes (empty heart → filled heart)
- Pulse (scale pop 1 → 1.15 → 1)
- Opacity changes (fade in/out)
- Badge appearance
- Scale pop

Do not classify these as static/no-animation if visible animation exists.

### Rule 17 — Special Rule for Small Objects

Small objects are easy to lose in tracking, but they must still be included if they are visibly present.

Examples: bonus badges, small title icons, heart badges, attached indicators.

Small size is **not** a reason to omit an object.

### Rule 18 — Best-Match Policy + Relationship Priority

If evidence is ambiguous:
- Choose the best semantic match
- Keep the object if it is visible
- Lower the confidence if needed
- Explain the ambiguity in `match_reason`

Do not drop visible objects just because confidence is not perfect.

**Transfer Animations**: If one object visibly travels toward another object and the destination object changes visual state at the end of that motion, treat this as a transfer animation. Include at least:
- One `moves_to` relationship
- One `causes_state_change` or `fills` relationship

Do not reduce transfer animations to only `aligned_with` or `paired_with`.

---

## Output Schema — v6.0.0

Write a JSON file with this structure:

```jsonc
{
  "schema": "6.0.0",

  "meta": {
    "scene": "<active scene name>",
    "scene_path": "<scene asset path>",
    "source_video": "$0",
    "detection_json": "$1",
    "canvas": {
      "w": 1080,
      "h": 1920,
      "scale_mode": "ScaleWithScreenSize",
      "match": 0.5,
      "render_mode": "ScreenSpaceOverlay"
    },
    "generated_at": "<ISO 8601 timestamp>"
  },

  "easing_library": {
    "linear":      { "formula": "t",                           "csharp": "t" },
    "ease_in":     { "formula": "t²",                          "csharp": "t * t" },
    "ease_out":    { "formula": "1 − (1−t)²",                  "csharp": "1f - (1f - t) * (1f - t)" },
    "ease_in_out": { "formula": "t<0.5 ? 2t² : 1−(−2t+2)²/2", "csharp": "t < 0.5f ? 2f * t * t : 1f - Mathf.Pow(-2f * t + 2f, 2f) / 2f" },
    "spring":      { "formula": "overshoot then settle",       "csharp": "<custom per-object>" },
    "constant":    { "formula": "step function",               "csharp": "1f" }
  },

  "animated_objects": [
    {
      "id":               "btn_refill_tap",
      "display_name":     "Refill Button Tap Feedback",
      "object_category":  "interactive_element",
      "motion_type":      "scale",
      "animation_type":   "tap_feedback",
      "trigger":          "on_tap:btn_refill_green",
      "description":      "Button dips then returns on press.",

      "target": {
        "path":        "UI_Root/PopupCard/BtnRefill",
        "apply_to":    "single",
        "required_components": ["RectTransform", "Button", "CanvasGroup"],
        "initial_state": { "scale": [1.0, 1.0, 1.0], "alpha": 1.0 }
      },

      "tracks": [
        {
          "component": "RectTransform",
          "property":  "localScale",
          "channels":  ["x", "y", "z"],
          "keyframes": [
            { "time_sec": 0.00, "values": [1.0, 1.0, 1.0], "easing": "ease_in_out" },
            { "time_sec": 0.15, "values": [0.95, 0.95, 1.0], "easing": "ease_in_out" },
            { "time_sec": 0.30, "values": [1.0, 1.0, 1.0] }
          ]
        }
      ],

      "total_duration_sec": 0.30,
      "motion_summary":    "Button dips to 95% scale on press then returns to 100%.",

      "relationships": [
        {
          "type": "activates",
          "target_object_id": "heart_fill_sequence",
          "explanation": "Tapping the refill button triggers the heart fill sequence."
        }
      ],

      "source_evidence": {
        "track_ids":        ["track_3"],
        "match_confidence":  0.92,
        "match_reason":     "Track bbox overlaps btn_refill_green at 91%. Scale oscillation matches tap feedback.",
        "visual_evidence":  ["large green rounded button at bottom center", "scale pulse 1→0.95→1 over ~0.3s"],
        "presence_status":  "tracked"
      }
    },
    {
      "id":               "dim_overlay_fade",
      "display_name":     "Dim Overlay Fade Out",
      "object_category":  "overlay",
      "motion_type":      "fade",
      "animation_type":   "fade_out",
      "trigger":          "on_event:popup_dismiss",
      "description":      "Dark overlay fades from visible to invisible.",

      "target": {
        "path":        "UI_Root/DimOverlay",
        "apply_to":    "single",
        "required_components": ["RectTransform", "CanvasGroup", "Image"],
        "initial_state": { "alpha": 0.6 }
      },

      "tracks": [
        {
          "component": "CanvasGroup",
          "property":  "m_Alpha",
          "keyframes": [
            { "time_sec": 0.00, "value": 0.6, "easing": "linear" },
            { "time_sec": 1.20, "value": 0.6, "easing": "ease_in_out" },
            { "time_sec": 1.80, "value": 0.0 }
          ]
        }
      ],

      "total_duration_sec": 1.80,
      "motion_summary":    "Overlay holds at 60% opacity, fades to 0% during dismiss.",

      "relationships": [],

      "source_evidence": {
        "track_ids":        [],
        "match_confidence":  0.85,
        "match_reason":     "No CV track — uniform color. Inferred from first vs last frame.",
        "visual_evidence":  ["dark overlay behind popup, visible in first frame, gone in last"],
        "presence_status":  "inferred_static"
      }
    }
  ],

  "animation_sequences": [
    {
      "id":           "refill_full_sequence",
      "display_name": "Full Refill Flow",
      "trigger":      "on_tap:btn_refill_green",
      "description":  "Button tap → hearts fill → fly to HUD → overlay dismiss.",
      "steps": [
        { "order": 1, "animation_id": "btn_refill_tap", "parallel": false },
        { "order": 2, "animation_id": "heart_fill_sequence", "parallel": true, "parallel_count": 3 },
        { "order": 3, "animation_id": "dim_overlay_fade", "parallel": false }
      ]
    }
  ],

  "scene_wiring": {
    "note": "Minimal hints for build-anim to create/find supporting GameObjects."
  },

  "track_matching": {
    "matched_tracks": [
      { "track_id": "track_3", "object_id": "btn_refill_tap", "confidence": 0.92 }
    ],
    "unmatched_tracks": [
      { "track_id": "track_7", "reason": "Brief noise track, 4 frames, no match." }
    ],
    "inferred_objects": [
      { "object_id": "dim_overlay_fade", "reason": "Uniform color — inferred from frame comparison." }
    ]
  }
}
```

---

## Track → Animation Property Mapping

| CV track observation | Unity property to animate |
|---|---|
| Position displacement (dx, dy) | `RectTransform.m_AnchoredPosition.x/y` |
| Scale change (sx, sy) | `RectTransform.localScale.x/y/z` |
| Object appears/disappears | `CanvasGroup.m_Alpha` or `Image.m_Color.a` |
| Object bbox shrinks to 0 then gone | `localScale` + `m_Alpha` (popup dismiss) |
| Bbox grows from 0 | `localScale` (popup appear) |
| Object stays put but bbox pulses | `localScale` (tap feedback or pulse) |
| No CV track but visible in first, gone in last | `CanvasGroup.m_Alpha` fade (infer timing from nearby tracks) |
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

## Easing Values

| Value | When to use |
|---|---|
| `"linear"` | Constant-speed movement |
| `"constant"` | Step/instant change (bool, sprite swap) |
| `"ease_in"` | Slow start → fast end |
| `"ease_out"` | Fast start → slow end (landing, settling) |
| `"ease_in_out"` | Smooth acceleration + deceleration (most UI animations) |
| `"spring"` | Overshoots target, settles back (bouncy popup appear) |

---

## Object Category Values

Categories describe the **animation behaviour role** of each object, not its UI widget type. Choose the most specific match:

| Value | Description | Typical Script Pattern |
|---|---|---|
| `"interactive_element"` | Tappable object that triggers animation (tile, card, button) | Data component + Animator component |
| `"container"` | Manages a group of slots/positions (rack, hand, grid) | Controller component (insert, match, shift) |
| `"effect"` | Visual feedback on an action (particles, sparkle, burst) | Effect component (CanvasGroup-driven) |
| `"text_feedback"` | Text that pops in/out ("Awesome!", "Combo!", score) | Text animator (scale pop + fade) |
| `"overlay"` | Full-screen or regional layer for rendering/dimming | RectTransform + CanvasGroup, minimal script |

---

## Motion Type Values

Describes the **physical motion** observed in the video:

| Value | When |
|---|---|
| `"static"` | No meaningful movement detected |
| `"translation"` | Object moves position (dx/dy) |
| `"scale"` | Object changes size (pulse, grow, shrink) |
| `"rotation"` | Object rotates |
| `"fade"` | Object changes opacity (appear/disappear) |
| `"compound"` | Multiple motion types combined (e.g., translate + scale + fade) |

---

## Animation Type Values

Describes the **semantic animation intent** (what the animation means in the game):

| Value | When |
|---|---|
| `"none"` | No meaningful animation |
| `"pulse"` | Scale pop (1 → 1.15 → 1) — idle highlight or attention grab |
| `"tap_feedback"` | Button press dip (1 → 0.95 → 1) |
| `"popup_enter"` | Popup scale-in or fade-in from hidden state |
| `"popup_exit"` | Popup scale-out or fade-out to hidden state |
| `"fill"` | Visual fill change (empty → filled, sprite swap) |
| `"fade_in"` | Opacity 0 → 1 (appear) |
| `"fade_out"` | Opacity 1 → 0 (disappear) |
| `"trajectory"` | Object flies along a path (tile → rack, heart → HUD) |
| `"bounce"` | Spring/overshoot animation (scale 0 → 1.15 → 1) |
| `"shatter"` | Destructive expansion + fade (match clear, break) |
| `"slide"` | Lateral slide to fill gaps (rack compact) |
| `"compound"` | Multiple animation types combined |

---

## Relationship Type Values

Relationships describe how animated objects interact. Prefer **motion/causal** relationships over purely structural ones:

| Value | Priority | When |
|---|---|---|
| `"moves_to"` | 1 | Object travels toward target (tile → rack slot) |
| `"moves_from"` | 1 | Object originates from target |
| `"transitions_into"` | 1 | Object morphs/transitions into target |
| `"causes_state_change"` | 2 | Object's arrival changes target's visual state |
| `"fills"` | 2 | Object fills or completes target |
| `"activates"` | 2 | Object triggers target's animation |
| `"attached_to"` | 3 | Object is visually attached to target |
| `"contained_in"` | 3 | Object is inside target |
| `"aligned_with"` | 4 | Object is spatially aligned with target |
| `"paired_with"` | 4 | Object is visually paired with target |
| `"overlaps"` | 4 | Object overlaps target |

---

## Trigger Values

| Value | When |
|---|---|
| `"auto_on_open"` | Plays when the screen/popup appears |
| `"auto_on_close"` | Plays when the screen/popup dismisses |
| `"on_tap:<object_id>"` | Plays when user taps the named object |
| `"on_event:<event_name>"` | Plays on a game event (e.g., `rack_match_found`, `all_shatters_complete`) |
| `"on_sequence_complete:<sequence_id>"` | Chains after another animation sequence completes |
| `"manual"` | Only triggered via code |

---

## Validation Checklist

Before writing output:

- [ ] Output JSON has `"schema": "6.0.0"` at root
- [ ] `meta` contains `scene`, `scene_path`, `source_video`, `detection_json`, `canvas`, `generated_at`
- [ ] `easing_library` defines all easing functions used in keyframes
- [ ] Every `animated_objects[].id` is unique
- [ ] Every `animated_objects[].target.path` matches an actual scene hierarchy path
- [ ] `total_duration_sec` equals the last keyframe's `time_sec` in the longest track per object
- [ ] Keyframe `time_sec` values are monotonically increasing within each track
- [ ] No track has more than 6 keyframes (reduce if more — start, peak, end is enough)
- [ ] Every animated object has `object_category` from the allowed enum table
- [ ] Every animated object has `motion_type` and `animation_type` from allowed enums
- [ ] Every animated object has `motion_summary` (detailed explanation of visible motion)
- [ ] Every animated object has `relationships[]` array (can be `[]`)
- [ ] Every animated object has `source_evidence` with `track_ids`, `match_confidence`, `match_reason`, `visual_evidence`, `presence_status`
- [ ] `source_evidence.presence_status` is one of: `tracked`, `tracked_merged`, `inferred_static`, `inferred_attached`, `uncertain_visible`
- [ ] `animation_sequences[]` — if present — references valid `animated_objects[].id` values
- [ ] Repeated sibling objects are output separately (not collapsed)
- [ ] Jitter < 5px is not turned into false translation keyframes
- [ ] Static objects do not have position in keyframes (only scale/opacity/rotation)
- [ ] Moving objects have position in keyframes describing real trajectory
- [ ] Transfer animations include both `moves_to` and `causes_state_change`/`fills` relationships
- [ ] Every detection JSON object is either in `animated_objects` or in `track_matching.inferred_objects`
- [ ] Unmatched CV tracks are listed in `track_matching.unmatched_tracks`

---

## Output Summary (print after saving)

```
✅ Saved: <output_path> (schema 6.0.0)

Animated objects       : <N>
Total tracks           : <N>
Animation sequences    : <N>
Objects with animation : <N> / <total objects in detection JSON>
  tracked (CV match)   : <N>
  inferred (no CV)     : <N>
Unmatched CV tracks    : <N>
```

Then an animated objects table:

| id | object_category | track_ids | confidence | animation_type | tracks | duration | motion_summary |
|---|---|---|---|---|---|---|---|
| btn_refill_tap | interactive_element | track_3 | 0.92 | tap_feedback | localScale | 0.30s | tap dip 1→0.95→1 |
| dim_overlay_fade | overlay | (inferred) | 0.85 | fade_out | m_Alpha | 1.80s | hold 0.6 → fade 0 |

Then a relationships summary:

```
Relationships:
  • btn_refill_tap ──activates──→ heart_fill_sequence
  • heart_fill ──moves_to──→ hud_heart_slot
  • heart_fill ──causes_state_change──→ hud_heart_slot
```

Then sequences:

```
Sequences:
  • refill_full_sequence — trigger: on_tap:btn_refill_green — 3 steps
```
