---
name: Add UI Animation
description: Create UI animations from a reference video using detect-anim → build-anim pipeline.
version: 1.0.0
category: Implementation
applicable_roles: [game-engineer, engineer]
tags: [engineer, implementation, unity, animation, ui]

source: project
author: Agent OS Core
---

## Preconditions
- Reference video (.mp4/.mov) of the target UI animation is available.
- Detection JSON (output of `detect-ui`) describing the scene's object hierarchy is available.
- Target scene is open in Unity Editor.
- GDD or design doc is available (optional — provides game mechanic context).

## Steps

1. **Detect**: Run `../detect-anim` skill on the reference video.
   - Input: `<path/to/video.mp4> <path/to/detection.json> [output_json_path]`
   - Output: `animation_detection.json` with per-object keyframe tracks (position, scale, opacity, timing, easing).
   - Read the output JSON to understand the animated objects before proceeding.

2. **Review**: Inspect the `animation_detection.json` object list. Cross-reference with the scene hierarchy to confirm which GameObjects correspond to which animated objects. Note:
   - Objects in the JSON are **references** — generalise to all similar objects in the scene.
   - Identify object categories: interactive elements, containers, effects, text feedback.

3. **Build**: Run `../build-anim` skill to implement the animations.
   - Input: `<animation_detection.json> <reference_video> [gdd_path] [scene_name]`
   - This writes C# coroutine scripts, creates supporting GameObjects, wires everything via MCP tools.

4. **Play Mode Validation**: Enter Play Mode and verify:
   - Zero runtime errors in console.
   - Interactive elements respond to clicks (EventSystem + correct InputModule present).
   - Animation sequences play correctly (pickup, fly, match, effects, text feedback).
   - Fix any runtime bugs and re-test until clean.

5. **Final Gate**: Execute `validation-and-review` workflow.

## Output
- `animation_detection.json` detection file describing all animated objects and keyframes.
- C# coroutine scripts under `Assets/Game/Scripts/Animation/`.
- Scene GameObjects wired with animation scripts, supporting GOs, and EventSystem.
- Zero compile and runtime errors confirmed via Play Mode test.
