# Plan: Simple Snake Game

> Created: 2024-05-20T10:00:00+00:00
> Status: draft
> Project: /workspace/snake-game

## Config

working_dir: /workspace/snake-game

## Goal

Develop a classic, playable Snake game using standard web technologies (HTML, CSS, JavaScript). The game must feature a robust game loop, movement controls, food generation, score tracking, accurate collision detection for game over states, and a stunning, highly polished, beautiful user interface with modern visual effects.

## EPIC-001 - Architecture & Setup

Roles: architect
Objective: Define the game architecture, rendering strategy, visual theme, and state schema
Lifecycle:
```text
pending → architect ─┬─► passed → signoff
             ▲       │
             └───────┘ (on fail → fixing)
```

Tasks: Scaffold the project structure and define the technical design for the game loop, grid system, state management, and high-level UI/UX strategy.

### Definition of Done
- [ ] Technical and visual design is documented and project scaffolding is complete

### Tasks
- [ ] TASK-001 — Initialize project structure (index.html, style.css, game.js)
- [ ] TASK-002 — Define game state schema (snake body coordinates, food position, current direction, score)
- [ ] TASK-003 — Architect the rendering approach (HTML5 Canvas) and grid coordinate system
- [ ] TASK-004 — Define the visual design system (color palette, typography, modern UI theme, and rendering effects strategy)

### Acceptance criteria:
- Documented separation between game logic and rendering.
- Grid dimensions and game tick interval are clearly defined.
- A clear visual theme (e.g., modern neon, retro arcade, or sleek minimal) is established.

depends_on: []

## EPIC-002 - UI Design & Core Game Implementation

Roles: designer, engineer, qa
Objective: Design a beautiful UI and implement the game engine, user input, rendering, and core mechanics
Lifecycle:
```text
pending → designer → engineer → qa ─┬─► passed → signoff
             ▲          ▲           │
             │          └─ engineer ◄┤ (on functionality bug)
             └─────────── designer ◄─┘ (on design feedback)
```

Tasks: Craft a beautiful user interface, build the game loop, render the grid, implement snake movement, handle keyboard input, manage collision logic, and apply visual polish.

### Definition of Done
- [ ] Fully playable, visually stunning snake game with no core mechanical bugs

### Tasks
- [ ] TASK-001 — Design and implement a beautiful, modern UI layout (CSS styling, typography, responsive layout, background aesthetics)
- [ ] TASK-002 — Implement the game loop using `requestAnimationFrame` for smooth rendering
- [ ] TASK-003 — Handle keyboard input for directional changes (preventing 180-degree reversals)
- [ ] TASK-004 — Implement snake movement and rendering on the Canvas with high-quality graphics (e.g., rounded segments, gradients, smooth interpolation)
- [ ] TASK-005 — Implement food spawning logic and eating mechanics with visual effects (e.g., glow effects, particle pop on eat)
- [ ] TASK-006 — Implement collision detection (walls and self) to trigger Game Over
- [ ] TASK-007 — Add beautifully animated game state screens (Start screen, stylish Game Over screen with score highlight)

### Acceptance criteria:
- The game UI is highly polished, beautiful, and visually impressive.
- Snake is controlled smoothly via arrow keys.
- Eating food increases the score by 1 and grows the snake's tail, accompanied by a pleasing visual effect.
- Food does not spawn inside the snake's body.
- Hitting a wall or hitting the snake's own body stops the game loop and transitions to a beautifully styled Game Over message.
- QA validates all edge cases, including rapid key presses and UI responsiveness.

depends_on: [EPIC-001]

## EPIC-003 - Documentation & Polish

Roles: technical-writer, qa
Objective: Document gameplay instructions and verify final project state
Lifecycle:
```text
pending → technical-writer → qa ─┬─► passed → signoff
               ▲                 │
               └─ technical-writer ◄┘ (on fail → fixing)
```

Tasks: Create a comprehensive README.md detailing how to run and play the game.

### Definition of Done
- [ ] Repository contains clear, QA-verified documentation

### Tasks
- [ ] TASK-001 — Write README.md with project description and screenshot placeholders highlighting the beautiful UI
- [ ] TASK-002 — Document how to run the game locally
- [ ] TASK-003 — Document game controls and rules

### Acceptance criteria:
- Instructions are clear enough for a non-technical user to open the game in a browser.
- All controls and features are accurately described.

depends_on: [EPIC-002]