### Epic Overview
The Dot-Grid Board System visual foundation has been implemented successfully. `GridView` creates a scalable, pooled grid of dots constrained to valid board sizes ([3x3] to [40x40]) and establishes precise coordinate mapping to bridge logical grid positions with visual Unity world-space positions. `LevelData.IsValid()` acts as a defensive guard to prevent bad data from reaching the board.

### Sub-tasks Completed
- [x] TASK-001 — **Grid dot rendering.** Created `GridView.cs` MonoBehaviour with `Setup(LevelData levelData)` entry point. Implemented `CreateGridDots()` to instantiate a dot prefab at every (x,y) within the board's content rect. Used `UnityEngine.Pool.ObjectPool<GameObject>` pooling to recycle dots between level loads.
- [x] TASK-002 — **Coordinate mapping.** Implemented `GridView.GridToWorld(Vector2Int gridPos)` and `WorldToGrid(Vector3 worldPos)`. Grid row 0 is the top of the board but world Y increases upward, so Y was correctly inverted. Added unit tests for boundary positions.
- [x] TASK-003 — **Content rect calculation.** Implemented `GridView.CalculateContentRect()` to compute the bounding rect from board dimensions, successfully handling padding and edge cases.
- [x] TASK-004 — **Board size validation.** Implemented board size validation in `GridView.Setup()`: clamped `_gridSize` to [3,3]-[40,40] with `Debug.LogWarning` when clamping occurs.

### Files Modified/Created
- `Assets/Scripts/Board/GridView.cs` (Created implementation)
- `Assets/Scripts/Tests/EditMode/Board/GridViewTests.cs` (Created unit tests)
- `Assets/Scripts/Level/LevelData.cs` (Validation guards added)
- `Assets/Scripts/Tests/EditMode/Level/LevelDataTests.cs` (Added IsValid tests)
- `.war-rooms/room-001/TASKS.md` (Checked off all tasks)

### How to test the full epic
1. Open the **Test Runner** (Window > General > Test Runner) in the Unity Editor.
2. Go to the **EditMode** tab.
3. Locate and run `GridViewTests` and `LevelDataTests` to verify coordinate mapping, bounds calculation, clamping, and pooling.
4. Run the main Game scene and load into a level — the GridView will safely construct the correctly padded grid using pooled GameObjects and log a warning if fed a level with illegally oversized/undersized bounds.