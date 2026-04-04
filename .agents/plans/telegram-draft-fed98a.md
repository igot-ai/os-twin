```markdown
<!-- MANAGER INSTRUCTION:
The plan below maps out the creation of a web-based Snake game using HTML5 Canvas and JavaScript. It defines the necessary roles and lifecycle for each Epic to ensure autonomous agents can execute, review, and fix their work.
-->

# Plan: Simple Snake Game

> Created: 2024-05-20T00:00:00+00:00
> Status: draft
> Project: /workspace/snake-game

## Config

working_dir: /workspace/snake-game

## Goal

Build a fully functional, web-based classic Snake game using HTML5 Canvas, CSS, and JavaScript. The game should include score tracking, progressive difficulty, and a game-over state.

## EPIC-001 - Project Setup & Architecture

Roles: architect, engineer
Objective: Set up the project structure and define the game architecture, state models, and configuration constants.
Lifecycle:
```text
pending → architect → engineer ─┬─► passed → signoff
              ▲                 │
              └── architect ◄───┘ (on fail → fixing)
```
Skills: html, css, javascript, scaffolding

### Definition of Done
- [ ] Core file structure created (HTML, CSS, JS)
- [ ] Constants and state models defined

### Tasks
- [ ] TASK-001 — Create `index.html` with canvas element
- [ ] TASK-002 — Create `style.css` for basic layout and centering
- [ ] TASK-003 — Create `game.js` and define game configuration (grid size, frame rate, initial state)

### Acceptance criteria:
- HTML file successfully loads CSS and JS files without console errors.
- Canvas element is present and appropriately sized.

depends_on: []

## EPIC-002 - Core Game Engine & Logic

Roles: engineer, qa
Objective: Implement the main game loop, snake movement, food generation, and collision detection logic.
Lifecycle:
```text
pending → engineer → qa ─┬─► passed → signoff
             ▲           │
             └─ engineer ◄┘ (on fail → fixing)
```
Skills: javascript, game-loop, algorithms

### Definition of Done
- [ ] Core game loop is functional
- [ ] Snake movement and growth logic implemented
- [ ] Collision detection (walls and self) is functional

### Tasks
- [ ] TASK-001 — Implement the game loop using `requestAnimationFrame` or `setInterval`
- [ ] TASK-002 — Implement snake coordinate updates based on current velocity/direction
- [ ] TASK-003 — Implement food spawning at random valid grid coordinates
- [ ] TASK-004 — Implement boundary and self-collision detection resulting in game over

### Acceptance criteria:
- Snake moves at a consistent coordinate rate.
- Eating food increases the snake's length array.
- Hitting a boundary or self triggers the game-over state.

depends_on: [EPIC-001]

## EPIC-003 - UI Rendering & Controls

Roles: engineer, qa
Objective: Render the game state to the canvas and handle user keyboard input for controls.
Lifecycle:
```text
pending → engineer → qa ─┬─► passed → signoff
             ▲           │
             └─ engineer ◄┘ (on fail → fixing)
```
Skills: javascript, canvas-api, event-listeners

### Definition of Done
- [ ] Game state is accurately rendered to the Canvas every frame
- [ ] Keyboard input correctly updates the snake's direction

### Tasks
- [ ] TASK-001 — Implement canvas rendering functions for the background, snake segments, and food
- [ ] TASK-002 — Add event listeners for arrow keys (or WASD) to change direction, preventing 180-degree immediate reversals
- [ ] TASK-003 — Render the current score and a "Game Over" overlay when applicable

### Acceptance criteria:
- Visuals reflect the internal game state accurately without flickering.
- Controls are responsive and ignore illegal reverse moves (e.g., moving right while already moving left).
- Score increments visually when food is eaten.

depends_on: [EPIC-002]
```