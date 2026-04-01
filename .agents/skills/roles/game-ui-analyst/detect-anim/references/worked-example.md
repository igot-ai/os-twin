# Worked Example: Semantic Track Matching

This walks through the complete reasoning process for matching one CV track to one semantic object.

---

## Input: CV Track Data

From `motion_data.json`:

```json
{
  "track_summary": [
    {
      "track_id": "track_3",
      "start_frame": 12,
      "end_frame": 22,
      "duration_frames": 10,
      "start_bbox": [380, 1420, 720, 1560],
      "normalized_start_center": [0.509, 0.776],
      "displacement_px": 3.2,
      "scale_change": { "sx": 0.94, "sy": 0.94 },
      "motion_type_hint": "scale"
    },
    {
      "track_id": "track_7",
      "start_frame": 8,
      "end_frame": 12,
      "duration_frames": 4,
      "start_bbox": [502, 1395, 518, 1410],
      "normalized_start_center": [0.472, 0.731],
      "displacement_px": 42.7,
      "scale_change": { "sx": 1.0, "sy": 1.0 },
      "motion_type_hint": "translation"
    }
  ]
}
```

Video info: 30 fps, 1080x1920, 2.1 seconds.

## Input: Detection JSON Object

```json
{
  "id": "btn_refill_green",
  "category": "UI/Button",
  "bounding_box": [370, 1410, 710, 1570],
  "normalized_bbox": [0.343, 0.734, 0.657, 0.818],
  "canvas_position": { "x": 0, "y": -410 }
}
```

## Step 1 -- Inspect the Semantic Object

The detection JSON describes `btn_refill_green` as a `UI/Button` at the bottom center of the screen (normalized center ~0.50, ~0.78). Bounding box spans 340x160 pixels -- a wide, short button.

**What to expect:** A button of this type likely has tap feedback (scale dip) or is part of a popup dismiss sequence. Position should be stable (buttons don't fly). Scale or alpha changes are plausible.

## Step 2 -- Shortlist Candidate Tracks

Two tracks overlap the time range and spatial region:

- **track_3**: Center (0.509, 0.776) is very close to the button's normalized center. Bbox [380,1420,720,1560] overlaps with [370,1410,710,1570]. Displacement is only 3.2px (essentially stationary). Scale change is 0.94x (a ~6% shrink). Motion hint: "scale".

- **track_7**: Center (0.472, 0.731) is moderately close but offset. Bbox [502,1395,518,1410] is only 16x15 pixels -- far too small for a 340x160 button. Displacement is 42.7px (significant). This is a tiny, fast-moving blob.

## Step 3 -- Reject Bad Candidates

**Reject track_7** for `btn_refill_green`:
- Size mismatch: track_7 bbox is 16x15px vs the button's 340x160px (99% size difference)
- The displacement of 42.7px suggests small debris or a child element, not the button itself
- Duration is only 4 frames (~0.13s) -- too brief for a button interaction
- This track likely corresponds to a small badge or noise artifact

## Step 4 -- Accept Best Match

**Accept track_3** for `btn_refill_green`:
- **Position overlap**: track_3 bbox [380,1420,720,1560] overlaps with detection [370,1410,710,1570] at ~91% IoU
- **Normalized center**: track_3 (0.509, 0.776) vs detection center (0.500, 0.776) -- nearly identical
- **Motion type**: Scale change of 0.94x matches a typical tap-feedback dip pattern
- **Displacement**: 3.2px is below the 5px jitter threshold -- no real translation (as expected for a button)
- **Size match**: track_3 bbox is 340x140px, detection is 340x160px -- very close

**Confidence: 0.92** (strong match -- minor bbox height difference, otherwise excellent overlap)

**Presence status: `tracked`** (single stable CV track with clear correspondence)

## Step 5 -- Derive Keyframes and Easing

From `transforms["track_3"]`, the scale data shows:

| Frame | Scale X | Scale Y | Time (sec) |
|---|---|---|---|
| 12 | 1.00 | 1.00 | 0.400 |
| 15 | 0.97 | 0.97 | 0.500 |
| 17 | 0.94 | 0.94 | 0.567 |
| 20 | 0.98 | 0.98 | 0.667 |
| 22 | 1.00 | 1.00 | 0.733 |

The scale dips from 1.0 to 0.95 and returns. Total duration: ~0.33s.

**Keyframe reduction** (5 frames -> 3 keyframes):
1. Start: t=0.00, scale=1.0 (animation-relative time)
2. Peak dip: t=0.15, scale=0.95 (smoothed from 0.94; the 0.94 value likely includes measurement noise)
3. Return: t=0.30, scale=1.0

**Easing**: The speed ramps up then back down symmetrically -> `"ease_in_out"`

## Step 6 -- Produce Final JSON Entry

```json
{
  "id": "btn_refill_tap",
  "display_name": "Refill Button Tap Feedback",
  "source_category": "UI/Button",
  "object_category": "interactive_element",
  "motion_type": "scale",
  "animation_type": "tap_feedback",
  "trigger": "on_tap:btn_refill_green",
  "description": "Button dips then returns on press.",
  "target": {
    "path": "UI_Root/PopupCard/BtnRefill",
    "path_validated": false,
    "apply_to": "single",
    "required_components": ["RectTransform", "Button", "CanvasGroup"],
    "initial_state": { "scale": [1.0, 1.0, 1.0], "alpha": 1.0 }
  },
  "tracks": [
    {
      "component": "RectTransform",
      "property": "localScale",
      "channels": ["x", "y", "z"],
      "keyframes": [
        { "time_sec": 0.00, "values": [1.0, 1.0, 1.0], "easing": "ease_in_out" },
        { "time_sec": 0.15, "values": [0.95, 0.95, 1.0], "easing": "ease_in_out" },
        { "time_sec": 0.30, "values": [1.0, 1.0, 1.0] }
      ]
    }
  ],
  "total_duration_sec": 0.30,
  "motion_summary": "The refill button shows a classic tap-feedback scale dip. Starting at full scale (1.0), it contracts to approximately 95% over 0.15 seconds, then springs back to 1.0 over the next 0.15 seconds. The motion is symmetrical with no noticeable position change -- the 3.2px displacement from CV data is below the jitter threshold and does not represent real translation. This is a standard mobile UI button feedback pattern that makes the press feel responsive.",
  "relationships": [
    {
      "type": "activates",
      "target_object_id": "heart_fill_sequence",
      "explanation": "Tapping the refill button initiates the heart fill animation sequence. The button dip provides immediate tactile feedback while the hearts begin filling after the dip completes."
    }
  ],
  "source_evidence": {
    "track_ids": ["track_3"],
    "match_confidence": 0.92,
    "match_reason": "Track_3's bounding box [380,1420,720,1560] overlaps with btn_refill_green's detection box [370,1410,710,1570] at approximately 91% IoU. The normalized center positions are nearly identical (track: 0.509/0.776, detection: 0.500/0.776). The track shows a clear scale oscillation from 1.0 to 0.94 and back, consistent with tap feedback on a large button. The minimal displacement of 3.2px confirms the button stays in place. Track_7 was rejected because its bbox (16x15px) is far too small for this 340x160px button -- it likely belongs to a child badge element.",
    "visual_evidence": [
      "large green rounded rectangular button at the bottom center of the popup",
      "button occupies roughly 340x160 pixels in a 1080x1920 frame",
      "visible scale contraction in annotated frames 15-17, returning by frame 22",
      "no position change -- button stays anchored at bottom center"
    ],
    "presence_status": "tracked"
  }
}
```

---

## Key Takeaways

1. **Always start from the semantic object**, not from the track. Ask: "What should this object do?" before looking at track data.
2. **Reject by size first.** A 16x15px track cannot be a 340x160px button. Size mismatch is the fastest rejection criterion.
3. **Smooth noisy values.** The CV measured 0.94x scale, but the real animation is probably 0.95x. Use the CV data as a guide, not a blueprint.
4. **Explain rejections in `match_reason`.** The builder needs to understand why track_7 was NOT used for this object.
5. **Multi-sentence fields.** Both `match_reason` and `motion_summary` must be detailed enough for someone unfamiliar with the video to understand the matching logic.
