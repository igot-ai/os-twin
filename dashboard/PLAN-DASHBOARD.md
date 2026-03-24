# Plan: Agentic OS — Dashboard Screen (FE-Only with Mock API)
> Created: 2026-03-23T10:00:00+08:00
> Revised: 2026-03-24T10:27:00+07:00
> Status: draft
> Project: /Users/paulaan/PycharmProjects/agent-os/dashboard
> Strategy: **Frontend-only build with mock API layer** — no backend dependency

## Config
working_dir: /Users/paulaan/PycharmProjects/agent-os/dashboard

## Goal
Build the Agentic OS Dashboard FE ./fe as a **frontend-only application** with a comprehensive **mock API layer** that simulates all backend behavior. The FE team can **develop, review, and refactor every screen** following the design reference in `mockup.html` without depending on a live backend.

All data comes from **Next.js API route handlers** (`src/app/api/`) backed by **in-memory mock data** (`src/lib/mock-data.ts`). WebSocket is replaced by **simulated real-time events** (polling or `setTimeout`-based push). This allows parallel FE + BE development — when the real backend is ready, swap the mock API routes for proxy routes pointing to the FastAPI server.

---

## Technology Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Framework | Next.js (App Router) | 16.1.6 | Already scaffolded |
| UI Library | React | 19.2.3 | Already installed |
| Language | TypeScript | 5.9.3 | Already configured |
| Styling | TailwindCSS | 4.x | Migrate from CDN (mockup) to local install |
| Fonts | Plus Jakarta Sans + IBM Plex Mono | Google Fonts | Already in `mockup.html` |
| Icons | Material Symbols Outlined | Google Fonts | Already in `mockup.html` |
| State Management | Zustand | — | Lightweight client state |
| Data Fetching | SWR | — | Stale-while-revalidate from mock API routes |
| Drag & Drop | `@dnd-kit/core` + `@dnd-kit/sortable` | — | For Kanban and task reordering |
| Charts | Recharts | — | For sparklines, donut rings |
| Mock API | Next.js API Routes (`src/app/api/`) | — | In-memory data, simulated latency |
| Simulated WebSocket | `setTimeout` + SWR polling | — | Replaces real WebSocket; toggle-able via config |

> **Note:** No Python backend, no FastAPI, no WebSocket server, no external database required.

---

## Design Reference

The visual design spec is `mockup.html` — an **Epic Detail page** mockup. Key design tokens:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#2563eb` (blue-600) | Primary actions, active states, links |
| `--color-background-light` | `#f8fafc` (slate-50) | Page background |
| `--color-background-dark` | `#0f172a` (slate-900) | Terminal/channel feed, dark mode |
| `--color-surface` | `#ffffff` | Cards, panels, modals |
| `--color-text-main` | `#0f172a` | Primary text |
| `--color-text-muted` | `#64748b` (slate-500) | Secondary text, labels |
| `--color-border` | `#e2e8f0` (slate-200) | Borders, dividers |
| `--color-warning` | `#eab308` (yellow-500) | Warnings, blocked states |
| `--color-terminal-sys` | `#38bdf8` (sky-400) | System messages in channel feed |
| Font: display | Plus Jakarta Sans (400, 500, 600, 700) | All UI text |
| Font: mono | IBM Plex Mono (400, 500) | Code, task IDs, timestamps |
| Border radius | 4px (default), 6px (md), 8px (lg) | Cards, badges, inputs |
| Card shadow | `0 4px 6px -1px rgba(15,23,42,0.05)` | Card elevation |

The mockup demonstrates: sticky header with breadcrumb, three-panel layout (task checklist sidebar → lifecycle visualizer center → QA/role overrides right), terminal-style channel feed footer, state-node pulse animation, and Material Symbols icon usage.

---

## Existing Codebase Inventory

| File / Directory | Status | Notes |
|-----------------|--------|-------|
| `src/types/index.ts` | ✅ Complete | Plan, Epic, Task, Role, Skill, ChannelMessage, Lifecycle types |
| `src/lib/mock-data.ts` | ✅ Complete | 6 plans, 6 epics, 5 messages, lifecycle, 4 roles, 8 skills |
| `src/app/page.tsx` | ⚠️ Needs refactor | Dashboard landing page — align to new design |
| `src/app/plans/` | ⚠️ Stub | Route exists but minimal content |
| `src/app/roles/` | ⚠️ Stub | Route exists but minimal content |
| `src/app/skills/` | ⚠️ Stub | Route exists but minimal content |
| `src/components/layout/` | ⚠️ Needs audit | TopBar exists, may need refactor |
| `src/components/dashboard/` | ⚠️ Needs audit | Some dashboard components exist |

---

## Mock API Strategy

All API endpoints are **Next.js API route handlers** (`src/app/api/`) that read/write from **in-memory mock data**. This enables:

1. **Realistic fetch patterns** — components use `fetch('/api/plans')` just like production
2. **Simulated latency** — each handler adds `await delay(200)` to mimic network
3. **Simulated mutations** — POST/PUT/DELETE handlers modify in-memory state
4. **Simulated real-time** — SWR `refreshInterval` replaces WebSocket
5. **Easy swap** — when backend is ready, change API routes to proxy to FastAPI

### API Route Map

| Endpoint | Method | Mock Behavior | EPIC |
|----------|--------|---------------|------|
| `/api/stats` | GET | Return `mockStats` | EPIC-001 |
| `/api/plans` | GET | Return `mockPlans` with filter/sort query params | EPIC-001 |
| `/api/plans/[id]` | GET | Return single plan by ID | EPIC-001 |
| `/api/plans/[id]/epics` | GET | Return `mockEpics` filtered by `plan_id` | EPIC-001 |
| `/api/plans/[id]/epics/[ref]` | GET | Return single epic by ref | EPIC-001 |
| `/api/plans/[id]/epics/[ref]/tasks` | PATCH | Toggle task completion | EPIC-001 |
| `/api/plans/[id]/epics/[ref]/state` | POST | Advance lifecycle state | EPIC-001 |
| `/api/plans/[id]/epics/[ref]/messages` | GET | Return `mockMessages` for room | EPIC-001 |
| `/api/roles` | GET, POST, PUT, DELETE | CRUD on `mockRoles` | EPIC-001 |
| `/api/roles/[id]/test` | POST | Simulated model connection test | EPIC-001 |
| `/api/skills` | GET, POST, PUT, DELETE | CRUD on `mockSkills` | EPIC-001 |
| `/api/lifecycle` | GET | Return `mockLifecycle` | EPIC-001 |
| `/api/plans/[id]/dag` | GET | Return computed DAG from epic deps | EPIC-001 |
| `/api/notifications` | GET | Return mock notifications | EPIC-001 |

---

## Verification Strategy

| Method | Scope | Tool | When |
|--------|-------|------|------|
| Manual Browser Review | UI fidelity vs mockup.html | Side-by-side comparison | Per-EPIC |
| Dev Server Smoke | All routes render without crash | `bun run dev` | Per-EPIC |
| Build Verification | Static export works | `bun run build` | After EPIC-002, then every 3 EPICs |
| Visual Review | Design token accuracy | Browser DevTools | Per-component |

---

## EPIC-001 — Mock API Layer & Data Foundation

Roles: engineer
Objective: Create the complete Next.js API route layer and expand mock data to support all screens. This is the **backend substitute** — every component fetches from these routes.

### Definition of Done
- [ ] All API routes from the API Route Map table are implemented and return correct JSON.
- [ ] Mock data in `src/lib/mock-data.ts` is expanded to cover all entity types needed.
- [ ] Each route handler adds simulated latency (`100-300ms` random delay).
- [ ] Mutation routes (POST/PUT/DELETE) modify in-memory state for the session.
- [ ] A `src/lib/api-client.ts` utility wraps `fetch` with base URL and error handling.
- [ ] SWR provider is configured in root layout with global `refreshInterval: 0` (manual revalidation by default).

### Tasks
- [ ] TASK-001 — **Expand `mock-data.ts`:** Add DAG data (`mockDAG`), notification data (`mockNotifications`), model registry data (`mockModels`), and more varied channel messages (10+ messages with all `MessageType` variants). Ensure all cross-references are consistent (plan IDs in epics match plan list, skill refs in roles match skill list).
- [ ] TASK-002 — **Create API route handlers:** Build all routes in `src/app/api/`. Each handler: imports mock data, applies query params (filter/sort), returns JSON response. GET routes are pure reads. POST/PUT/PATCH/DELETE routes mutate the in-memory arrays (valid for dev session only).
- [ ] TASK-003 — **Build `api-client.ts`:** Wrapper functions: `apiGet<T>(path)`, `apiPost<T>(path, body)`, `apiPut<T>(path, body)`, `apiDelete(path)`. Each handles `Response.ok` check, JSON parse, and throws typed errors. Base URL is relative (`/api`).
- [ ] TASK-004 — **Build SWR hooks:** Create `src/hooks/use-plans.ts`, `use-epics.ts`, `use-roles.ts`, `use-skills.ts`, `use-stats.ts`, `use-messages.ts`. Each hook wraps SWR with the correct API path and return types. Export both data and mutation helpers.
- [ ] TASK-005 — **Build simulated real-time service:** Create `src/lib/mock-realtime.ts` — a simple event emitter that dispatches fake progress updates on a configurable interval (disabled by default, toggle-able via `NEXT_PUBLIC_ENABLE_MOCK_REALTIME=true`). Components can subscribe to simulate live updates without WebSocket.
- [ ] TASK-006 — **Configure SWR provider in root layout:** Wrap app with `SWRConfig` in `layout.tsx`. Set default fetcher to use `api-client.ts`. Set default `dedupingInterval: 2000`.

Files:
```
[MOD]  src/lib/mock-data.ts                   (expand entities)
[NEW]  src/app/api/stats/route.ts
[NEW]  src/app/api/plans/route.ts
[NEW]  src/app/api/plans/[id]/route.ts
[NEW]  src/app/api/plans/[id]/epics/route.ts
[NEW]  src/app/api/plans/[id]/epics/[ref]/route.ts
[NEW]  src/app/api/plans/[id]/epics/[ref]/tasks/route.ts
[NEW]  src/app/api/plans/[id]/epics/[ref]/state/route.ts
[NEW]  src/app/api/plans/[id]/epics/[ref]/messages/route.ts
[NEW]  src/app/api/plans/[id]/dag/route.ts
[NEW]  src/app/api/roles/route.ts
[NEW]  src/app/api/roles/[id]/route.ts
[NEW]  src/app/api/roles/[id]/test/route.ts
[NEW]  src/app/api/skills/route.ts
[NEW]  src/app/api/skills/[id]/route.ts
[NEW]  src/app/api/lifecycle/route.ts
[NEW]  src/app/api/notifications/route.ts
[NEW]  src/lib/api-client.ts
[NEW]  src/lib/mock-realtime.ts
[NEW]  src/hooks/use-plans.ts
[NEW]  src/hooks/use-epics.ts
[NEW]  src/hooks/use-roles.ts
[NEW]  src/hooks/use-skills.ts
[NEW]  src/hooks/use-stats.ts
[NEW]  src/hooks/use-messages.ts
[MOD]  src/app/layout.tsx                     (SWR provider)
```

Acceptance criteria:
- `curl localhost:3000/api/plans` returns JSON array of plans.
- `curl localhost:3000/api/plans/plan-001/epics` returns epics for that plan.
- SWR hooks return typed data in components without direct mock imports.

depends_on: []

---

## EPIC-002 — Design System & Project Foundation

Roles: engineer
Objective: Bootstrap TailwindCSS locally, define design tokens matching `mockup.html`, load fonts, and create shared UI components. This EPIC produces the visual building blocks.

### Definition of Done
- [ ] TailwindCSS is migrated from CDN to local install with all design tokens from the Design Reference table.
- [ ] CSS custom properties defined in `globals.css` for both light and dark themes.
- [ ] Google Fonts loaded (Plus Jakarta Sans, IBM Plex Mono, Material Symbols Outlined).
- [ ] Shared base components exist: `<Button>`, `<Badge>`, `<StatusBadge>`, `<Tooltip>`, `<Modal>`, `<Skeleton>`, `<Dropdown>`, `<IconButton>`.
- [ ] Dark mode toggle works via `data-theme` attribute.
- [ ] `bun run dev` starts without errors.

### Tasks
- [ ] TASK-001 — **Configure TailwindCSS locally.** Migrate the `tailwind.config` from `mockup.html` CDN block into `tailwind.config.ts`. Add all color tokens, font families, border-radius, and box-shadow values. Replace CDN usage with PostCSS integration.
- [ ] TASK-002 — **Set up CSS custom properties in `globals.css`.** Define variables in `:root` (light) and `[data-theme="dark"]` (dark). Include custom scrollbar styles and `state-node-pulse` animation from mockup.
- [ ] TASK-003 — **Load fonts via `next/font` or `<link>`.** Plus Jakarta Sans (400, 500, 600, 700), IBM Plex Mono (400, 500), Material Symbols Outlined.
- [ ] TASK-004 — **Build shared UI components.** Create `src/components/ui/`: `Button.tsx`, `Badge.tsx`, `StatusBadge.tsx`, `Tooltip.tsx`, `Modal.tsx`, `Skeleton.tsx`, `Dropdown.tsx`, `IconButton.tsx`. Each component uses design tokens and supports dark mode.
- [ ] TASK-005 — **Create App Router route structure.** Ensure routes exist: `/` (Dashboard), `/plans/[id]` (Plan Workspace), `/plans/[id]/epics/[ref]` (Epic Detail), `/roles`, `/skills`, `/settings`. Each page exports a placeholder.

Files:
```
[MOD]  tailwind.config.ts                     (design tokens from mockup)
[MOD]  src/app/globals.css                    (CSS variables, animations)
[MOD]  src/app/layout.tsx                     (fonts, providers)
[NEW]  src/components/ui/Button.tsx
[NEW]  src/components/ui/Badge.tsx
[NEW]  src/components/ui/StatusBadge.tsx
[NEW]  src/components/ui/Tooltip.tsx
[NEW]  src/components/ui/Modal.tsx
[NEW]  src/components/ui/Skeleton.tsx
[NEW]  src/components/ui/Dropdown.tsx
[NEW]  src/components/ui/IconButton.tsx
[MOD]  src/app/plans/[id]/page.tsx            (placeholder)
[NEW]  src/app/plans/[id]/epics/[ref]/page.tsx (placeholder)
```

Acceptance criteria:
- `bun run dev` starts without errors and serves placeholder routes.
- Design tokens from `mockup.html` are available as CSS variables and Tailwind classes.
- Dark mode toggle switches all custom properties correctly.

depends_on: []

---

## EPIC-003 — Global Navigation Shell & App Layout

Roles: engineer
Objective: Build the persistent app shell: top bar, collapsible sidebar, and content area. Every subsequent EPIC renders inside the content slot.

### Definition of Done
- [ ] App shell renders with top bar (56px), collapsible sidebar (240px / 64px), and flexible content area.
- [ ] Navigation items route to Dashboard, Plans, Skills, Roles, Settings.
- [ ] Sidebar collapse state persists in localStorage.
- [ ] Top bar is sticky and matches mockup header style.

### Tasks
- [ ] TASK-001 — **Build `<AppShell>` layout.** CSS Grid: `grid-template-columns: auto 1fr; grid-template-rows: 56px 1fr`. Sidebar is collapsible with toggle button.
- [ ] TASK-002 — **Build `<TopBar>` component.** Contains: global search input placeholder (`Cmd+K`), notification bell icon with mock unread count, user avatar dropdown. Styled per mockup header.
- [ ] TASK-003 — **Build `<Sidebar>` component.** Navigation items: Dashboard (grid icon), Plans (folder icon), Skills (puzzle icon), Roles (person icon), Settings (gear icon). Active route has accent left-border. Collapsed = icon-only.
- [ ] TASK-004 — **Build `<NotificationBell>` with dropdown.** Clicking opens a 360px dropdown listing mock notifications from `/api/notifications`. Shows type icon, plan name, timestamp, read/unread indicator.

Files:
```
[NEW]  src/components/layout/AppShell.tsx
[NEW]  src/components/layout/TopBar.tsx
[NEW]  src/components/layout/Sidebar.tsx
[NEW]  src/components/layout/NotificationBell.tsx
[MOD]  src/app/layout.tsx                     (wrap with AppShell)
```

Acceptance criteria:
- Shell renders consistently, sidebar toggle ≤200ms CSS transition.
- Navigation routes work correctly.
- Top bar remains sticky on scroll.

depends_on: [EPIC-002]

---

## EPIC-004 — Dashboard: Stats Row & Plan Grid

Roles: engineer
Objective: Build the Dashboard landing page — four metric cards at top and a filterable plan card grid. All data fetched from mock API routes.

### Definition of Done
- [ ] Four metric cards display: Total Plans, Active EPICs, Completion Rate, Escalations from `/api/stats`.
- [ ] Plan grid renders all plans from `/api/plans` as cards with progress rings.
- [ ] Filtering by status and domain works client-side.
- [ ] Grid/table view toggle.
- [ ] Plan cards are clickable (navigate to `/plans/[id]`).
- [ ] Loading skeletons render while data fetches.

### Tasks
- [ ] TASK-001 — **Build `<MetricCard>` component.** Props: label, value, trend, color. Count-up animation on load. Loading skeleton.
- [ ] TASK-002 — **Build `<StatsRow>` container.** Fetches `/api/stats` via SWR hook. Renders four `<MetricCard>` instances.
- [ ] TASK-003 — **Build `<PlanCard>` component.** Shows: domain tag, title, goal excerpt, progress ring, EPIC fraction, role avatars, alert indicator.
- [ ] TASK-004 — **Build `<ProgressRing>` SVG component.** Circular progress, color thresholds (green >70%, amber 30-70%, red <30%).
- [ ] TASK-005 — **Build `<PlanGrid>` container.** Fetches `/api/plans` via SWR. Card grid layout with `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`.
- [ ] TASK-006 — **Build `<FilterBar>` component.** Status multi-select, domain multi-select, search input (200ms debounce), sort dropdown. Filters combine with AND logic.
- [ ] TASK-007 — **Build empty state.** "No plans match your filters" with "Clear Filters" button.

Files:
```
[NEW]  src/components/dashboard/MetricCard.tsx
[NEW]  src/components/dashboard/StatsRow.tsx
[NEW]  src/components/dashboard/PlanCard.tsx
[NEW]  src/components/dashboard/ProgressRing.tsx
[NEW]  src/components/dashboard/PlanGrid.tsx
[NEW]  src/components/dashboard/FilterBar.tsx
[MOD]  src/app/page.tsx                       (compose Dashboard)
```

Acceptance criteria:
- Dashboard renders with data from mock API (no direct mock import in components).
- Filter produces correct subsets. Sort works in both directions.
- Plan cards navigate to Plan Workspace.
- Loading skeleton → data transition has no layout shift.

depends_on: [EPIC-003]

---

## EPIC-005 — Plan Workspace: Layout, Tabs & Kanban

Roles: engineer
Objective: Build the Plan Workspace — three-panel layout with left sidebar (plan metadata + tab nav), center panel (EPICs Kanban as default tab), and right contextual panel. Data from `/api/plans/[id]` and `/api/plans/[id]/epics`.

### Definition of Done
- [ ] Three-panel layout: left (240px), center (flexible), right (360px collapsible).
- [ ] Tab navigation: EPICs (Kanban), Roles & Models, Skills, DAG (placeholder), Settings.
- [ ] Kanban board renders EPIC cards grouped by lifecycle state columns.
- [ ] EPIC cards show: ref badge, title, task progress bar, role avatar, state badge.
- [ ] Clicking an EPIC card opens quick view in right panel.
- [ ] Breadcrumb: Dashboard > Plan Name.

### Tasks
- [ ] TASK-001 — **Build `<PlanWorkspace>` root.** Fetches plan + epics via SWR hooks. Three-panel CSS Grid. React Context provides plan data to children.
- [ ] TASK-002 — **Build `<PlanSidebar>` (left panel).** Plan title, status badge, goal description, tab navigation list (EPICs with count, Roles, Skills, DAG, Settings).
- [ ] TASK-003 — **Build `<WorkspaceTabs>` content switcher.** Lazy-load tab content. URL updates: `/plans/:id?tab=roles`. Default tab = epics.
- [ ] TASK-004 — **Build `<KanbanBoard>` container.** Columns ordered by lifecycle: Pending → Engineering → QA Review → Fixing → Manager Triage → Passed → Signoff. `display: flex; overflow-x: auto; gap: 16px`.
- [ ] TASK-005 — **Build `<KanbanColumn>` component.** Column header: state name + count badge. Column background: state color at 5% opacity. Min-width: 260px.
- [ ] TASK-006 — **Build `<EpicCard>` component.** EPIC ref badge, title (2 lines max), task progress bar, role avatar, state micro-badge. Left border: 3px solid state color. Hover: shadow + translateY(-1px).
- [ ] TASK-007 — **Build `<ContextPanel>` (right panel).** Collapsible. When EPIC clicked: shows EPIC quick view (title, status, tasks preview, "Open Full Detail" link). Default: plan progress summary.
- [ ] TASK-008 — **Build `<PlanBreadcrumb>`.** Dashboard / Plan Name. Each segment is a link.

Files:
```
[NEW]  src/components/plan/PlanWorkspace.tsx
[NEW]  src/components/plan/PlanSidebar.tsx
[NEW]  src/components/plan/WorkspaceTabs.tsx
[NEW]  src/components/plan/KanbanBoard.tsx
[NEW]  src/components/plan/KanbanColumn.tsx
[NEW]  src/components/plan/EpicCard.tsx
[NEW]  src/components/plan/ContextPanel.tsx
[NEW]  src/components/plan/PlanBreadcrumb.tsx
[MOD]  src/app/plans/[id]/page.tsx            (render PlanWorkspace)
```

Acceptance criteria:
- Three-panel layout maintains proportions on resize.
- Kanban columns ordered by lifecycle precedence.
- EPIC cards show correct data from mock API.
- Tab switching via URL query param works.

depends_on: [EPIC-004]

---

## EPIC-006 — Epic Detail Page (Three-Panel Layout per Mockup)

Roles: engineer
Objective: Build the Epic Detail page matching `mockup.html` exactly — sticky header, three-panel layout (task checklist sidebar → lifecycle visualizer center → QA/role overrides right), and channel feed footer. This is the **highest-fidelity** screen. All data from mock API.

### Definition of Done
- [ ] Page loads via `/plans/[id]/epics/[ref]` with data from mock API.
- [ ] Sticky header shows: breadcrumb (Plan > EPIC ref), EPIC title, status badge, action buttons (Advance State, Retry, Escalate, Edit).
- [ ] Left panel (w-72): Task Checklist with checkboxes, task IDs, descriptions, role badges, drag handles.
- [ ] Center panel: Lifecycle Visualizer with state nodes, transition arrows, current-state glow.
- [ ] Right panel (w-80): QA section (DoD checklist + Acceptance Criteria) and Role Overrides.
- [ ] Footer: Channel Feed with terminal-style dark background, message timeline, filter chips.
- [ ] Layout matches `mockup.html` pixel-for-pixel where possible.

### Tasks
- [ ] TASK-001 — **Build `<EpicDetailPage>` root.** Route: `/plans/[id]/epics/[ref]`. Fetches epic config, lifecycle, messages from mock API. Layout: `flex flex-col h-screen`.
- [ ] TASK-002 — **Build `<EpicHeader>` sticky component.** Per mockup: breadcrumb nav, EPIC ref + title + status badge, action buttons (Advance State, Retry, Escalate, Edit). Sticky below app shell top bar.
- [ ] TASK-003 — **Build `<TaskChecklistPanel>` (left sidebar).** Per mockup: header "Task Checklist" with fraction badge (3/5), scrollable task list. Each task: checkbox, T-ID (mono), description, role badge, drag handle. Completed tasks: strikethrough + muted. Active task: blue border highlight. Pending: default border.
- [ ] TASK-004 — **Build `<LifecycleVisualizer>` (center panel).** Per mockup: header "Lifecycle Visualizer" with agent/built-in legend, dot-grid background. State nodes as cards: current state (blue bg, larger, `state-node-pulse` animation, "Current State" badge), completed (solid blue bg), future (dashed border, opacity-60). Transition labels (done/fail) between nodes. Arrow connectors between states.
- [ ] TASK-005 — **Build `<QAPanel>` (right top half).** Per mockup: "Quality Assurance" header. Definition of Done checklist with verified/unverified states, verifier + timestamp. Acceptance Criteria cards with Passed/Pending status, colored left border, italic text.
- [ ] TASK-006 — **Build `<RoleOverridesPanel>` (right bottom half).** Per mockup: "Role Overrides" header. Role cards showing: role name, "Overridden" vs "Inherited" badge, model override (strikethrough old → bold new), added skills as badges. Inherited roles show "Using default Plan-level configurations."
- [ ] TASK-007 — **Build `<ChannelFeed>` footer.** Per mockup: dark terminal background, header with "Channel Feed" + filter pills (All, Tasks, Escalations) + auto-scroll toggle + settings. Alert banner (warning: "Action required…" with "Approve Execution" button). Message timeline grouped by state transitions. Each message: role avatar badge (SYS/DA), sender label (colored), type badge, timestamp, body text. Security intercept messages highlighted in yellow. Blinking cursor "Waiting for approval…" at bottom.
- [ ] TASK-008 — **Build `<StateNode>` component.** Reusable lifecycle state node matching mockup: rounded-lg card with state label, title, role avatar + name, type badge (Agent/Built-in), timestamp. Supports variants: current (pulse + shadow), completed (solid), future (dashed + opacity).
- [ ] TASK-009 — **Build `<ChannelMessage>` component.** Per mockup: role avatar box (SYS/DA/etc), sender name (colored by role), type badge (Task/Design-Guidance/Intercept), timestamp, body text. Security messages use yellow accent styling.

Files:
```
[NEW]  src/components/epic/EpicDetailPage.tsx
[NEW]  src/components/epic/EpicHeader.tsx
[NEW]  src/components/epic/TaskChecklistPanel.tsx
[NEW]  src/components/epic/LifecycleVisualizer.tsx
[NEW]  src/components/epic/QAPanel.tsx
[NEW]  src/components/epic/RoleOverridesPanel.tsx
[NEW]  src/components/epic/ChannelFeed.tsx
[NEW]  src/components/epic/StateNode.tsx
[NEW]  src/components/epic/ChannelMessage.tsx
[MOD]  src/app/plans/[id]/epics/[ref]/page.tsx (render EpicDetailPage)
```

Acceptance criteria:
- Epic Detail page matches `mockup.html` layout and styling when compared side-by-side.
- All data renders correctly from mock API.
- Header action buttons are present and styled (mock handlers — console.log on click).
- Channel feed renders messages in chronological order with correct grouping.
- `state-node-pulse` animation works on current state node.

depends_on: [EPIC-005]

---

## EPIC-007 — Role & Model Configuration Tab

Roles: engineer
Objective: Build the Roles & Models tab in the Plan Workspace — a data table of roles with a slide-over editor panel. All CRUD operations go to `/api/roles` mock endpoints.

### Definition of Done
- [ ] Roles table lists all roles with: name, provider icon, model version, temperature, budget, skills, actions.
- [ ] "Edit" opens a slide-over panel (420px) with full configuration form.
- [ ] "Test Connection" button simulates a model health check (mock: always returns OK after 300ms).
- [ ] Role creation, editing, and deletion mutate mock data and revalidate SWR cache.
- [ ] Form validates: duplicate names, temperature range, empty fields.

### Tasks
- [ ] TASK-001 — **Build `<RolesTable>`.** Full-width table, sticky header, sortable columns, empty state with "+ Add Role" CTA.
- [ ] TASK-002 — **Build `<RoleEditorPanel>` slide-over.** Sections: Identity (name + presets), Model Binding (provider cards + version list), Parameters (temperature slider, budget, retries, timeout), Skills (chip input with search), Advanced (system prompt textarea).
- [ ] TASK-003 — **Build `<ProviderSelector>` component.** Three card buttons: Claude, GPT, Gemini. Brand colors. Selection triggers version list filter.
- [ ] TASK-004 — **Build `<TestConnectionButton>`.** Mock: `POST /api/roles/[id]/test` returns `{ ok: true, latency_ms: 340 }` after 300ms. Shows green "✓ OK — 340ms" result.
- [ ] TASK-005 — **Build `<SkillChipInput>`.** Multi-select with search dropdown. Shows attached skills as removable chips. Dropdown filters from `/api/skills`.

Files:
```
[NEW]  src/components/roles/RolesTable.tsx
[NEW]  src/components/roles/RoleEditorPanel.tsx
[NEW]  src/components/roles/ProviderSelector.tsx
[NEW]  src/components/roles/TestConnectionButton.tsx
[NEW]  src/components/roles/SkillChipInput.tsx
[MOD]  src/app/roles/page.tsx                 (render RolesTable)
```

Acceptance criteria:
- Roles table shows data from mock API. Sorting and empty state work.
- Editor panel validates fields before save.
- Test Connection shows simulated result.
- Skills chip input searches and filters correctly.

depends_on: [EPIC-005]

---

## EPIC-008 — Skill Library Tab

Roles: engineer
Objective: Build the Skill Library — a searchable card grid of skills with category filtering, detail modal, and attach/detach toggle. All data from `/api/skills`.

### Definition of Done
- [ ] Skill Library renders all skills in a card grid from `/api/skills`.
- [ ] Search filters skills by name and description in real-time (200ms debounce).
- [ ] Category filter pills toggle skill visibility.
- [ ] Skill detail modal shows full description, applicable roles, and instruction template.
- [ ] Attach/detach toggle updates SWR cache.

### Tasks
- [ ] TASK-001 — **Build `<SkillLibrary>` container.** Search input, category filter pills, summary badges, card grid.
- [ ] TASK-002 — **Build `<SkillCard>`.** Left accent border by category, name + version, description (2-line clamp), role pills, usage count, attach/detach button.
- [ ] TASK-003 — **Build `<SkillDetailModal>`.** Full description, applicable roles, instruction template (monospace), version history, attach/detach button.
- [ ] TASK-004 — **Build category filter system.** Color-coded pills, multi-toggle, OR logic. Categories: implementation, review, testing, writing, analysis, compliance, triage.
- [ ] TASK-005 — **Build skill sorting.** Dropdown: Name A-Z, Most Used, Recently Updated, Category.

Files:
```
[NEW]  src/components/skills/SkillLibrary.tsx
[NEW]  src/components/skills/SkillCard.tsx
[NEW]  src/components/skills/SkillDetailModal.tsx
[MOD]  src/app/skills/page.tsx                (render SkillLibrary)
```

Acceptance criteria:
- Skill grid renders from mock API. Search returns results within 200ms debounce.
- Category filter shows/hides correctly. Detail modal shows instruction template.
- Attach/detach is reflected in card badge.

depends_on: [EPIC-005]

---

## EPIC-009 — DAG Dependency Viewer (Placeholder)

Roles: engineer
Objective: Build a simplified DAG visualization for the Plan Workspace "DAG" tab. Uses pre-computed positions from mock data. Full D3/Dagre integration is deferred.

### Definition of Done
- [ ] DAG tab renders EPIC nodes as styled cards with status colors.
- [ ] Directed edges (SVG lines) connect dependent EPICs.
- [ ] Critical path edges are visually distinct (thicker, colored).
- [ ] Nodes are clickable (navigate to EPIC detail).

### Tasks
- [ ] TASK-001 — **Build `<DAGViewer>` component.** SVG canvas with pre-computed node positions from `/api/plans/[id]/dag`. Nodes as `<StateNode>` (reused from EPIC-006). Edges as SVG paths.
- [ ] TASK-002 — **Build `<DAGEdge>` component.** SVG line with arrowhead. Critical path = thicker + colored. Non-critical = dashed gray. Hover tooltip with dependency info.
- [ ] TASK-003 — **Build DAG toolbar.** Zoom in/out buttons (transform scale), fit-to-view, highlight critical path toggle.

Files:
```
[NEW]  src/components/plan/DAGViewer.tsx
[NEW]  src/components/plan/DAGEdge.tsx
```

Acceptance criteria:
- DAG renders all plan EPICs with correct dependency edges.
- Critical path is visually distinct.
- Nodes are clickable and navigate to EPIC detail.

depends_on: [EPIC-005]

---

## EPIC-010 — Plan Progress Footer

Roles: engineer
Objective: Build the Plan Workspace sticky footer showing at-a-glance plan health and an expandable analytics overlay panel.

### Definition of Done
- [ ] Progress footer is sticky at bottom of Plan Workspace (56px height).
- [ ] Shows: progress ring, critical path text, current wave, active EPIC count, "View Analytics" button.
- [ ] "View Analytics" opens an overlay panel with status breakdown chart and token budget bars.
- [ ] All data from mock API.

### Tasks
- [ ] TASK-001 — **Build `<ProgressFooter>` component.** Sticky footer, horizontal items with vertical dividers. Progress ring + percentage, critical path "2/3", active EPICs "3 in flight", "View Analytics" button.
- [ ] TASK-002 — **Build `<AnalyticsPanel>` overlay.** Slides up from footer (480px). Status breakdown stacked bar, token budget per-EPIC horizontal bars (green/amber/red thresholds).
- [ ] TASK-003 — **Build `<TokenBudgetChart>`.** Horizontal bars with utilization colors. EPIC ref label, usage bar, fraction label.

Files:
```
[NEW]  src/components/plan/ProgressFooter.tsx
[NEW]  src/components/plan/AnalyticsPanel.tsx
[NEW]  src/components/plan/TokenBudgetChart.tsx
```

Acceptance criteria:
- Footer stays visible during all workspace interactions.
- Analytics panel opens/closes smoothly. Charts render from mock data.

depends_on: [EPIC-005]

---

## EPIC-011 — Interactive Features & Mock Mutations

Roles: engineer
Objective: Wire up interactive behaviors that mutate mock data: task checkbox toggle, state advancement, drag-and-drop task reordering, and EPIC drag between Kanban columns. All mutations POST/PATCH to mock API routes.

### Definition of Done
- [ ] Task checkboxes toggle via `PATCH /api/plans/[id]/epics/[ref]/tasks` and update progress bar.
- [ ] "Advance State" button sends `POST /api/plans/[id]/epics/[ref]/state` and updates lifecycle visualizer.
- [ ] Task reordering via drag-and-drop persists new order.
- [ ] Kanban EPIC cards can be dragged between valid lifecycle columns.
- [ ] All mutations optimistically update UI and revalidate SWR.

### Tasks
- [ ] TASK-001 — **Wire task toggle.** Checkbox click → optimistic update → PATCH mock API → SWR revalidation. Update progress bar. Authorization simulation (only matching roles can toggle).
- [ ] TASK-002 — **Wire "Advance State" button.** Click → validation dialog (check uncompleted DoD items) → confirmation → POST mock API → animate lifecycle visualizer to new state.
- [ ] TASK-003 — **Implement drag-and-drop task reordering.** `@dnd-kit/sortable` on task list. Dragged task shows floating copy. Drop sends new order to mock API.
- [ ] TASK-004 — **Implement Kanban drag-and-drop.** `@dnd-kit/core` on Kanban board. Only allow drops on valid lifecycle transition columns. Invalid targets show red overlay. On valid drop: optimistic move + mock API call.
- [ ] TASK-005 — **Build `<AdvanceStateDialog>` component.** Confirmation dialog: current state → target state, unchecked DoD items list, confirm/cancel buttons.

Files:
```
[MOD]  src/components/epic/TaskChecklistPanel.tsx  (add toggle handler)
[MOD]  src/components/epic/EpicHeader.tsx          (wire Advance State)
[NEW]  src/components/epic/AdvanceStateDialog.tsx
[MOD]  src/components/plan/KanbanBoard.tsx         (add dnd-kit)
[MOD]  src/components/plan/EpicCard.tsx             (draggable)
```

Acceptance criteria:
- Task toggle immediately updates checkbox state and progress bar.
- Advance State is blocked when DoD items are unchecked (dialog shown).
- Drag-and-drop reorder persists. Kanban drag validates lifecycle transitions.

depends_on: [EPIC-006]

---

## EPIC-012 — Simulated Real-Time Updates

Roles: engineer
Objective: Simulate real-time behavior without WebSocket. Use SWR polling + the mock realtime service from EPIC-001 to periodically update dashboard stats, progress rings, and inject new channel messages.

### Definition of Done
- [ ] Dashboard stats auto-refresh every 10s via SWR `refreshInterval` when `NEXT_PUBLIC_ENABLE_MOCK_REALTIME=true`.
- [ ] Plan cards reflect progress changes smoothly (no full reload).
- [ ] Connection status indicator in top bar (green dot = simulated "connected").
- [ ] New channel messages appear in feed with fade-in animation.
- [ ] Escalation toast notifications appear at bottom-right when simulated.

### Tasks
- [ ] TASK-001 — **Configure SWR polling.** When env var enabled: set `refreshInterval: 10000` on stats and plan hooks. Mock API routes randomly adjust values slightly on each call.
- [ ] TASK-002 — **Build `<ConnectionStatus>` indicator.** 8px dot in top bar. Green = "connected" (simulated), gray = "off" (mock realtime disabled). Tooltip shows status.
- [ ] TASK-003 — **Build `<ToastNotification>` component.** Bottom-right floating toast. Auto-dismiss 8s. Max 3 stacked. Triggered by mock realtime events.
- [ ] TASK-004 — **Animate updates.** Progress ring animates from old→new value. New messages slide in with opacity fade. Stat card values count-up on change.

Files:
```
[MOD]  src/hooks/use-stats.ts                 (conditional refreshInterval)
[MOD]  src/hooks/use-plans.ts                 (conditional refreshInterval)
[NEW]  src/components/layout/ConnectionStatus.tsx
[NEW]  src/components/ui/ToastNotification.tsx
[MOD]  src/components/layout/TopBar.tsx        (add ConnectionStatus)
```

Acceptance criteria:
- With mock realtime enabled, stats visibly update every ~10s.
- Toast notifications appear and auto-dismiss.
- Without env var, no polling occurs (stable static display).

depends_on: [EPIC-004]

---

## EPIC-013 — Dark Mode, Accessibility & Polish

Roles: engineer
Objective: Production-ready polish pass. Dark mode for all components, keyboard navigation, accessibility audit, and responsive adjustments.

### Definition of Done
- [ ] Dark mode renders correctly across all screens (no un-themed elements).
- [ ] All interactive elements are keyboard-navigable with ARIA labels.
- [ ] Keyboard shortcuts: `Cmd+K` (search), `?` (help overlay).
- [ ] Responsive layout: sidebar auto-collapses at 1024px, stats stack 2×2.
- [ ] Channel feed `state-node-pulse` and scrollbar styles match mockup.

### Tasks
- [ ] TASK-001 — **Dark mode pass.** Audit every component for CSS variable usage. Dark theme: background #0F172A, surface #1E293B, text #F1F5F9, border #334155. Test all screens.
- [ ] TASK-002 — **Keyboard shortcuts.** `Cmd+K` opens search, `?` opens help overlay, `J`/`K` to navigate plan cards, `Enter` to open.
- [ ] TASK-003 — **ARIA labels and roles.** `role="main"`, `role="navigation"`, `role="search"`, `role="log"` on channel feed. `aria-label` on all icon buttons.
- [ ] TASK-004 — **Responsive adjustments.** 1024-1280px: sidebar auto-collapses, stats 2×2 grid, plan grid 2 columns.
- [ ] TASK-005 — **Polish pass.** Verify all animations match mockup timing. Custom scrollbar styles. Focus rings on keyboard navigation.

Files:
```
[MOD]  src/app/globals.css                    (dark mode tokens audit)
[MOD]  Multiple component files               (ARIA, responsive, dark mode)
[NEW]  src/components/ui/KeyboardShortcutHelp.tsx
```

Acceptance criteria:
- Dark mode toggle produces no white flashes or invisible text.
- All interactive elements reachable via Tab key with visible focus rings.
- Lighthouse accessibility score ≥ 90.
- Layout adapts cleanly at 1024px breakpoint.

depends_on: [EPIC-006]

---

## EPIC-014 — Build Verification & Backend Swap Preparation

Roles: engineer
Objective: Ensure the full application builds successfully for static export and prepare the mock API layer for easy swap to real backend.

### Definition of Done
- [ ] `bun run build` completes without errors.
- [ ] All pages render correctly in production build.
- [ ] `src/lib/api-client.ts` supports a `NEXT_PUBLIC_API_BASE_URL` env var for backend swap.
- [ ] Documentation in `README.md` explains: how to run with mock API, how to swap to real backend.
- [ ] All mock API routes have `// MOCK: Replace with proxy to FastAPI` comments.

### Tasks
- [ ] TASK-001 — **Fix build errors.** Resolve any dynamic route issues for static export. Ensure all pages have proper `generateStaticParams` if needed.
- [ ] TASK-002 — **Add backend swap config.** `api-client.ts` reads `NEXT_PUBLIC_API_BASE_URL` — if set, all API calls go to that URL instead of local routes. Default: empty (uses local API routes).
- [ ] TASK-003 — **Update README.md.** Document: `bun run dev` (mock API), `NEXT_PUBLIC_API_BASE_URL=http://localhost:9000/api bun run dev` (real backend), and the mock realtime toggle.
- [ ] TASK-004 — **Add swap comments to mock routes.** Each `src/app/api/` route gets a header comment explaining what real endpoint it simulates and how to swap.

Files:
```
[MOD]  src/lib/api-client.ts                  (env var support)
[MOD]  README.md                              (setup docs)
[MOD]  src/app/api/**                         (swap comments)
[MOD]  next.config.ts                         (build config if needed)
```

Acceptance criteria:
- `bun run build` exits 0.
- Setting `NEXT_PUBLIC_API_BASE_URL` redirects all API calls correctly.
- README is clear enough for a new team member to run the project in 5 minutes.

depends_on: [EPIC-013]