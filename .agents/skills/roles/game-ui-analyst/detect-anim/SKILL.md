---
name: detect-anim
description: "Analyse a screen-recorded video of a Unity UI animation (popup appear, heart refill, level complete, etc.) and generate animation_clips JSON with per-object keyframe tracks. Uses a 2-phase pipeline -- Python/OpenCV extracts motion data, then Claude performs semantic analysis matching tracks to objects from a detection JSON. Triggers on 'analyse animation', 'detect animation', 'extract animation', 'animation from video', 'video to animation', 'detect-anim'. Use this skill whenever the user has a screen recording of a UI animation and wants to extract structured animation data from it."
argument-hint: <video_path> <detection_json_path> [output_json_path]
---

**Quick Start:** Run CV pipeline on video -> read motion_data.json + detection JSON + frames -> match tracks to semantic objects -> produce animation_clips JSON (schema 6.1.0) -> hand off to `unity-animation-builder`.

---

Parse `$ARGUMENTS` as:
- `$0` -- video file path (.mov / .mp4)
- `$1` -- detection JSON path (semantic object list with id, category, bounding_box, canvas_position)
- `$2` -- output JSON path (optional; default: `$1` with `_anim.json` suffix)

## Architecture

```
Phase 1 -- Python/OpenCV (Bash)          Phase 2 -- Claude (semantic analysis)
+--------------------------+            +------------------------------+
| extract_motion.py        |            | Agent reads:                 |
|  1. Extract frames       |            |  - motion_data.json          |
|  2. Detect motion        |  ----->    |  - annotated_*.png           |
|  3. Segment blobs        |  output    |  - detection JSON            |
|  4. Track centroids      |  dir       |  - first/last raw frames     |
|  5. Compute transforms   |            |                              |
|  6. Save annotated PNGs  |            | Agent produces:              |
|     + motion_data.json   |            |  - animation_clips JSON      |
+--------------------------+            +------------------------------+
```

OpenCV handles pixel-level work (motion detection, tracking). Claude handles semantic reasoning (matching tracks to objects, easing, inferring static elements).

---

## Phase 1 -- Run the CV Pipeline

```bash
python "${CLAUDE_SKILL_DIR}/scripts/extract_motion.py" \
    "$0" \
    "/tmp/detect_anim_out" \
    --threshold 30 \
    --min-area 500 \
    --max-keyframes 20
```

**Output** in `/tmp/detect_anim_out/`:
- `motion_data.json` -- transforms, track summaries, video info
- `annotated_NNNN.png` -- keyframe images with bounding boxes and track IDs
- `frame_first.png` / `frame_last.png` -- raw start/end frames

If `cv2` is missing: `pip install opencv-python-headless numpy`

### Phase 1 Failure Recovery

| Symptom | Action |
|---|---|
| `cv2` not found | Install packages. If Python unavailable, ask for precomputed `motion_data.json` |
| 0 tracks | Compare first/last frames visually. Emit only inferred objects. Set `meta.phase1_quality: "no_tracks"` |
| 50+ noisy tracks | Rerun with `--threshold 50 --min-area 1000`. Ignore sub-5-frame tracks |
| OOM on long video | Ask user to trim to animation segment (<30s, moderate resolution) |
| Annotated frames unreadable | Use raw first/last frames + detection JSON positions. Lower confidence |

For detailed parameter tuning, read `references/cv-tuning.md`.

---

## Phase 2 -- Semantic Analysis

### Step 2.1 -- Read all inputs (parallel if possible)

1. `/tmp/detect_anim_out/motion_data.json`
2. `$1` -- detection JSON
3. `/tmp/detect_anim_out/frame_first.png` and `frame_last.png`
4. A few `annotated_*.png` files

Extract from `motion_data.json`: `video_info.fps`, `duration_sec`, `resolution`, `track_summary[]`, `transforms{}`.
Extract from detection JSON: `screens[0].objects[]`, `meta.to_canvas`.

### Step 2.2 -- Match tracks to semantic objects

**CRITICAL: Work semantic-object-first, not track-first.**

For each semantic object from the detection JSON:
1. Is it visually present in the video?
2. Does it have meaningful visible motion?
3. Which CV track(s) support it?
4. Should missing tracking be inferred from visual evidence?

**Matching strategy (priority order):**
1. Position overlap -- track `start_bbox` vs object `bounding_box`
2. Normalized center proximity
3. Size similarity
4. Motion hints alignment
5. Visual evidence from annotated frames

**Disposition rules:**
- Track matches one object -> `tracked`
- Multiple tracks for same object -> merge sequentially -> `tracked_merged`
- Object visible but no track -> classify as `inferred` (choose `inferred_static` or `inferred_attached` after visual review in Step 2.4)
- Track with no matching object -> list in `track_matching.unmatched_tracks`
- Detection JSON object not visible in video -> list in `track_matching.not_in_clip`

For a complete worked example of this reasoning, read `references/worked-example.md`.

### Step 2.3 -- Build animation clips

For each matched object:
1. Read transform data (position, scale per frame)
2. Convert frames to time: `time_sec = frame_idx / fps`
3. Reduce to 2-4 keyframes (max 6): start, peak, end
4. Determine easing from displacement curve shape (see heuristics below)

**Easing selection heuristics:**

| Displacement Curve Shape | Easing |
|---|---|
| Constant speed across frames | `"linear"` |
| Speed highest early, then decays | `"ease_out"` |
| Speed ramps from near-zero, then constant | `"ease_in"` |
| Speed ramps 0 -> peak -> 0 symmetrically | `"ease_in_out"` |
| Position overshoots target then settles | `"spring"` |
| Instant jump between frames | `"constant"` |

### Step 2.4 -- Handle objects without CV tracks

Objects that lack a CV track still need to be included if visible:

| Object Type | Inference Method |
|---|---|
| Dim overlay | Compare first/last frame for alpha change |
| Popup card | Infer scale/alpha from appearance/disappearance |
| Text labels | Usually animate with parent (`inferred_attached`) |
| Static containers | No animation -- minimal keyframes or skip |
| Sprite swaps (heart fill) | Infer from context -- CV can't detect texture changes |

### Step 2.5 -- Validate target paths (optional)

If MCP tools are available, validate `target.path` entries against the scene hierarchy:
1. `scene-list-opened` -> `scene-get-data` for hierarchy
2. `gameobject-find` for each path
3. Fix mismatches, log corrections

If MCP unavailable, set `target.path_validated: false` on all objects. The builder skill will resolve paths later.

---

## Semantic Analysis Rules

These 18 rules govern how you reason about CV data. Follow all of them.

**Priority order:**
1. Coverage of visible objects -- never drop a visible animated object
2. Correct semantic matching -- assign the right identity
3. Accurate motion reconstruction -- keyframes reflect real motion
4. Unity-compatible output -- valid component/property paths

### Object coverage (Rules 1-4)

- **R1 -- Never drop visible motion objects.** If visible and animated, include it -- even if noisy, brief, or small.
- **R2 -- Maximize semantic coverage.** Every visible detection object gets output. Weakly tracked -> inferred. Siblings -> output each separately.
- **R3 -- Repeated siblings stay separate.** `heart_0`, `heart_1`, `heart_2` each get their own entry.
- **R4 -- Attached children stay separate.** If a badge has its own detection ID and is visually distinct, output it separately from its parent.

### Track handling (Rules 5-9)

- **R5 -- Merge fragmented tracks.** Multiple tracks for same object -> merge sequentially. One entry per semantic object.
- **R6 -- Infer visible objects without tracks.** Use visual evidence, parent-child relationships, nearby objects. Mark as `inferred_static` or `inferred_attached`.
- **R7 -- Ignore jitter < 5px.** Do not create false translation keyframes from noise.
- **R8 -- Static vs Moving.** Static objects: no position keyframes (scale/opacity/rotation only). Moving objects: include position trajectory.
- **R9 -- Reduce keyframes.** 2-4 keyframes per object (max 6): start, peak, end.

### Output quality (Rules 10-14)

- **R10 -- Timeline.** Keyframe `time_sec` is relative to clip start. `total_duration_sec` = last keyframe time in longest track.
- **R11 -- Loop type.** `false` for one-shot (default), `true` for continuous loops.
- **R12 -- Unity compatibility.** Target real component properties (`RectTransform.localScale`, `CanvasGroup.m_Alpha`, etc.). See `references/schema.md` for the full property reference.
- **R13 -- Validate motion.** If detected motion contradicts expected behavior (icon teleports, button jumps), assume tracking error and correct with semantic reasoning.
- **R14 -- Match evidence required.** Every entry needs `source_evidence` with: `track_ids`, `match_confidence` (0.0-1.0), `match_reason` (detailed, multi-sentence), `visual_evidence` (concrete cues), `presence_status`.

### Semantics and relationships (Rules 15-18)

- **R15 -- Motion semantics required.** Every entry needs: `source_category` (raw from detection JSON), `object_category` (animation role enum), `motion_type`, `animation_type`, `motion_summary` (detailed, multi-sentence), `relationships[]`.
- **R16 -- UI state animations count.** Fill changes, pulses, opacity changes, badge appearances are real animations -- do not classify as static.
- **R17 -- Small objects matter.** Small size is not a reason to omit. Badges, icons, heart badges must be included if visible.
- **R18 -- Best-match policy.** If ambiguous: choose best match, keep the object, lower confidence, explain ambiguity. Transfer animations need both `moves_to` and `causes_state_change`/`fills` relationships.

---

## Output

Write JSON to `$2` with `"schema": "6.1.0"`.

For the complete schema, field definitions, enum tables, and validation checklist, read `references/schema.md`.
For a self-consistent example output, read `references/example-output.json`.

### Key schema changes in v6.1.0 (vs 6.0.0)

- Added `source_category` field (raw detection JSON category) alongside `object_category` (animation role enum)
- Added `target.path_validated` boolean
- Added `meta.phase1_quality` and `meta.scene_validation` fields
- Added `track_matching.not_in_clip[]` for detection objects absent from video
- Relationship field standardized as `explanation` (not `relationship_explanation`)

### Output summary (print after saving)

```
Saved: <path> (schema 6.1.0)
Animated objects: N | Tracked: N | Inferred: N | Not in clip: N
Unmatched CV tracks: N
Sequences: N
```

Then print an objects table and relationships summary.

---

## Handoff to Builder

The output JSON is consumed by `unity-animation-builder`. The builder expects:

| Section | Required | Notes |
|---|---|---|
| `animated_objects[]` | Yes | Core animation data |
| `easing_library` | Yes | `prime_tween_ease` field maps to PrimeTween.Ease |
| `meta` | Yes | Canvas config, scene info |
| `animation_sequences[]` | No | If present, builder uses for orchestration |
| `scene_wiring` | No | Hints for GO creation |
| `track_matching` | No | Diagnostic info |

If any `path_validated: false`, the builder will run MCP path resolution before proceeding.

---

## References

| File | Content | When to read |
|---|---|---|
| `references/schema.md` | Full JSON schema, field definitions, enum tables, validation checklist | When building output JSON |
| `references/worked-example.md` | Complete matching walkthrough (track -> object -> JSON) | First time using this skill, or when matching is ambiguous |
| `references/example-output.json` | Self-consistent valid sample output | When you need a template to follow |
| `references/cv-tuning.md` | Parameter tuning, failure recovery, CV limitations | When Phase 1 gives bad results |

---

## Related Skills

| Need | Skill                                               |
|---|-----------------------------------------------------|
| Validate target paths against live scene | `develop-unity-ui` (scene-get-data, gameobject-find) |
| uGUI hierarchy conventions | `unity-ui`                                          |
| Build Unity animations from this output | `build-anim`                                 |
| PrimeTween easing reference | `unity-ui-animation`                                |

---

## Project Conventions

- **Namespaces**: All game code under `Game.*`
- **Canvas**: 1080x1920, ScaleWithScreenSize, Match 0.5, ScreenSpaceOverlay
- **Animation**: PrimeTween v1.3.7 -- `prime_tween_ease` maps to `PrimeTween.Ease` enum
- **Async**: UniTask -- builder uses `await sequence.ToUniTask()`
