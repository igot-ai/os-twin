```markdown
# Plan: Simple Snake Game

> Created: 2024-05-24T12:00:00+00:00
> Status: draft
> Project: /snake-game

## Config

working_dir: /snake-game

---

## Goal

Develop a fully functional, web-based classic Snake game using HTML5 Canvas, JavaScript, and CSS. The game will feature core mechanics (movement, growth, collision detection), score tracking, and basic game states (Start, Playing, Game Over).

## EPIC-001 - Project Setup and Architecture

Roles: architect, engineer
Objective: Establish the foundational HTML/CSS structure and the basic JavaScript game loop rendering to a canvas.
Lifecycle:
```text
pending → architect → engineer ─┬─► passed → signoff
                      ▲         │
                      └ architect ◄┘ (on fail → fixing)
```

Tasks: Scaffold the project structure. Set up the HTML5 Canvas element. Implement a responsive `requestAnimationFrame` or `setInterval` game loop.

### Definition of Done
- [ ] Project files (`index.html`, `styles.css`, `game.js`) are created
- [ ] Canvas renders correctly in the browser
- [ ] Game loop successfully executes and clears the canvas each frame

### Tasks
- [ ] TASK-001 — Create HTML skeleton and link CSS/JS
- [ ] TASK-002 — Set up basic CSS for centering and canvas borders
- [ ] TASK-003 — Initialize Canvas context and basic game loop

Acceptance criteria:
- A blank game board is rendered.
- No console errors on load.

depends_on: []

## EPIC-002 - Core Mechanics (Snake & Food)

Roles: engineer, qa
Objective: Implement the interactive gameplay logic, including snake movement, food generation, and collision rules.
Lifecycle:
```text
pending → engineer → qa ─┬─► passed → signoff
             ▲           │
             └─ engineer ◄┘ (on fail → fixing)
```

Tasks: Handle keyboard input for directions. Implement the snake body as an array of coordinates. Generate food at random coordinates. Handle snake growth and collision logic (walls and self).

### Definition of Done
- [ ] Snake can be controlled via arrow keys
- [ ] Snake grows when eating food
- [ ] Game correctly registers collision with walls or self

### Tasks
- [ ] TASK-001 — Implement keyboard event listeners for directional control
- [ ] TASK-002 — Build snake movement and drawing logic
- [ ] TASK-003 — Build food generation and eating logic
- [ ] TASK-004 — Implement collision detection logic (game over conditions)

Acceptance criteria:
- Snake cannot reverse directly into itself.
- Food does not spawn on top of the snake's current body.
- QA validates all movement and edge-case collisions.

depends_on: [EPIC-001]

## EPIC-003 - Game States & UI Polish

Roles: engineer, qa
Objective: Add score tracking, Start/Game Over screens, and final visual polish.
Lifecycle:
```text
pending → engineer → qa ─┬─► passed → signoff
             ▲           │
             └─ engineer ◄┘ (on ui/logic bug)
```

Tasks: Add overlay screens for Start and Game Over. Implement a live score counter and high score tracking (using `localStorage`). Apply final CSS styling for a retro arcade look.

### Definition of Done
- [ ] Game supports Start, Play, and Game Over states
- [ ] Score is displayed and updates in real-time
- [ ] User can restart the game after dying

### Tasks
- [ ] TASK-001 — Implement state management (Start menu, Playing, Game Over)
- [ ] TASK-002 — Add live score overlay and high score tracking
- [ ] TASK-003 — Apply styling polish (colors, typography, responsive scaling)
- [ ] TASK-004 — Add Restart button and reset logic

Acceptance criteria:
- Game does not start until the user clicks "Start".
- Score resets properly on new game, but high score persists.
- UI elements do not obstruct the game canvas during gameplay.

depends_on: [EPIC-002]
```