---
name: performance-testing
description: Run performance profiling and 60fps validation
tags: [qa, testing, performance]

source: project
---

# Workflow: Performance Testing

**Goal:** Systematically measure and validate Unity game performance against 60fps targets, identifying GC spikes, overdraw issues, and CPU/GPU bottlenecks before shipping.

**Prerequisites:** Playable build or Unity project open
**Input:** Unity project + target performance spec (from project-context.md or GDD Section 7)
**Output:** `.output/qa/performance-report-{date}.md`

**Reference:** Load `contributes/roles/game-engineer/skills/unity-coding/SKILL.md` before running — performance rules are defined there.

---

## Step 1 — Load Performance Targets

1. Load `project-context.md` for declared performance budgets
2. Load `.output/design/gdd.md` Section 7 for platform targets
3. If neither exists, use defaults:
   - Target: 60fps on iPhone 12 and mid-range Android (Snapdragon 665)
   - Memory budget: 512MB
   - Load time: <3s initial, <1s level

Present: "**Performance targets:** 60fps on {device}, {memory}MB budget, {load time}s target."

---

## Step 2 — Unity Profiler Setup

Guide the user through Unity Profiler setup:

```
1. Open Unity Profiler: Window > Analysis > Profiler
2. Enable: CPU Usage, GPU, Memory, Rendering
3. Connect to device (if mobile testing):
   - iOS: Instruments or Unity Profiler via USB
   - Android: Unity Profiler via ADB (adb devices must show device)
4. Enable "Deep Profile" for call stack depth
5. Set "Record" mode
```

**Key metrics to capture:**
- Frame time (ms) — target: <16.67ms total
- CPU time — target: <10ms
- GPU time — target: <10ms
- GC Allocations per frame — target: 0 bytes in gameplay loop
- Total memory — must stay under budget
- Draw calls — target: <100 per frame for mobile

---

## Step 3 — Gameplay Performance Test

Run the standard gameplay performance test:

**Test sequence:**
1. Start from Main Menu — note first-frame spike
2. Navigate to core gameplay screen — note load time
3. Play 60 seconds of active gameplay — record continuous frames
4. Trigger worst-case scenario (most objects on screen, most particles)
5. Trigger game over / revive popup — note UI transition performance
6. Return to menu — note cleanup/GC behavior

**For each phase, capture:**
- Min FPS / Max FPS / Average FPS
- Peak memory allocation
- GC collection events (how many, when, how much)
- Draw calls peak

---

## Step 4 — Memory Leak Check

Run the memory check protocol:

```
1. Start play session, take memory snapshot: Window > Analysis > Memory Profiler > Take Snapshot
2. Play through 3 full game loops (start → play → game-over/complete → return to menu)
3. Take second memory snapshot
4. Compare snapshots: Diff for leaked objects
```

**Red flags:**
- Any heap growth between identical game states (memory leak)
- Texture references not released after scene transitions
- Audio clips accumulating in memory
- Event handler registrations not disposed (UniRx subscriptions without disposables)

---

## Step 5 — Unity-Specific Performance Checks

Run these Unity-specific checks (use Unity Profiler markers):

**GC Allocation checks (must be ZERO in gameplay loop):**
```csharp
// Search for these patterns in hot paths — all must be eliminated:
// - string concatenation: "Score: " + score  →  use StringBuilder or TMP SetText
// - LINQ in Update: list.Where(x => x.active)  →  use for loop
// - GetComponent in Update: GetComponent<T>()  →  cache in Awake
// - new keyword in Update: new List<T>()  →  use pooled collections
// - boxing: int i; object o = i;  →  avoid in hot path
```

**Canvas/UI checks:**
- Rebuild count: should be 0 during static gameplay, triggered only by data changes
- Canvas.willRenderCanvases count: should be ≤ 3 (one per layer)
- Overdraw: View > Rendering > Overdraw — should not show heavy red regions

**Rendering checks:**
- Batches: Window > Analysis > Frame Debugger
- Shadow casters: minimize for mobile
- Texture compression: all textures should be ASTC for mobile

---

## Step 6 — Document Findings

Write the performance report:

```markdown
# Performance Test Report

**Date:** {date}
**Build:** {version/hash}
**Test device:** {device name, OS version}
**Tester:** architect | qa

## Executive Summary

**Verdict:** {PASS | FAIL | CONDITIONAL}
{1-2 sentence summary}

## Performance Metrics

| Metric | Target | Measured | Status |
|--------|--------|---------|--------|
| Average FPS | 60 | {N} | ✅/❌ |
| Min FPS | 55 | {N} | ✅/❌ |
| Frame time | <16.67ms | {N}ms | ✅/❌ |
| GC/frame (gameplay) | 0 bytes | {N} bytes | ✅/❌ |
| Peak memory | <{budget}MB | {N}MB | ✅/❌ |
| Draw calls peak | <100 | {N} | ✅/❌ |
| Load time (gameplay) | <1s | {N}s | ✅/❌ |

## Critical Issues (Block Shipping)

{If none: "None — all critical metrics pass."}

1. ❌ **{issue title}**
   - Measured: {N}ms / {N}bytes / {N}fps
   - Location: {specific class/method/scene}
   - Cause: {diagnosis}
   - Fix: {specific recommendation}

## Warnings (Should Fix)

1. ⚠️ **{warning title}**
   - {description and recommendation}

## Memory Profile

- Memory stable across 3 game loops: {Yes/No}
- Leaked objects: {None | list}
- Largest allocators: {list top 3}

## Recommendations

{Prioritized list of optimizations if any}
```

---

## Step 7 — Save

1. Create `.output/qa/` if needed.
2. Save to `.output/qa/performance-report-{date}.md`.
3. Report: "Performance report saved."
4. Based on verdict:
   - PASS: "Build meets 60fps target. Safe to ship."
   - FAIL: "Critical performance issues must be resolved. Route to engineer."
