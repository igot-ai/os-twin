---
name: game-ui-analytics-pipeline
description: End-to-end Game UI analytics pipeline for Unity UI. Orchestrates detect-ui and detect-anim into a unified analysis with cross-validation. Takes screenshot + video → produces detection JSON, animation JSON, and a validated analytics report.
argument-hint: <screenshot_path> [video_path] [real_bg_asset_path] [output_dir]
allowed-tools: Read, Write, Glob, Grep, Bash
---

End-to-end computer vision analytics pipeline for Unity UI screens.

Parse `$ARGUMENTS` as:
- `$0` — screenshot / reference image path (required) — used for UI detection
- `$1` — video path (.mov/.mp4) — for animation detection (optional — omit for static-only analysis)
- `$2` — real background asset path OR output directory (optional)
- `$3` — output directory (only when `$2` is a background asset)

If `$1` ends with `.json` → it is an **existing detection JSON** — skip Step 1 and use it directly.

Default output directory: same directory as `$0`.

---

## Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    game-ui-analytics-analytics Pipeline                             │
│                                                                      │
│  Inputs: screenshot.png + animation.mov + [bg_asset.png]            │
│                                                                      │
│  ┌─────────────────────┐    ┌──────────────────────────────┐        │
│  │ Step 1              │    │ Step 2                       │        │
│  │ UI DETECTION        │    │ CV MOTION EXTRACTION         │        │
│  │                     │    │                              │        │
│  │ Rules from:         │    │ Script from:                 │        │
│  │ /detect-ui/SKILL.md │    │ /detect-anim/scripts/        │        │
│  │                     │    │ extract_motion.py            │        │
│  │ screenshot ──→      │    │ video ──→                    │        │
│  │   detection.json    │    │   motion_data.json           │        │
│  │                     │    │   annotated_*.png            │        │
│  │                     │    │   frame_first/last.png       │        │
│  └────────┬────────────┘    └─────────────┬────────────────┘        │
│           │                               │                          │
│           └──────────┐   ┌────────────────┘                          │
│                      ▼   ▼                                           │
│           ┌──────────────────────────────┐                           │
│           │ Step 3                       │                           │
│           │ ANIMATION SEMANTIC ANALYSIS  │                           │
│           │                              │                           │
│           │ Rules from:                  │                           │
│           │ /detect-anim/SKILL.md        │                           │
│           │ (Phase 2 + Rules 1-18)       │                           │
│           │                              │                           │
│           │ detection.json + motion_data │                           │
│           │ + annotated frames ──→       │                           │
│           │   animation.json             │                           │
│           └─────────────┬────────────────┘                           │
│                         ▼                                            │
│           ┌──────────────────────────────┐                           │
│           │ Step 4                       │                           │
│           │ CROSS-VALIDATION             │                           │
│           │                              │                           │
│           │ Unique to cv-analytics:      │                           │
│           │ • object coverage check      │                           │
│           │ • confidence distribution    │                           │
│           │ • track utilization          │                           │
│           │ • consistency verification   │                           │
│           └─────────────┬────────────────┘                           │
│                         ▼                                            │
│           ┌──────────────────────────────┐                           │
│           │ Step 5                       │                           │
│           │ UNIFIED ANALYTICS REPORT     │                           │
│           │                              │                           │
│           │ Merge: detection + animation │                           │
│           │        + validation          │                           │
│           │ Output: *_analytics.json     │                           │
│           └──────────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Modes

Detect which mode to run based on arguments:

| Mode | Condition | Steps Run |
|---|---|---|
| **Full pipeline** | `$0` = screenshot AND `$1` = video file | 1 → 2 → 3 → 4 → 5 |
| **Static-only** | `$0` = screenshot, no `$1` | 1 → 4 → 5 (no animation) |
| **Anim-only** | `$0` = screenshot AND `$1` = existing `.json` AND video provided as `$2` | 2 → 3 → 4 → 5 (use existing detection) |
| **Resume from detection** | `$1` = existing `.json` AND `$2` = video | Skip 1, run 2 → 3 → 4 → 5 |

---

## Step 1 — UI Detection

**Read and follow all rules from:** `.claude/skills/detect-ui/SKILL.md`

This step produces the **detection JSON** — the semantic object list that all subsequent steps depend on.

### Input
- `$0` — the screenshot / reference image
- `$2` — real background asset (if provided)

### What to do
Follow the detect-ui skill fully:
1. Classify background (source_role, scene_background type)
2. Read the image and measure source resolution
3. Detect all UI objects back → front (z-order)
4. For each object: measure bounding_box, compute canvas_position/canvas_size, find sprite, determine unity_component, parent_id, interaction
5. Fill spatial_layout for repeated groups
6. Validate against detect-ui checklist
7. Write detection JSON

### Output
- `<output_dir>/<name>_detection.json`

### Key schema fields from detect-ui
- `meta.source_role`, `meta.scene_background`, `meta.to_canvas`
- `screens[i].objects[j]` — each with `id`, `category`, `bounding_box`, `canvas_position`, `canvas_size`, `parent_id`, `z_index`, `unity_component`, etc.
- `spatial_layout`, `missing_assets`, `summary`

**After Step 1: verify** the detection JSON passes detect-ui's validation checklist before proceeding.

---

## Step 2 — CV Motion Extraction

**Skip this step if no video was provided (static-only mode).**

This step runs the Python/OpenCV pipeline from detect-anim's scripts.

### Input
- Video file path (`.mov` / `.mp4`)

### Run via Bash

```bash
python ".claude/skills/detect-anim/scripts/extract_motion.py" \
    "<video_path>" \
    "/tmp/cv_analytics_out" \
    --threshold 30 \
    --min-area 500 \
    --max-keyframes 20
```

If the script fails (missing `cv2`), install: `pip install opencv-python-headless numpy`

### Output (in `/tmp/cv_analytics_out/`)
- `motion_data.json` — transforms, track summaries, video info
- `annotated_NNNN.png` — keyframe images with red bounding boxes + track IDs
- `frame_first.png` — raw first frame (before animation)
- `frame_last.png` — raw last frame (after animation)

### Quick validation
- Read terminal output for track count
- If 0 tracks found → the video may have no motion, or threshold is too high. Try `--threshold 20 --min-area 300`

---

## Step 3 — Animation Semantic Analysis

**Skip this step if no video was provided (static-only mode).**

**Read and follow all rules from:** `.claude/skills/detect-anim/SKILL.md` — specifically **Phase 2** (Steps 2.1–2.5) and **all 18 Semantic Analysis Rules**.

### Input
Read these files (in parallel if possible):
1. `/tmp/cv_analytics_out/motion_data.json` — CV motion data (from Step 2)
2. Detection JSON (from Step 1) — semantic object list
3. `/tmp/cv_analytics_out/frame_first.png` — starting state
4. `/tmp/cv_analytics_out/frame_last.png` — ending state
5. Several `annotated_*.png` files — tracked bounding boxes

### What to do
Follow detect-anim's Phase 2 + Rules 1-18:
1. **Step 2.1** — Read all inputs
2. **Step 2.2** — Understand video_info, track_summary, transforms, detection objects
3. **Step 2.3** — Match tracks to semantic objects (**semantic-object-first, not track-first**)
4. **Step 2.4** — Build animation clips (2-4 keyframes per object, proper easing)
5. **Step 2.5** — Handle objects without tracks (inferred_static, inferred_attached)

### Critical rules to enforce (from detect-anim)
- **Rule 1**: Do NOT drop visible motion objects
- **Rule 3**: Repeated siblings output separately (heart_0, heart_1, heart_2)
- **Rule 7**: Jitter < 5px = noise, do NOT create false keyframes
- **Rule 8**: Static objects: no position in keyframes. Moving objects: position in keyframes.
- **Rule 14**: Every track needs detailed `match_reason` + `visual_evidence` + `match_confidence`
- **Rule 15**: Every track needs `object_category` (from detection JSON), `motion_type`, `animation_type`, `motion_summary`, `relationships`
- **Rule 18**: Transfer animations need both `moves_to` AND `causes_state_change`/`fills`

### Output
- `<output_dir>/<name>_anim.json`

Follow detect-anim's full output schema (meta, animation_clips, track_matching).

---

## Step 4 — Cross-Validation

**This step is unique to cv-analytics.** It verifies consistency between the detection and animation outputs.

### 4.1 — Object Coverage Check

For every object in `detection.json → screens[0].objects[]`:

| Object status | Meaning | Expected location in animation JSON |
|---|---|---|
| **Animated** | Object has CV tracks or inferred animation | In `animation_clips[].tracks[]` |
| **Inferred static** | Object visible but no animation | In `track_matching.inferred_objects[]` |
| **Not visible in video** | Object from detection but absent in video | Flag as `not_in_video` |

**Coverage metric:**
```
object_coverage = (animated + inferred) / total_detection_objects
```

Target: `object_coverage ≥ 0.90` — if below, investigate missing objects.

### 4.2 — ID Consistency Check

Verify:
- Every `object_id` in animation tracks exists in detection objects
- Every `object_id` in `track_matching.matched_tracks` exists in detection objects
- Every `object_id` in `track_matching.inferred_objects` exists in detection objects
- No unknown IDs appear in animation output

Flag mismatches as errors.

### 4.3 — Confidence Distribution

Compute:
```
avg_confidence = mean(all track match_confidence values)
low_confidence_count = count(confidence < 0.60)
high_confidence_count = count(confidence ≥ 0.90)
```

Flag if `low_confidence_count > 30%` of total tracks.

### 4.4 — Track Utilization

```
cv_tracks_total = count(all tracks from motion_data.json)
cv_tracks_matched = count(track_matching.matched_tracks)
cv_tracks_unmatched = count(track_matching.unmatched_tracks)
track_utilization = cv_tracks_matched / cv_tracks_total
```

Flag if `track_utilization < 0.50` — most CV tracks should match semantic objects.

### 4.5 — Geometry Consistency

For tracked objects, verify:
- Track `start_bbox` overlaps with detection object's `bounding_box` (IoU > 0.3)
- Track displacement direction is plausible for the object type
- Scale changes are within reasonable range (0.1 – 5.0)

### 4.6 — Relationship Consistency

For objects with `relationships`:
- Every `target_object_id` must exist in detection objects
- `moves_to` targets should have plausible positions (fly-target objects exist)
- `contained_in` targets should have larger bounding boxes than the child
- `attached_to` targets should overlap or be adjacent

### 4.7 — Temporal Consistency

- All keyframe `time_sec` values are within `[0, video_duration]`
- `total_duration_sec` ≤ video_duration
- No object has keyframes after `total_duration_sec`
- Staggered animations (sibling fills) have monotonically increasing start times

---

## Step 5 — Unified Analytics Report

Merge detection + animation + validation into one `*_analytics.json`.

### Output Schema

```jsonc
{
  "meta": {
    "pipeline_version": "1.0.0",
    "mode": "full",                    // "full" | "static_only" | "anim_only"
    "timestamp": "2026-03-16T...",
    "inputs": {
      "screenshot": "$0",
      "video": "$1 or null",
      "bg_asset": "$2 or null"
    },
    "outputs": {
      "detection_json": "<path>",
      "animation_json": "<path> or null",
      "analytics_json": "<path>"
    }
  },

  // ── Full detection output (from Step 1) ───────────────────────────
  "detection": {
    // ... entire detection JSON contents (meta, screens, spatial_layout, etc.)
    // Embedded verbatim — the analytics file is self-contained
  },

  // ── Full animation output (from Step 3, null if static-only) ──────
  "animation": {
    // ... entire animation JSON contents (animation_clips, track_matching, etc.)
    // null if static-only mode
  },

  // ── Cross-validation results (from Step 4) ────────────────────────
  "validation": {
    "status": "pass",              // "pass" | "warn" | "fail"
    "errors": [],                  // list of error strings
    "warnings": [],                // list of warning strings

    "object_coverage": {
      "total_detection_objects": 13,
      "animated_objects": 8,
      "inferred_static_objects": 4,
      "not_in_video_objects": 1,
      "coverage_ratio": 0.92,
      "missing_objects": [
        {
          "object_id": "hud_life_container",
          "reason": "HUD element not visible in popup video recording"
        }
      ]
    },

    "id_consistency": {
      "valid": true,
      "unknown_ids": [],           // IDs in animation not in detection
      "orphaned_ids": []           // IDs in detection not accounted for in animation
    },

    "confidence_distribution": {
      "avg_confidence": 0.87,
      "min_confidence": 0.65,
      "max_confidence": 0.98,
      "low_confidence_count": 1,   // < 0.60
      "high_confidence_count": 9,  // ≥ 0.90
      "distribution": {
        "0.90-1.00": 9,
        "0.80-0.89": 2,
        "0.60-0.79": 1,
        "0.40-0.59": 0,
        "0.00-0.39": 0
      }
    },

    "track_utilization": {
      "cv_tracks_total": 12,
      "cv_tracks_matched": 10,
      "cv_tracks_unmatched": 2,
      "utilization_ratio": 0.83
    },

    "temporal_consistency": {
      "valid": true,
      "video_duration_sec": 3.0,
      "clip_duration_sec": 3.0,
      "issues": []
    }
  },

  // ── Per-object unified view ───────────────────────────────────────
  "objects": [
    {
      // Merged view: detection fields + animation fields per object
      "object_id":        "btn_refill_green",
      "name":             "Green Refill Button",
      "category":         "UI/Button",
      "unity_component":  "Button",

      // From detection
      "canvas_position":  { "x": 0, "y": -280 },
      "canvas_size":      { "width": 380, "height": 100 },
      "sprite_source":    "Assets/UI/Revive/btn_next_green_.png",
      "parent_id":        "popup_base_cream",
      "z_index":          6,

      // From animation (null if static-only)
      "has_animation":    true,
      "motion_type":      "scale",
      "animation_type":   "tap_feedback",
      "motion_summary":   "Button dips to 95% scale on press...",
      "track_ids":        ["track_3"],
      "match_confidence": 0.92,
      "presence_status":  "tracked",
      "keyframe_count":   3,
      "time_range_sec":   [0.00, 0.30],
      "relationships": [
        {
          "type": "activates",
          "target_object_id": "heart_empty_0",
          "relationship_explanation": "..."
        }
      ]
    }
    // ... one entry per detection object
  ],

  // ── Pipeline summary ──────────────────────────────────────────────
  "summary": {
    "total_objects":            13,
    "objects_with_animation":   8,
    "objects_inferred_static":  4,
    "objects_not_in_video":     1,
    "animation_clips_count":   1,
    "total_tracks":            12,
    "avg_confidence":          0.87,
    "validation_status":       "pass",
    "missing_assets_count":    2,
    "pipeline_mode":           "full"
  }
}
```

---

## Skill References

This skill orchestrates two sub-skills. During execution, read their full SKILL.md for detailed rules:

| Step | Sub-skill | SKILL.md Path | What to read |
|---|---|---|---|
| Step 1 | detect-ui | `.claude/skills/detect-ui/SKILL.md` | Full file — all sections |
| Step 2 | detect-anim (scripts) | `.claude/skills/detect-anim/scripts/extract_motion.py` | Run via Bash |
| Step 3 | detect-anim (rules) | `.claude/skills/detect-anim/SKILL.md` | Phase 2 (Steps 2.1–2.5) + Semantic Analysis Rules (1-18) + Output Schema + all enum tables |

**Before starting each step**, read the referenced SKILL.md to load the full rules into context.

---

## Intermediate File Locations

| File | Produced by | Used by | Path |
|---|---|---|---|
| `*_detection.json` | Step 1 | Steps 3, 4, 5 | `<output_dir>/<name>_detection.json` |
| `motion_data.json` | Step 2 | Step 3 | `/tmp/cv_analytics_out/motion_data.json` |
| `annotated_*.png` | Step 2 | Step 3 | `/tmp/cv_analytics_out/annotated_*.png` |
| `frame_first.png` | Step 2 | Step 3 | `/tmp/cv_analytics_out/frame_first.png` |
| `frame_last.png` | Step 2 | Step 3 | `/tmp/cv_analytics_out/frame_last.png` |
| `*_anim.json` | Step 3 | Steps 4, 5 | `<output_dir>/<name>_anim.json` |
| `*_analytics.json` | Step 5 | Final output | `<output_dir>/<name>_analytics.json` |

---

## Validation Checklist (Final — before writing analytics.json)

### From detect-ui (Step 1)
- [ ] `source_role` is valid
- [ ] `scene_background.type` is valid
- [ ] Every `parent_id` references a valid `id`
- [ ] All `bounding_box` values within source resolution
- [ ] `canvas_position` and `canvas_size` match `meta.to_canvas` formulas

### From detect-anim (Step 3)
- [ ] Every `object_id` in tracks references a valid `id` from detection
- [ ] `total_duration_sec` equals last keyframe in longest track
- [ ] Keyframe `time_sec` values are monotonically increasing
- [ ] No track has more than 6 keyframes
- [ ] Every track has `object_category`, `motion_type`, `animation_type`
- [ ] Every track has `motion_summary` and `relationships`
- [ ] `source_evidence` has `match_reason` (detailed), `visual_evidence`, `presence_status`
- [ ] Repeated siblings output separately
- [ ] Jitter < 5px not turned into false keyframes

### From cv-analytics (Step 4)
- [ ] `object_coverage.coverage_ratio` ≥ 0.90 (warn if below)
- [ ] `id_consistency.valid` is true (error if false)
- [ ] `confidence_distribution.low_confidence_count` < 30% of total tracks (warn if above)
- [ ] `track_utilization.utilization_ratio` ≥ 0.50 (warn if below)
- [ ] `temporal_consistency.valid` is true (error if false)
- [ ] Every detection object appears in `objects[]` unified view
- [ ] `validation.status` correctly reflects errors/warnings:
  - Any error → `"fail"`
  - Any warning, no errors → `"warn"`
  - No issues → `"pass"`

---

## Output Summary (print after saving)

```
═══════════════════════════════════════════════════════
  CV Analytics Pipeline — Complete
═══════════════════════════════════════════════════════

Mode                   : <full | static_only | anim_only>
Validation status      : <pass ✅ | warn ⚠️ | fail ❌>

── Step 1: UI Detection ──────────────────────────────
Objects detected       : <N>
Background type        : <scene_background.type>
Assets matched         : <N>
Missing assets         : <N>

── Step 2: CV Motion ─────────────────────────────────
CV tracks found        : <N>
Video duration         : <N>s @ <fps> fps
Keyframes annotated    : <N>

── Step 3: Animation Analysis ────────────────────────
Animation clips        : <N>
Tracks generated       : <N>
Objects animated       : <N> / <total>
  tracked (CV match)   : <N>
  inferred (no CV)     : <N>

── Step 4: Cross-Validation ──────────────────────────
Object coverage        : <ratio> (<N> / <total>)
ID consistency         : <valid ✅ | invalid ❌>
Avg confidence         : <float>
Track utilization      : <ratio>
Temporal consistency   : <valid ✅ | invalid ❌>

── Output Files ──────────────────────────────────────
Detection JSON         : <path>
Animation JSON         : <path>
Analytics JSON         : <path>
═══════════════════════════════════════════════════════
```

Then the per-object unified table:

| object_id | category | has_anim | animation_type | confidence | status | time range |
|---|---|---|---|---|---|---|
| dim_overlay | UI/Overlay | ✓ | fade_out | 0.85 | inferred_static | 0.00–1.80s |
| popup_border_red | UI/Container | ✓ | popup_exit | 0.94 | tracked | 0.00–1.80s |
| btn_refill_green | UI/Button | ✓ | tap_feedback | 0.92 | tracked | 0.00–0.30s |
| heart_empty_0 | UI/Icon | ✓ | compound | 0.88 | tracked | 0.30–2.90s |
| heading_text | UI/Text | — | — | — | inferred_attached | — |
| … | … | … | … | … | … | … |

Validation issues (if any):

```
⚠️ Warning: object_coverage 0.85 < 0.90 threshold
   Missing: hud_life_container (not visible in video recording)

⚠️ Warning: track_8 unmatched — brief 4-frame noise near screen edge
```
