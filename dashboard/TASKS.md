# Tasks for EPIC-000: Project Foundation & Design System Bootstrap

- [x] TASK-001 — Define design system tokens and component API
  - AC: `docs/design-system-spec.md` exists and contains extracted tokens from `mockup.html`.
- [x] TASK-002 — Install and verify npm dependencies
  - AC: All required packages in Technology Stack are present in `package.json` and importable.
- [x] TASK-003 — Configure TailwindCSS locally
  - AC: `tailwind.config.ts` matches design tokens from spec. CDN script replaced with PostCSS integration.
- [x] TASK-004 — Set up CSS custom properties in `globals.css`
  - AC: CSS variables for colors, typography, spacing, etc., are defined in `:root` and `[data-theme="dark"]`.
- [x] TASK-005 — Create App Router route structure
  - AC: Placeholder pages exist for `/plans/[id]`, `/plans/[id]/epics/[taskRef]`, `/roles`, `/skills`, `/settings`.
- [x] TASK-006 — Scaffold Zustand stores
  - AC: `src/lib/stores/planStore.ts`, `wsStore.ts`, and `uiStore.ts` are created and exported.
- [x] TASK-007 — Create API client and WebSocket hook
  - AC: `src/lib/api.ts` handles fetch with base URL. `src/hooks/useWebSocket.ts` manages connection with reconnect logic.
- [x] TASK-008 — Build shared base components
  - AC: UI components (`Button`, `Badge`, `Tooltip`, etc.) implemented in `src/components/ui/` with correct props and dark mode support.
- [x] TASK-009 — Configure Next.js API proxy
  - AC: `next.config.ts` proxies `/api/*` to `http://localhost:9000/api/*`.
- [x] TASK-010 — Set up Vitest and sample test
  - AC: `vitest.config.ts` configured. `npm test` runs and passes a sample component test.

