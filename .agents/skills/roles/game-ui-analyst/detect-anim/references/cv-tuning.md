# CV Pipeline Tuning & Failure Recovery

Reference for adjusting `extract_motion.py` parameters and handling failure modes.

---

## Parameter Tuning Table

Default command:
```bash
python extract_motion.py <video> <output_dir> --threshold 30 --min-area 500 --max-keyframes 20
```

Adjust parameters based on observed symptoms:

| Symptom | Parameter | Change | Reason |
|---|---|---|---|
| Too many tiny noise tracks (30+) | `--threshold` | Raise to 40-50 | Higher threshold = less sensitive to small pixel changes |
| Too many tiny noise tracks (30+) | `--min-area` | Raise to 800-1000 | Ignores small blobs entirely |
| Small badges/icons missing from tracks | `--min-area` | Lower to 200-300 | Allows smaller detected regions |
| Small badges/icons missing from tracks | `--threshold` | Lower to 20-25 | More sensitive to subtle changes |
| Keyframes too dense, hard to review | `--max-keyframes` | Lower to 10-12 | Fewer but more significant frames |
| Important motion phase missing | `--max-keyframes` | Raise to 30 | Captures more temporal detail |
| Full-screen dimming falsely detected as motion | `--threshold` | Raise to 40+ | Gradual opacity changes produce low-delta pixels |
| Slow fade-in/fade-out missed | - | Cannot fix with params | CV fundamentally cannot detect alpha. Use visual inference in Phase 2 |
| Video is very high-resolution (4K) | `--min-area` | Raise proportionally | A 500px blob at 1080p = 2000px at 4K |

### When to Rerun

Rerun the CV pipeline with adjusted parameters when:
- The initial run produces 0 useful tracks (everything is noise)
- More than 50 tracks are detected (too noisy to reason about)
- You can see important objects moving in the video but no track covers them

Do NOT rerun just because a few objects lack tracks -- that's normal. Use inference in Phase 2 instead.

---

## Failure Mode Decision Tree

### Script fails to run

| Error | Action |
|---|---|
| `ModuleNotFoundError: No module named 'cv2'` | Run `pip install opencv-python-headless numpy` |
| `ModuleNotFoundError: No module named 'numpy'` | Run `pip install numpy` |
| Python not available at all | Ask the user for a precomputed `motion_data.json`. Set `meta.phase1_quality: "precomputed"` |
| Permission denied on output directory | Change output to a writable path (e.g., `/tmp/detect_anim_out_v2`) |

### Script runs but bad output

| Symptom | Action |
|---|---|
| **0 tracks found** | Compare `frame_first.png` vs `frame_last.png` visually. All objects are inferred. Set `meta.phase1_quality: "no_tracks"`. Focus Phase 2 on visual inference -- emit only `inferred_*` entries. Lower confidence across the board (max 0.70). |
| **50+ tracks** (extreme noise) | Rerun with `--threshold 50 --min-area 1000`. If still noisy: ignore all tracks under 5 frames. Log `meta.phase1_quality: "high_noise"`. In Phase 2, be aggressive with Rule 7 (jitter filtering) and Rule 13 (motion validation). |
| **motion_data.json is empty or corrupt** | Rerun the script. If it still fails, fall back to visual-only analysis using first/last frames + detection JSON. Set `meta.phase1_quality: "no_tracks"`. |
| **Annotated frames are unreadable** (overlapping boxes, too many tracks) | Use `frame_first.png` and `frame_last.png` (raw frames) instead. Cross-reference detection JSON positions directly. Report reduced confidence. |

### Video problems

| Symptom | Action |
|---|---|
| **Video too long (>30s)** | Ask the user to trim to the animation segment only. If they can't, warn about potential OOM and suggest lowering resolution. |
| **Video too short (<0.5s)** | Mark timing as unreliable. Require at least one stable pre-state and post-state frame. If neither exists, abort and ask for a longer recording. |
| **OOM during processing** | Ask the user to: (1) trim the video, (2) reduce resolution, or (3) run on a machine with more RAM. The CV pipeline loads all frames into memory. |
| **Video is screen recording with status bar** | Crop or ignore tracks in the top 50-80px (status bar region). Detection JSON objects shouldn't be in that area. |

---

## Known CV Pipeline Limitations

These are inherent to the OpenCV approach and cannot be fixed with parameter tuning:

| Limitation | Impact | Compensation in Phase 2 |
|---|---|---|
| **No opacity/alpha detection** | Fade-in/fade-out invisible to CV | Compare first vs last frame; infer alpha from appearance/disappearance |
| **No rotation detection** | `rotation_deg` always 0.0 | Infer rotation from bbox aspect ratio changes or visual evidence |
| **Greedy centroid tracker** | Fast crossovers cause ID switches | Use Rule 5 (Track Merging); verify identity from annotated frames |
| **All frames loaded to RAM** | Long/high-res videos can OOM | Keep videos <30s, moderate resolution |
| **Fixed blur kernel (21x21)** | Over-smooths fine UI elements | Lower `--min-area` if small objects missed |
| **No semantic labelling** | Track IDs are meaningless numbers | Phase 2 exists to assign semantic identity |
| **No sprite/texture change detection** | Fill states, sprite swaps invisible | Infer from context (e.g., heart empty -> filled) |
