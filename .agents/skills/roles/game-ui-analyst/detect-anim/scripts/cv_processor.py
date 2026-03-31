"""
CV processor for UI animation detection.
Adapted from physical_motion/cv_processor.py for Unity UI video analysis.

Extracts frames from video, detects motion regions, tracks objects across frames,
and computes transform deltas — all using OpenCV. No LLM calls here; the semantic
analysis is done by the AI agent following the SKILL.md instructions.
"""

import cv2
import numpy as np
import math
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class BaseCVProcessor(ABC):
    """Abstract interface for computer vision processing."""

    @abstractmethod
    def extract_frames(self, video_path: str) -> List[np.ndarray]:
        pass

    @abstractmethod
    def detect_motion(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def detect_segments(
        self, frames: List[np.ndarray], motion_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def track_objects(
        self, frames: List[np.ndarray], segments: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        pass

    @abstractmethod
    def extract_transforms(
        self, tracked_objects: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        pass


class OpenCVProcessor(BaseCVProcessor):
    """
    OpenCV-based frame extraction, motion detection, object tracking, and
    transform computation.  Tuned for mobile-game UI recordings at ~30 fps.
    """

    def __init__(
        self,
        motion_threshold: int = 30,
        min_motion_area: int = 500,
        max_track_distance: int = 150,
        min_track_frames: int = 3,
    ):
        self.motion_threshold = motion_threshold
        self.min_motion_area = min_motion_area
        self.max_track_distance = max_track_distance
        self.min_track_frames = min_track_frames

    # ── Frame extraction ────────────────────────────────────────────────────

    def extract_frames(self, video_path: str) -> List[np.ndarray]:
        """Read every frame from a video file into memory (BGR numpy arrays)."""
        cap = cv2.VideoCapture(video_path)
        frames: List[np.ndarray] = []
        if not cap.isOpened():
            print(f"Error: cannot open video {video_path}")
            return frames
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        return frames

    def get_video_fps(self, video_path: str) -> float:
        """Return the FPS of the video file, defaulting to 30."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.release()
        return fps

    # ── Motion detection ────────────────────────────────────────────────────

    def detect_motion(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
        """
        Frame-differencing algorithm:
        1. Convert consecutive frames to greyscale + Gaussian blur.
        2. Absolute pixel difference → threshold → dilate.
        3. Find contours; filter by min area.
        Returns per-frame lists of bounding boxes where motion was detected.
        """
        if len(frames) < 2:
            return []

        motion_data: List[Dict[str, Any]] = []
        prev_gray = cv2.GaussianBlur(
            cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY), (21, 21), 0
        )

        for i in range(1, len(frames)):
            gray = cv2.GaussianBlur(
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY), (21, 21), 0
            )
            diff = cv2.absdiff(prev_gray, gray)
            _, thresh = cv2.threshold(
                diff, self.motion_threshold, 255, cv2.THRESH_BINARY
            )
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            regions: List[Tuple[int, int, int, int]] = []
            for c in contours:
                if cv2.contourArea(c) >= self.min_motion_area:
                    x, y, w, h = cv2.boundingRect(c)
                    regions.append((x, y, w, h))

            if regions:
                motion_data.append({"frame_idx": i, "regions": regions})

            prev_gray = gray

        return motion_data

    # ── Segment formatting ──────────────────────────────────────────────────

    def detect_segments(
        self, frames: List[np.ndarray], motion_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Assign temporary IDs to each motion blob per frame."""
        segments: List[Dict[str, Any]] = []
        for md in motion_data:
            fidx = md["frame_idx"]
            matched = []
            for j, r in enumerate(md["regions"]):
                matched.append(
                    {"object_id": f"blob_f{fidx}_{j}", "bbox": list(r)}
                )
            segments.append({"frame_idx": fidx, "matched_regions": matched})
        return segments

    # ── Centroid tracking ───────────────────────────────────────────────────

    def track_objects(
        self, frames: List[np.ndarray], segments: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Greedy nearest-neighbour centroid tracker.
        Matches blobs across consecutive segment frames; creates new tracks
        for unmatched blobs.  Tracks surviving < min_track_frames are pruned.
        """
        tracked: Dict[str, List[Dict[str, Any]]] = {}
        next_id = 0
        active: Dict[str, Dict[str, Any]] = {}  # track_id → last centroid info

        for seg in segments:
            fidx = seg["frame_idx"]
            blobs = seg["matched_regions"]

            centroids = []
            for b in blobs:
                x, y, w, h = b["bbox"]
                centroids.append({"bbox": b["bbox"], "centroid": (x + w / 2, y + h / 2)})

            matched_indices: set = set()

            # Match existing tracks to nearest blob
            for tid, last in list(active.items()):
                lcx, lcy = last["centroid"]
                best_dist = float("inf")
                best_j = -1
                for j, cb in enumerate(centroids):
                    if j in matched_indices:
                        continue
                    cx, cy = cb["centroid"]
                    d = math.hypot(cx - lcx, cy - lcy)
                    if d < self.max_track_distance and d < best_dist:
                        best_dist = d
                        best_j = j
                if best_j != -1:
                    matched_indices.add(best_j)
                    active[tid] = centroids[best_j]
                    tracked.setdefault(tid, []).append(
                        {
                            "frame_idx": fidx,
                            "bbox": centroids[best_j]["bbox"],
                            "center": list(centroids[best_j]["centroid"]),
                        }
                    )

            # New tracks for unmatched blobs
            for j, cb in enumerate(centroids):
                if j not in matched_indices:
                    tid = f"track_{next_id}"
                    next_id += 1
                    active[tid] = cb
                    tracked[tid] = [
                        {
                            "frame_idx": fidx,
                            "bbox": cb["bbox"],
                            "center": list(cb["centroid"]),
                        }
                    ]

        # Prune short tracks (noise)
        return {
            tid: tl for tid, tl in tracked.items() if len(tl) >= self.min_track_frames
        }

    # ── Transform extraction ────────────────────────────────────────────────

    def extract_transforms(
        self, tracked_objects: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        For each track compute per-frame deltas from its first appearance:
        position (dx, dy), scale (sx, sy), rotation (placeholder 0), opacity 1.
        """
        transforms: Dict[str, List[Dict[str, Any]]] = {}

        for tid, entries in tracked_objects.items():
            if not entries:
                continue
            base = entries[0]
            bcx, bcy = base["center"]
            bw, bh = base["bbox"][2], base["bbox"][3]
            track_transforms = []
            for e in entries:
                cx, cy = e["center"]
                w, h = e["bbox"][2], e["bbox"][3]
                track_transforms.append(
                    {
                        "frame_idx": e["frame_idx"],
                        "position": [round(cx - bcx, 2), round(cy - bcy, 2)],
                        "scale": [
                            round(w / bw, 3) if bw else 1.0,
                            round(h / bh, 3) if bh else 1.0,
                        ],
                        "rotation_deg": 0.0,
                        "opacity": 1.0,
                        "abs_bbox": list(e["bbox"]),
                    }
                )
            transforms[tid] = track_transforms

        return transforms

    # ── Annotated keyframe rendering ────────────────────────────────────────

    def render_annotated_frames(
        self,
        frames: List[np.ndarray],
        transforms: Dict[str, List[Dict[str, Any]]],
        key_indices: List[int],
    ) -> List[np.ndarray]:
        """
        Draw red bounding boxes and track IDs on selected keyframes.
        Returns a list of annotated BGR images.
        """
        annotated: List[np.ndarray] = []
        for fidx in key_indices:
            img = frames[fidx].copy()
            for tid, tlist in transforms.items():
                for t in tlist:
                    if t["frame_idx"] == fidx and "abs_bbox" in t:
                        x, y, w, h = [int(v) for v in t["abs_bbox"]]
                        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        cv2.putText(
                            img, tid, (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2,
                        )
                        break
            annotated.append(img)
        return annotated
