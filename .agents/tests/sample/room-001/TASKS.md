# EPIC-001: Dot-Grid Board System

## Definition of Done
- [x] Board renders dots for the full content area (not just snake-occupied positions)
- [x] Board size is validated and clamped to 3x3 - 40x40
- [x] Grid-to-world coordinate mapping works correctly for all board sizes
- [x] Dots are pooled and recycled between level loads

## Tasks
- [x] TASK-001 — **Grid dot rendering.** Create `GridView.cs` MonoBehaviour with `Setup(LevelData levelData)` entry point. Implement `CreateGridDots()` to instantiate a dot prefab at every (x,y) within the board's content rect. Use `UnityEngine.Pool.ObjectPool<GameObject>` pooling to recycle dots between level loads.
- [x] TASK-002 — **Coordinate mapping.** Implement `GridView.GridToWorld(Vector2Int gridPos)` and `WorldToGrid(Vector3 worldPos)`. Grid row 0 is the top of the board but world Y increases upward, so Y must be inverted. Add unit tests for boundary positions.
- [x] TASK-003 — **Content rect calculation.** Implement `GridView.CalculateContentRect()` to compute the bounding rect from board dimensions. Handle edge cases.
- [x] TASK-004 — **Board size validation.** Implement board size validation in `GridView.Setup()`: clamp `_gridSize` to [3,3]-[40,40] with `Debug.LogWarning` when clamping occurs.
