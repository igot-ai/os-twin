#!/usr/bin/env python3
"""
extract_motion.py — CV pipeline for UI animation detection.

Runs OpenCV steps 1-5 (extract → motion → segments → track → transforms),
then saves:
  1. transforms.json        — per-track position/scale deltas
  2. track_summary.json     — human-readable track overview
  3. annotated_NNN.png      — keyframe images with red bounding boxes

The agent reads these outputs to perform the semantic analysis step.

Usage:
    python extract_motion.py <video_path> <output_dir> [--threshold 30] [--min-area 500]
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

from cv_processor import OpenCVProcessor


def select_keyframe_indices(
    transforms: dict, total_frames: int, max_keyframes: int = 20
) -> list:
    """
    Pick a representative subset of frame indices where motion happens.
    Caps at max_keyframes to keep annotated image count manageable for the agent.
    Always includes the first frame and the last frame of the video.
    """
    indices = set()

    # Collect all frame indices across all tracks
    for tid, tlist in transforms.items():
        for t in tlist:
            indices.add(t["frame_idx"])

    # Always include first and last frame
    indices.add(0)
    indices.add(total_frames - 1)

    sorted_idx = sorted(indices)

    # Downsample if too many
    if len(sorted_idx) > max_keyframes:
        step = len(sorted_idx) / float(max_keyframes)
        sampled = [sorted_idx[int(i * step)] for i in range(max_keyframes)]
        # Ensure first and last are included
        if 0 not in sampled:
            sampled[0] = 0
        if (total_frames - 1) not in sampled:
            sampled[-1] = total_frames - 1
        sorted_idx = sorted(set(sampled))

    return sorted_idx


def build_track_summary(
    transforms: dict, fps: float, frame_width: int, frame_height: int
) -> list:
    """
    Build a concise per-track summary for the agent to read quickly.
    Each entry: track_id, first/last frame, duration, total displacement,
    bounding box at start/end, etc.
    """
    summaries = []
    for tid, tlist in transforms.items():
        if not tlist:
            continue
        first = tlist[0]
        last = tlist[-1]
        total_dx = last["position"][0]
        total_dy = last["position"][1]
        total_disp = (total_dx**2 + total_dy**2) ** 0.5

        avg_scale_x = sum(t["scale"][0] for t in tlist) / len(tlist)
        avg_scale_y = sum(t["scale"][1] for t in tlist) / len(tlist)
        max_scale_x = max(t["scale"][0] for t in tlist)
        min_scale_x = min(t["scale"][0] for t in tlist)

        summaries.append(
            {
                "track_id": tid,
                "frame_range": [first["frame_idx"], last["frame_idx"]],
                "duration_sec": round((last["frame_idx"] - first["frame_idx"]) / fps, 3),
                "start_time_sec": round(first["frame_idx"] / fps, 3),
                "num_frames": len(tlist),
                "start_bbox": first["abs_bbox"],
                "end_bbox": last["abs_bbox"],
                "total_displacement_px": round(total_disp, 1),
                "delta_position": [round(total_dx, 1), round(total_dy, 1)],
                "scale_range": [round(min_scale_x, 3), round(max_scale_x, 3)],
                "avg_scale": [round(avg_scale_x, 3), round(avg_scale_y, 3)],
                "motion_type_hint": classify_motion(total_disp, min_scale_x, max_scale_x, len(tlist)),
                "normalized_start_center": [
                    round(first["abs_bbox"][0] + first["abs_bbox"][2] / 2, 1) / frame_width,
                    round(first["abs_bbox"][1] + first["abs_bbox"][3] / 2, 1) / frame_height,
                ],
            }
        )

    # Sort by start time
    summaries.sort(key=lambda s: s["start_time_sec"])
    return summaries


def classify_motion(
    displacement: float, min_scale: float, max_scale: float, num_frames: int
) -> str:
    """
    Quick heuristic classification for the agent's benefit.
    Not authoritative — agent makes the final call.
    """
    has_translation = displacement > 15
    has_scale = (max_scale - min_scale) > 0.08
    is_brief = num_frames < 8

    if has_translation and has_scale:
        return "compound (translation + scale)"
    if has_translation:
        return "translation"
    if has_scale:
        return "scale_pulse" if is_brief else "scale_change"
    return "minimal_or_static"


def main():
    parser = argparse.ArgumentParser(
        description="Run CV pipeline on a UI animation video."
    )
    parser.add_argument("video", help="Path to the video file (.mov/.mp4)")
    parser.add_argument("outdir", help="Output directory for transforms + annotated frames")
    parser.add_argument("--threshold", type=int, default=30, help="Motion pixel threshold (default: 30)")
    parser.add_argument("--min-area", type=int, default=500, help="Minimum motion area in pixels (default: 500)")
    parser.add_argument("--max-track-dist", type=int, default=150, help="Max centroid distance for tracking (default: 150)")
    parser.add_argument("--min-track-frames", type=int, default=3, help="Min frames for a track to survive (default: 3)")
    parser.add_argument("--max-keyframes", type=int, default=20, help="Max annotated keyframe images to save (default: 20)")
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Error: video file not found: {args.video}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    # ── Initialize processor ────────────────────────────────────────────────
    cv = OpenCVProcessor(
        motion_threshold=args.threshold,
        min_motion_area=args.min_area,
        max_track_distance=args.max_track_dist,
        min_track_frames=args.min_track_frames,
    )
    fps = cv.get_video_fps(args.video)

    # ── Step 1: Extract frames ──────────────────────────────────────────────
    print(f"Step 1/5: Extracting frames from {args.video}...")
    frames = cv.extract_frames(args.video)
    if not frames:
        print("Error: no frames extracted.")
        sys.exit(1)
    h, w = frames[0].shape[:2]
    print(f"  -> {len(frames)} frames ({w}x{h}) at {fps:.1f} fps ({len(frames)/fps:.2f}s)")

    # ── Step 2: Detect motion ───────────────────────────────────────────────
    print("Step 2/5: Detecting motion...")
    motion_data = cv.detect_motion(frames)
    print(f"  -> Motion in {len(motion_data)} frames")

    # ── Step 3: Detect segments ─────────────────────────────────────────────
    print("Step 3/5: Segmenting motion blobs...")
    segments = cv.detect_segments(frames, motion_data)
    print(f"  -> {len(segments)} segment frames")

    # ── Step 4: Track objects ───────────────────────────────────────────────
    print("Step 4/5: Tracking objects across frames...")
    tracked = cv.track_objects(frames, segments)
    print(f"  -> {len(tracked)} tracks (after noise filter)")

    # ── Step 5: Extract transforms ──────────────────────────────────────────
    print("Step 5/5: Computing transforms...")
    transforms = cv.extract_transforms(tracked)
    print(f"  -> {len(transforms)} transform tracks")

    # ── Select keyframes and render annotated images ────────────────────────
    key_indices = select_keyframe_indices(transforms, len(frames), args.max_keyframes)
    annotated = cv.render_annotated_frames(frames, transforms, key_indices)

    for i, (fidx, img) in enumerate(zip(key_indices, annotated)):
        path = os.path.join(args.outdir, f"annotated_{fidx:04d}.png")
        cv2.imwrite(path, img)

    # ── Save first and last raw frames (unannotated) for context ────────────
    cv2.imwrite(os.path.join(args.outdir, "frame_first.png"), frames[0])
    cv2.imwrite(os.path.join(args.outdir, "frame_last.png"), frames[-1])

    # ── Clean transforms for JSON (remove abs_bbox from LLM-facing data) ───
    clean_transforms = {}
    for tid, tlist in transforms.items():
        clean_transforms[tid] = [
            {k: v for k, v in t.items() if k != "abs_bbox"} for t in tlist
        ]

    # ── Build track summary ─────────────────────────────────────────────────
    track_summary = build_track_summary(transforms, fps, w, h)

    # ── Save outputs ────────────────────────────────────────────────────────
    output = {
        "video_path": args.video,
        "video_info": {
            "fps": round(fps, 2),
            "total_frames": len(frames),
            "duration_sec": round(len(frames) / fps, 3),
            "resolution": {"width": w, "height": h},
        },
        "cv_params": {
            "motion_threshold": args.threshold,
            "min_motion_area": args.min_area,
            "max_track_distance": args.max_track_dist,
            "min_track_frames": args.min_track_frames,
        },
        "track_summary": track_summary,
        "transforms": clean_transforms,
        "keyframe_indices": key_indices,
        "annotated_frame_paths": [
            f"annotated_{fidx:04d}.png" for fidx in key_indices
        ],
    }

    json_path = os.path.join(args.outdir, "motion_data.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)

    # ── Print summary ───────────────────────────────────────────────────────
    print(f"\n=== CV Pipeline Complete ===")
    print(f"Video       : {args.video}")
    print(f"Resolution  : {w}x{h} @ {fps:.1f}fps")
    print(f"Duration    : {len(frames)/fps:.2f}s ({len(frames)} frames)")
    print(f"Tracks found: {len(transforms)}")
    print(f"Keyframes   : {len(key_indices)} annotated images saved")
    print(f"Output dir  : {args.outdir}")
    print(f"Motion JSON : {json_path}")
    print()
    for s in track_summary:
        print(
            f"  {s['track_id']:12s}  "
            f"t={s['start_time_sec']:.2f}–{s['start_time_sec']+s['duration_sec']:.2f}s  "
            f"disp={s['total_displacement_px']:6.1f}px  "
            f"scale={s['scale_range'][0]:.2f}–{s['scale_range'][1]:.2f}  "
            f"hint={s['motion_type_hint']}"
        )


if __name__ == "__main__":
    main()
