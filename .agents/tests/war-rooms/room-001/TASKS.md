# EPIC-001 — Core Gameplay Engine

## Story 1.1: Dot-Grid Board System
- [x] T-001.1.1 — Define `BoardData` data class: `int width`, `int height`, `Vector2Int[] dotPositions`. Validate min 3×3, max 40×40.
- [x] T-001.1.2 — Create `BoardManager` MonoBehaviour: instantiate dot GameObjects from `BoardData` (using Object Pooling to support large boards up to 40x40), spacing them evenly in world space. Use a configurable `dotSpacing` float.
- [x] T-001.1.3 — Create a `DotView` prefab (SpriteRenderer with a small circle sprite, URP 2D material).
- [x] T-001.1.4 — Implement coordinate-to-world-position utility methods: `Vector2 GridToWorld(Vector2Int gridPos)` and `Vector2Int WorldToGrid(Vector2 worldPos)`.
- [x] T-001.1.5 — Write unit tests: board generation for 3×3, 10×10, 40×40; coordinate conversion round-trip.

## Story 1.2: Snake Rendering & Segmentation
- [x] T-001.2.1 — Define `SnakeData` class: list of `Vector2Int` occupied dots, head direction (enum `Direction { Left, Right, Up, Down }`), color/skin ID.
- [x] T-001.2.2 — Implement segment math: a snake occupying N dots has `(N-1)*2` visual segments (4 segments = 2 dots). Store segment midpoints.
- [x] T-001.2.3 — Create `SnakeRenderer` component using `LineRenderer` or a custom mesh-based spline. Render curves at bends (where consecutive dot directions change).
- [x] T-001.2.4 — Build `SnakeView` prefab hierarchy: head sprite, body segments, tail sprite. Support 5 color variants.
- [x] T-001.2.5 — Implement `SnakeManager`: spawns `SnakeView` instances from `SnakeData[]` in the current level via Object Pooling, positions them on the board dots.
- [x] T-001.2.6 — Write tests: snake spanning 2 dots produces 4 segments; snake with a 90-degree bend renders a curve; snake colors match data.

## Story 1.3: Snake Direction System
- [x] T-001.3.1 — Add `Direction exitDirection` property to `SnakeData`.
- [x] T-001.3.2 — Implement `SnakeDirectionResolver`: given a snake's exit direction, compute the ray/path from the snake's head position toward the board edge.
- [x] T-001.3.3 — Add visual indicator of direction on the snake head sprite (rotation or small arrow).
- [x] T-001.3.4 — Write tests: path generation towards the edge matching direction.

## Story 1.4: Tap-to-Move Mechanic
- [x] T-001.4.1 — Implement `InputManager` using Unity's Input System package (existing `InputSystem_Actions.inputactions`). Detect single-finger tap on mobile, mouse click in editor.
- [x] T-001.4.2 — Implement tap-to-snake raycasting: on tap, raycast from screen point into 2D world, check if a snake collider is hit.
- [x] T-001.4.3 — Implement `MoveValidator`: trace exit path. Check each dot for obstacles or other snakes. Return `MoveResult` containing `IsValid`, `BlockReason`, and `BlockingElement`.
- [x] T-001.4.4 — If path is clear → trigger the move (Story 1.5). If blocked → trigger wrong move (Story 1.6).
- [x] T-001.4.5 — Add move-in-progress lock: ignore taps while a snake is animating.
- [x] T-001.4.6 — Write tests: validate taps, validating blockers and move-in-progress locks.

## Story 1.5: Correct Move Logic
- [x] T-001.5.1 — Implement `SnakeMoveAnimator`: animate the snake sliding along its exit path dot-by-dot (speed: 1 dot per 33ms). Use DOTween or coroutine-based interpolation.
- [x] T-001.5.2 — Implement exit-off-board animation: continuing off-screen with slight acceleration.
- [x] T-001.5.3 — On animation complete: destroy or pool the snake GameObject, remove from list.
- [x] T-001.5.4 — Fire `OnSnakeExited` event.
- [x] T-001.5.5 — Implement coin/collection credit: increment a per-level snake collection counter.
- [x] T-001.5.6 — Write tests: valid move logic and event firing.

## Story 1.6: Wrong Move Logic
- [x] T-001.6.1 — Implement wrong-move feedback: bounce-back animation on the snake.
- [x] T-001.6.2 — Deduct 1 health via the Health System (Story 1.7) on the first wrong move per tap (prevent repeated deductions from rapid re-taps).
- [x] T-001.6.3 — Fire `OnWrongMove` event with details (which snake, what blocked it).
- [x] T-001.6.4 — Play screen shake effect.
- [x] T-001.6.5 — Write tests: bounce logic, deduction limits, event firing.

## Story 1.7: Health / Lives System
- [x] T-001.7.1 — Create `HealthManager` service: `maxHealth` (default 3), `currentHealth`, methods `TakeDamage`, `Heal`, `ResetHealth`.
- [x] T-001.7.2 — Fire `OnHealthChanged` and `OnHealthDepleted` events.
- [x] T-001.7.3 — Create health HUD display: heart icons in gameplay UI canvas updating reactively.
- [x] T-001.7.4 — Implement heart-break animation when health is lost.
- [x] T-001.7.5 — Write tests: health boundaries, event firing.

## Story 1.8: Level Completion Detection
- [x] T-001.8.1 — Implement `LevelStateManager`: track total snakes in level vs. snakes exited.
- [x] T-001.8.2 — When snakes exited equals total snakes, fire `OnLevelComplete` event.
- [x] T-001.8.3 — Transition to result screen (pass level stats: snakes collected, health remaining).
- [x] T-001.8.4 — Write tests: completion conditions.

## Story 1.9: Level Failure & Retry
- [x] T-001.9.1 — Listen to `OnHealthDepleted` in `LevelStateManager`. Trigger the Revive/Failed popup.
- [x] T-001.9.2 — Implement `RevivePopup` UI: revive (300 coin or watch ad) or restart.
- [x] T-001.9.3 — Revive flow: if 300 coin, deduct and `ResetHealth()`. If ad, call placeholder. Resume gameplay.
- [x] T-001.9.4 — Restart flow: reload the level from scratch.
- [x] T-001.9.5 — Failed/Home flow: return to home/dashboard.
- [x] T-001.9.6 — Write tests: revive states and proper level restarts.

## Story 1.10: Camera Pinch-to-Zoom
- [x] T-001.10.1 — Implement `CameraController` with default orthographic size to fit the board.
- [x] T-001.10.2 — Implement pinch-to-zoom using touch input: track distance delta, map to orthographic size change.
- [x] T-001.10.3 — Clamp camera position so the board stays visible (pan boundaries).
- [x] T-001.10.4 — In editor: support scroll-wheel zoom for testing.
- [x] T-001.10.5 — Write tests: zoom mapping and boundary clamps.

## Story 1.11: Level Data Loader
- [x] T-001.11.1 — Define `LevelData` format as JSON (to support future LiveOps/remote levels): sizes, dots, snakes, obstacles, maxHealth.
- [x] T-001.11.2 — Implement `LevelLoader` service.
- [x] T-001.11.3 — Implement `LevelBuilder`: takes `LevelData`, calls managers to set up the scene.
- [x] T-001.11.4 — Create 3 hand-crafted test levels (3x3, 7x7, 15x15).
- [x] T-001.11.5 — Write tests: validation of level parsing and instantiation.