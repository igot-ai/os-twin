<!-- MANAGER INSTRUCTION:
This plan redesigns the Ostwin Dashboard into a modern AI assistant interface inspired by Claude's
conversational UI. Key changes:
1. "Home" tab — A warmly greeted, conversational home screen with centered prompt
2. Sidebar — Left panel with 5-tab navigation + scrollable project/conversation history
3. Settings page enhanced — Extends existing Settings with MCP/Channel connection status
4. Plan Management — Full CRUD lifecycle for plans with real-time progress

Theme note: Light theme is the DEFAULT. Dark mode is a user-selectable option available
through the existing Settings > Appearance toggle (Light / Dark / System). Do NOT design
the home screen or any page for dark-first — all default styling must look great in light mode.

The sidebar keeps the same tabs shown in the current UI: Home (replaces Dashboard),
Plans, Skills, Roles, Settings. No new sidebar tabs — connections are managed through
the existing Settings, MCP, and Channels pages.

Every Epic below has a dynamically designed closed-loop lifecycle optimized for the specific
roles assigned. Not all epics require the same agent composition.
-->

# Plan: Ostwin Dashboard V2 — Command Center Redesign

> Created: 2026-04-01T11:00:00+07:00
> Status: draft
> Project: /mnt/e/OS Twin/os-twin

## Config

working_dir: /mnt/e/OS Twin/os-twin

---

## Goal

Redesign the Ostwin Dashboard into a modern, AI-assistant-style command center. The UI must feel like a premium conversational interface — not a generic admin panel. The redesign introduces:

1. **"Home" tab** — Replaces "Dashboard" as the primary landing page. A clean, prompt-centric welcome screen inspired by Replit Agent's home layout: workspace identity at top center, a bold greeting ("Hi [User], what do you want to build?"), a rounded prompt bar with `+` button and "Plan" mode chip, a horizontal plan-type category carousel (sourced from plan templates), rotating example prompt suggestions, and a "Your recent Plans" card grid. All data is dynamic — username from `/api/auth/me`, categories from `/api/plans/templates`, suggestions from `/api/prompts/examples`, and recent plans from `/api/plans/recent`. Dark mode is a user-selectable option in Settings — not the default.
2. **Sidebar with History** — A logically structured left sidebar with 5 tabs (matching the current UI) plus a scrollable history zone showing both recent conversations and plans, merged by last activity and grouped by time period.
3. **Enhanced Settings** — The existing Settings page already handles API Configuration, Appearance (Light/Dark/System), and API Keys. Connection management stays in the existing MCP and Channels pages — no separate "Connections" tab needed.
4. **Project (Plan) Management** — Full create, run, monitor, edit, duplicate, archive lifecycle.

### Complete Sidebar Navigation Structure

The sidebar keeps the **same 5 tabs** as the current UI (renaming "Dashboard" → "Home"), plus adds a scrollable project history zone below the navigation.

```
┌─────────────────────────────┐
│ ⬡ OsTwin                   │
│   Command Center        🔍  │  ← Search button
├─────────────────────────────┤
│ 🏠  Home        ← renamed  │  ← Tab bar: 5 items
│ 📁  Plans                   │     (same as current sidebar,
│ 🧩  Skills                  │      "Dashboard" → "Home")
│ 👤  Roles                   │
│ ⚙️  Settings                │
├─────────────────────────────┤
│ ── History ──────────────────  │  ← Scrollable history zone:
│                             │     conversations + plans merged
│ Today                       │
│  💬 Deploy a Telegram bot   │  ← conversation
│  📄 Dashboard V2 Redesign   │  ← plan
│                             │
│ Last 7 days                 │
│  💬 Refactor auth module    │  ← conversation
│  📄 Coffee Price Pipeline   │  ← plan
│                             │
│ Older                       │
│  📄 Vietnam Monitor         │
│  📄 Hello World Test        │
├─────────────────────────────┤
│ 👤 [User] · Free plan       │
│ ↕  Collapse                 │
└─────────────────────────────┘
```

### Connection Management (leveraging existing pages)

Connections are **already managed** across existing pages — no new sidebar tab required:

| What | Where | Already Exists? |
|------|-------|-----------------|
| API Keys (Gemini, Claude, GPT) | **Settings** page → "API Keys" section | ✅ Yes (fully built) |
| API Configuration (backend URL, WS) | **Settings** page → "API Configuration" | ✅ Yes |
| Theme / Appearance | **Settings** page → "Appearance" | ✅ Yes |
| Telegram, Discord, Slack connectors | **Channels** page (`/channels`) | ✅ Yes (setup wizards, pairing, etc.) |
| MCP builtin + extension servers | **MCP** page (`/mcp`) | ✅ Yes (table + add dialog) |
| MCP vault credentials | **MCP** page (per-server) | ✅ Yes |

The **Home screen's "Connect your tools" toolbar** links to Settings (for API keys) and MCP/Channels pages (for servers/platforms). These existing pages will be enhanced with health indicators and better UX, but no new top-level route is needed.

---

## EPIC-001 — Research & UI/UX Design

Roles: researcher, ui-designer
Objective: Research modern AI assistant UIs (Replit Agent, Claude, Cursor), decompose the Replit Agent reference screenshot, and produce a comprehensive design specification for the Home tab and Sidebar with project history.
Lifecycle:
```text
pending → researcher → ui-designer ─┬─► passed → signoff
              ▲                      │
              └── researcher ◄───────┘ (on fail → fixing)
```

Tasks: Analyze the Replit Agent home screen reference (workspace identity, centered greeting + prompt, plan type carousel, example prompt chips, recent projects grid). Produce design spec.

### Definition of Done
- [ ] Design spec document covers all 5 pages (Home, Plans, Skills, Roles, Settings)
- [ ] Sidebar information architecture with project history grouping is documented
- [ ] Plan-type category carousel and example prompt chip patterns are documented
- [ ] "Your recent Plans" card grid layout is documented
- [ ] Design tokens confirmed against existing `globals.css` (no new tokens)

### Tasks
- [ ] TASK-001 — Decompose Replit Agent home screen into atomic design elements:
  - **Top center**: Workspace/project identity badge with avatar + dropdown
  - **Greeting**: Large bold centered text — "Hi [User], what do you want to build?"
  - **Prompt bar**: Rounded input with `+` button (left), "Plan" mode chip + submit arrow (right)
  - **Plan type carousel**: Horizontal scrollable row of circular category icons with labels (e.g. Website, Mobile, Backend) — with left/right navigation arrows
  - **Example prompts**: "Try an example prompt 🔄" with rotating suggestion chips
  - **Recent projects**: "Your recent Plans" section header with "View All →" link, card grid below
  - **Sidebar**: Logo area, tab navigation (5 items), conversation list with time groupings, user footer
- [ ] TASK-002 — Map all connectable subsystems to their existing management pages:
  - **External Platforms** (Telegram, Discord, Slack) → existing `/channels` page
  - **MCP Servers** (channel, warroom, memory, serena, context7, ai-game-developer, stitch, github) → existing `/mcp` page
  - **MCP Catalog** (chrome-devtools, nanobanana) → existing `/mcp` page
  - **API Keys** (Gemini, Claude, GPT) → existing `/settings` page
  - **Vault Credentials** → existing `/mcp` page (per-server config)
- [ ] TASK-003 — Design sidebar information architecture:
  - Fixed top zone: 5 tab-style nav items (Home, Plans, Skills, Roles, Settings) — matches current sidebar layout
  - Scrollable bottom zone: Project history grouped by time ("Today", "Last 7 days", "Last 30 days", "Older")
  - Each project entry: Plan title (truncated), status dot, last activity timestamp
  - Collapsed mode: Icons only for tabs, project history hidden
- [ ] TASK-004 — Create wireframe spec document (`dashboard/PRD/dashboard-v2-wireframe.md`)
- [ ] TASK-005 — Document and confirm the existing Ostwin design tokens used by all new components:
  - All new components MUST use the existing CSS variables from `globals.css` — no new tokens:
    - Backgrounds: `var(--color-background)`, `var(--color-surface)`, `var(--color-surface-hover)`
    - Text: `var(--color-text-main)`, `var(--color-text-muted)`, `var(--color-text-faint)`
    - Brand: `var(--color-primary)`, `var(--color-primary-hover)`, `var(--color-primary-muted)`
    - Borders: `var(--color-border)`, `var(--color-border-light)`
    - Status: `var(--color-success)`, `var(--color-warning)`, `var(--color-danger)`
    - Fonts: `var(--font-display)` (Plus Jakarta Sans), `var(--font-mono)` (IBM Plex Mono)
    - Shadows: `var(--shadow-card)`, `var(--shadow-card-hover)`, `var(--shadow-modal)`
    - Radii: `var(--radius-sm/md/lg/xl/2xl/full)`
  - The greeting brand mark uses the existing ⬡ hexagon logo SVG with `--color-primary` as its fill (consistent with the brand)
  - Dark mode is already handled by `[data-theme="dark"]` in `globals.css` — no new overrides needed

### Acceptance Criteria
- All 5 dashboard pages have wireframe layouts
- Sidebar IA covers both 5 fixed nav tabs and scrollable project history
- Home screen layout spec covers: workspace badge, greeting, prompt, category carousel, example prompts, and recent plans grid
- All new components exclusively use the existing Ostwin CSS variables — no ad-hoc colors or hardcoded values

depends_on: []

---

## EPIC-002 — Sidebar Redesign with Project History & Conversation History

Roles: frontend-engineer, qa
Objective: Rebuild the sidebar with a 5-tab navigation (Home, Plans, Skills, Roles, Settings) and a scrollable history zone showing **both recent plans and recent conversations** grouped by time period — similar to Claude's sidebar conversation list.
Working_dir: dashboard/fe
Lifecycle:
```text
pending → frontend-engineer → qa ─┬─► passed → signoff
              ▲                    │
              └─ frontend-engineer ◄┘ (on fail → fixing)
```

Tasks: Redesign `Sidebar.tsx` with two distinct zones. The navigation zone has 5 tabs. The history zone is new — it shows conversations and plans from the API, interleaved and grouped into time buckets (conversations appear inline with plans since both represent work sessions).

### Definition of Done
- [ ] Sidebar renders with 5-tab nav bar and scrollable history zone
- [ ] History zone shows both conversations and plans grouped by time period
- [ ] Clicking a conversation item navigates to `/c/{conversation-id}` and restores the chat
- [ ] Clicking a plan item navigates to `/plans/{plan-id}`
- [ ] User footer shows name, tier badge, and collapse toggle
- [ ] Collapsed mode: tabs show icons only, history zone hidden

### Tasks
- [ ] TASK-001 — Create `SidebarTabBar.tsx` component:
  - 5 nav items in vertical list matching current UI:
    - Home (home icon) — replaces "Dashboard" (grid_view icon)
    - Plans (folder icon) — same as current
    - Skills (extension icon) — same as current
    - Roles (person icon) — same as current
    - Settings (settings icon) — same as current
  - Active state: light brand-tinted background + brand color icon/text + left accent bar
  - Inactive state: muted icon + text, hover highlights
  - Note: MCP and Channels remain accessible from their existing pages — NOT in the main sidebar tabs
- [ ] TASK-002 — Create `SidebarHistory.tsx` component (replaces `ProjectHistory.tsx`):
  - Fetches both conversations and plans from API via SWR:
    - `GET /api/conversations?limit=50` — returns conversation summaries
    - `GET /api/plans/recent` — returns plan summaries
  - Merges the two lists, sorted by `last_activity_at` descending
  - Groups into time buckets: "Today", "Last 7 days", "Last 30 days", "Older"
  - Each group has a collapsible section header (small caps, muted text)
  - Empty state: "No history yet. Start a conversation or create a plan."
  - "+ New conversation" button at the top of the history zone — navigates to `/` (empty home state)
- [ ] TASK-003 — Create `SidebarHistoryItem.tsx` component:
  - Unified item for both conversations and plans:
    - **Conversation item**: chat bubble icon (subtle) + conversation title (auto-generated from first message, truncated ~24 chars) + time-ago
    - **Plan item**: folder icon (subtle) + plan title + status dot (🟢/🟡/🔵/🔴)
  - Click:
    - Conversation → navigates to `/c/{conversation-id}`
    - Plan → navigates to `/plans/{plan-id}`
  - Active item highlighted with `var(--color-primary-muted)` background + left accent bar
  - Hover: subtle background highlight
  - Right-click / three-dot menu:
    - Conversation: Rename, Delete
    - Plan: Open, Duplicate, Archive, Delete
- [ ] TASK-004 — Create `SidebarUserFooter.tsx` component:
  - User initials circle (gradient background)
  - User name (from `/api/auth/me` or OS username)
  - Tier badge: reserved space only — empty `<span>` placeholder
  - Collapse toggle chevron button
- [ ] TASK-005 — Refactor `Sidebar.tsx` to compose new sub-components:
  - Structure: Logo → TabBar (fixed) → Divider → SidebarHistory (scrollable, flex-1) → UserFooter (fixed)
  - Update `navItems` array:
    ```ts
    const navItems = [
      { href: '/', icon: 'home', label: 'Home' },
      { href: '/plans', icon: 'folder', label: 'Plans' },
      { href: '/skills', icon: 'extension', label: 'Skills' },
      { href: '/roles', icon: 'person', label: 'Roles' },
      { href: '/settings', icon: 'settings', label: 'Settings' },
    ];
    ```
  - Remove old "Dashboard" (grid_view), "MCP" (terminal), and "Channels" (hub) entries
- [ ] TASK-006 — Implement sidebar collapsed behavior:
  - When collapsed: tab bar shows icons only, history section is hidden entirely
  - User footer shows only the initials circle and collapse toggle
  - Hover on collapsed icon shows tooltip with label
- [ ] TASK-007 — Add search shortcut button:
  - Small search icon/button in the sidebar header area (next to logo)
  - Click triggers `SearchModal` (Cmd+K / Ctrl+K)
  - Search modal searches across: plans, conversations, skills, MCP servers
- [ ] TASK-008 — Write tests:
  - Sidebar renders all 5 nav tabs
  - History zone shows both conversations and plans merged and grouped
  - Clicking conversation item navigates to `/c/{id}`
  - Clicking plan item navigates to `/plans/{id}`
  - Collapsed mode hides labels and history
  - Active conversation highlighted correctly

### Acceptance Criteria
- Sidebar has exactly 5 tabs: Home, Plans, Skills, Roles, Settings
- History zone shows both conversations and plans, merged by last activity time, grouped by period
- Clicking a conversation navigates to its permalink and restores the full chat
- Clicking a plan navigates to the plan detail page
- "+ New conversation" at top of history zone resets to empty home state
- Collapsed sidebar shows only icons for tabs

depends_on: [EPIC-001]

---

## EPIC-003 — Home Screen Redesign (Prompt-Centric Hub)

Roles: frontend-engineer, backend-engineer, qa
Objective: Transform the dashboard home page (`/`) into a prompt-centric command hub inspired by Replit Agent's home layout — a bold greeting, a focused prompt bar, a plan-type category carousel, example prompt suggestions, and a recent plans grid. All content is dynamic — no hardcoded names, categories, or suggestions.
Working_dir: dashboard/fe
Lifecycle:
```text
pending → frontend-engineer → backend-engineer → qa ─┬─► passed → signoff
               ▲                    ▲                 │
               │                    └─ backend-engineer ◄──┤ (on api bug)
               └───────────── frontend-engineer ◄─────────┘ (on ui bug)
```

### Home Screen: Two-State Layout

The home page has **two distinct states**. The welcome content (greeting, carousel, suggestions, recent plans) only exists in the empty state — it must not compete with conversation output.

---

**STATE 1 — Empty (Welcome)** — shown when no conversation is active

```text
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    ⬡ OsTwin Command Center ▾                    │  ← Workspace badge
│                                                                 │
│              Hi [User], what do you want to build?              │  ← Greeting (bold, 32px)
│                    2 plans running · 5 agents active            │  ← Status line (13px, faint)
│                                                                 │
│         ┌──────────────────────────────────────────────┐        │
│         │ + │ Describe your plan, Ostwin will...   │Plan│↗│      │  ← Prompt bar (centered)
│         └──────────────────────────────────────────────┘        │
│                                                                 │
│          ←  ◉ Feature  ◉ Bugfix  ◉ Service  ◉ Custom  →        │  ← Category carousel
│                                                                 │
│          Try an example prompt 🔄                               │
│    [ Deploy a bot ]  [ Refactor auth ]  [ Add MCP server ]      │  ← Suggestion chips
│                                                                 │
│    Your recent Plans                           View All →       │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐                    │  ← Plan cards (max 3)
│    │ Dashboard│  │ Bot Fix  │  │ CaseGNN  │                    │
│    │ ● Running│  │ ✓ Done   │  │ ◎ Draft  │                    │
│    └──────────┘  └──────────┘  └──────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

**STATE 2 — Active (Conversation)** — triggered the moment the user submits their first prompt

```text
┌─────────────────────────────────────────────────────────────────┐
│                    ⬡ OsTwin Command Center ▾                    │  ← Badge stays (shrinks, fixed top)
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [User]  Deploy a Telegram bot that posts war-room updates      │  ← User message bubble
│                                                                 │
│  [Ostwin] ▌ Generating plan...                                  │  ← Streaming agent response
│           Here's a plan for your Telegram bot:                  │
│           ...                                                   │
│                                                                 │
│  [User]  Also add a /status command                             │
│                                                                 │
│  [Ostwin] ▌ Updating plan...                                    │
│                                                                 │
│  (greeting, carousel, suggestions, recent plans — all HIDDEN)   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  + │ Follow-up or new request...                │Plan│↗│        │  ← Prompt anchored to bottom
└─────────────────────────────────────────────────────────────────┘
```

**State transition rules:**
- Empty → Active: fires on first prompt submission. `createConversation()` is called, a new conversation is created server-side, and the browser navigates to `/c/{id}`. Welcome content animates `slideUp + fadeOut` (200ms).
- Active → Empty: fires when the user clicks "New conversation" (calls `resetToHome()`, navigates back to `/`), or navigates to `/` directly from the sidebar.
- The active state is tracked by the **URL** (presence of `/c/[id]`), not client-side storage. There is no sessionStorage involved.
- The workspace badge always stays visible — it becomes a smaller fixed header on the `/c/[id]` route.

---

Tasks: Rebuild `page.tsx` (home) and create supporting components. The Home screen follows the **existing theme** (light by default; dark mode via Settings > Appearance). Every piece of content is API-driven:

1. **Workspace badge**: Top-center identity always visible. In empty state: full-size centered. In active state: shrinks to a fixed top bar at ~36px height.
2. **Greeting**: "Hi [User], what do you want to build?" — dynamic username from `/api/auth/me` (falls back to OS username). Only visible in empty state.
3. **Prompt bar**: In empty state — centered in the page. In active state — `position: sticky; bottom: 0`, full width, no border-radius on sides (flat edge against the content area bottom).
4. **Plan type carousel**: Horizontal scrollable row of circular category icons, sourced from `/api/plans/templates`. Only visible in empty state.
5. **Example prompt suggestions**: 3 rotating chips from `/api/prompts/examples`. Only visible in empty state.
6. **Recent plans grid**: Up to 3 plan cards from `/api/plans/recent`. Only visible in empty state.
7. **Chat history**: `AgentResponse` bubbles rendered in the main scroll area. Only visible in active state. Scrolls independently from the rest of the layout.

### Definition of Done
- [ ] Home screen renders correctly in both **empty (welcome)** and **active (conversation)** states
- [ ] State transition fires on first prompt submission: welcome content collapses, chat history appears, prompt anchors to bottom
- [ ] Returning to home with no active session restores the empty/welcome state
- [ ] Prompt accepts text and dispatches to backend (POST `/api/command`)
- [ ] Plan type carousel loads categories dynamically from `/api/plans/templates`
- [ ] Example prompt chips load from `/api/prompts/examples` and rotate on 🔄 click
- [ ] Recent plans section shows real plan data with status badges
- [ ] All content is dynamic — zero hardcoded names, categories, or suggestions

### Tasks
- [ ] TASK-001 — Create `WorkspaceBadge.tsx`:
  - Shows: ⬡ Ostwin hexagon icon + project/workspace name + dropdown chevron
  - Workspace name from `/api/config` → `project_name` field (falls back to directory name)
  - Dropdown: placeholder for future workspace switching (renders but disabled for now)
  - **Empty state**: centered, full-size, `var(--font-display)` 14px, `var(--color-text-muted)`, subtle pill background
  - **Active state**: fixed top bar, ~36px height, left-aligned, `background: var(--color-surface)`, bottom border `var(--color-border)`. Transition: `slideUp + shrink` on state change (250ms ease).
- [ ] TASK-002 — Create `WelcomeGreeting.tsx`:
  - **Greeting text**: "Hi [username], what do you want to build?" — bold, centered
  - **Username**: fetched from `/api/auth/me` → `name` field; falls back to OS username via the existing auth endpoint. Loading state shows "Hi there" as fallback.
  - Font: `var(--font-display)`, 32px, `font-weight: 700`, `var(--color-text-main)`
  - No brand mark icon — the greeting itself is the focal point (clean, Replit-inspired)
  - Layout: centered horizontally, generous vertical spacing above and below
  - **Operational status line** below the greeting: a single live context line, e.g.:
    - "2 plans running · 5 agents active" — data from `/api/plans/recent` + `/api/rooms`
    - "Ready to orchestrate" — shown when system is idle
    - Font: 13px, `var(--color-text-faint)`, auto-refreshes every 30s via SWR
- [ ] TASK-003 — Create `CommandPrompt.tsx`:
  - Rounded input container, `border-radius: var(--radius-2xl)` (~20px)
  - Background: `var(--color-surface)`, border: `var(--color-border)`, shadow: `var(--shadow-card)`
  - **Left side**: `+` button — opens an action menu (create plan from template, import, attach file)
  - **Center**: `<textarea>` with placeholder "Describe your plan, Ostwin will orchestrate it..."
  - **Right side**: "Plan" mode chip (pill-shaped, `var(--color-primary)` background, white text) + submit arrow button
  - Submit behavior: On `/` (empty state), triggers `createConversation()` from `useConversation` hook — which POSTs to `/api/conversations` then navigates to `/c/{id}`. On `/c/[id]` (active state), calls `sendMessage()` which POSTs to `/api/command` with `conversation_id`.
  - Keyboard: Enter to submit, Shift+Enter for newline
  - Auto-focus on page load
  - Focus state: border transitions to `var(--color-primary)` with `var(--shadow-card-hover)`
  - **Empty state**: centered in the content area, max-width 680px, `border-radius: var(--radius-2xl)` on all sides
  - **Active state**: `position: sticky; bottom: 0; width: 100%` — border-radius only on top two corners (flat bottom against page edge), background `var(--color-surface)`, top border `var(--color-border)`. Active-state placeholder changes to "Follow-up or new request..."
- [ ] TASK-004 — Create `PlanTypeCarousel.tsx`:
  - Horizontal scrollable row of circular category icons with text labels below
  - **Data source**: GET `/api/plans/templates` → returns `[{ id, name, icon, description }]`
  - Each category: 48px circular icon container with subtle background, label below in 12px text
  - Left/right navigation arrows at edges (hidden when at scroll boundary)
  - Click behavior: pre-fills the CommandPrompt with the template's starter prompt
  - Active state: selected category gets `var(--color-primary)` ring + slightly elevated shadow
  - **Fallback** (if API returns empty or errors): show hardcoded defaults — "Feature", "Bugfix", "Service", "Refactor", "Custom"
  - Smooth horizontal scroll with CSS `scroll-snap-type: x mandatory`
- [ ] TASK-005 — Create `ExamplePrompts.tsx`:
  - Header: "Try an example prompt" text + 🔄 refresh icon button
  - Shows 3 suggestion chips in a horizontal row
  - **Data source**: GET `/api/prompts/examples` → returns `string[]` of example prompts
  - Each chip: pill-shaped, `var(--color-surface-hover)` background, `var(--color-text-main)` text, subtle border
  - Click: fills the CommandPrompt `<textarea>` with the selected suggestion text
  - 🔄 button: randomly selects a new set of 3 from the full list (fade-out/fade-in animation)
  - **Fallback** (if API unavailable): show defaults — "Deploy a Telegram bot", "Refactor auth module", "Add a new MCP server"
- [ ] TASK-006 — Create `RecentPlans.tsx`:
  - Section header: "Your recent Plans" (left) + "View All →" link (right, navigates to `/plans`)
  - Shows up to 3 plan cards in a horizontal row (responsive: stack vertically on mobile)
  - **Data source**: GET `/api/plans/recent?limit=3`
  - Empty state: "No plans yet. Describe what you want to build above." with a subtle illustration
- [ ] TASK-007 — Create `RecentPlanCard.tsx`:
  - Card layout:
    - Top area: large ⬡ hexagon icon (using plan's accent color or `var(--color-primary)`) on subtle gradient background
    - Small status icon badge in top-left corner of the card
    - Bottom area: plan title (truncated, 1 line), time-ago text ("4 minutes ago"), status label
  - Status visual:
    - `running` → green dot + "Running" label
    - `draft` → gray dot + "Draft" label
    - `completed` → checkmark + "Done" label
    - `failed` → red dot + "Failed" label
  - Click: navigates to `/plans/{plan-id}`
  - Hover: `translateY(-2px)` + `var(--shadow-card-hover)` elevation
  - Right-click / three-dot menu: context menu (Open, Duplicate, Archive, Delete)
- [ ] TASK-008 — Backend: Create `/api/command` endpoint in `dashboard/routes/command.py`:
  - Initial version: `POST { message: string, mode?: "plan"|"chat" }`
  - Intent parsing:
    - mode="plan" → calls `plan_agent.py` to auto-generate plan from description
    - "run plan X" → calls plan executor
    - "connect telegram" → returns instructions + link to `/channels`
    - "what's the status" → queries rooms/plans status
    - default → passes to agent for general response
  - Response: `{ type: "plan_created"|"status"|"response", payload }`
  - **Note**: EPIC-006 TASK-003 extends this endpoint to accept `conversation_id` for message persistence. Build the base version here; EPIC-006 adds the conversation layer on top.
- [ ] TASK-009 — Backend: Create `/api/auth/me` endpoint in `dashboard/routes/auth.py`:
  - Returns `{ name, email?, tier: "free"|"pro", avatar_url? }`
  - Reads from `~/.ostwin/user.json` if exists
  - Falls back to OS username (`os.getlogin()` / `getpass.getuser()`)
- [ ] TASK-010 — Backend: Create `/api/prompts/examples` endpoint in `dashboard/routes/prompts.py`:
  - Returns `string[]` of example prompt suggestions
  - Reads from `.agents/config.json` → `prompt_examples` field if exists
  - Falls back to built-in defaults: ["Deploy a Telegram bot", "Refactor the auth module", "Set up CI/CD pipeline", "Add a new MCP server", "Create a REST API", "Build a dashboard widget", "Write integration tests", "Migrate database schema"]
  - Shuffles on each request for variety
- [ ] TASK-011 — Backend: Create `/api/plans/templates` endpoint in `dashboard/routes/plans.py`:
  - Returns `[{ id, name, icon, description, starter_prompt }]`
  - Scans `.agents/plans/` for `*.template.md` files
  - Falls back to built-in defaults: Feature, Bugfix, Service, Refactor, Research, Custom
  - Each template has an icon identifier (Material Symbols name) and a starter prompt string
- [ ] TASK-012 — Create `useConversation.ts` hook (replaces the ephemeral `useHomeState`):
  - **Server-backed**: conversations are persisted via API, not sessionStorage.
  - Types:
    ```ts
    type Message = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
    type Conversation = { id: string; title: string; messages: Message[]; created_at: string; last_activity_at: string }
    ```
  - `createConversation()` — POST `/api/conversations` → returns new `Conversation`, then navigates to `/c/{id}`
  - `loadConversation(id)` — GET `/api/conversations/{id}` → hydrates `messages` state
  - `sendMessage(content)` — appends optimistic user message, POSTs to `/api/command` with `conversation_id`, streams response tokens via WebSocket, appends final assistant message
  - `resetToHome()` — navigates to `/` (empty welcome state, no active conversation)
  - Auto-generates conversation title from first user message (first 50 chars, server-side)
- [ ] TASK-013 — Refactor `page.tsx` + add `/c/[id]/page.tsx` conversation route:
  - **`/` (home)**: renders the empty/welcome state. On first prompt submission, calls `createConversation()` which creates a session server-side and navigates to `/c/{id}`.
  - **`/c/[id]` (conversation)**: renders the active/conversation state. On mount, calls `loadConversation(id)` to hydrate the chat history from the API. This is the **permalink** — shareable, bookmarkable, survives page refresh.
  - Both routes share the same `CommandPrompt` and `WorkspaceBadge` components.
  - `WorkspaceBadge` on `/c/[id]` shows a "← New conversation" button (calls `resetToHome()`).
  - Staggered `fade-in-up` animations for the welcome state: badge (0ms), greeting (100ms), prompt (200ms), carousel (300ms), suggestions (400ms), recent plans (500ms).
  - Max-width: 720px centered for both routes.
- [ ] TASK-014 — Add CSS animations in `globals.css`:
  - `@keyframes fade-in-up` — translateY(12px→0) + opacity(0→1), 400ms ease-out
  - `@keyframes prompt-glow` — subtle border glow pulse on prompt focus
  - `@keyframes chip-swap` — fade-out/fade-in for example prompt refresh
  - CSS classes: `.animate-fade-in-up-0` through `.animate-fade-in-up-5` with staggered `animation-delay`
- [ ] TASK-015 — Write frontend tests for all new Home components
- [ ] TASK-016 — Write backend tests for `/api/command`, `/api/auth/me`, `/api/prompts/examples`, `/api/plans/templates`

### Acceptance Criteria
- Home page (`/`) renders the welcome state; submitting the first prompt creates a conversation and navigates to `/c/{id}`
- `/c/{id}` is a **permalink** — chat history fully restored on page refresh or from a different browser
- Conversations appear in the sidebar history zone alongside plans, merged by last activity time
- Clicking a conversation in the sidebar navigates to its permalink
- "New conversation" button in the active state navigates back to `/` and resets to welcome layout
- All components use existing Ostwin CSS variables — no hardcoded colors
- All animations run smoothly at 60fps
- Dark mode: all components adapt correctly when user switches to dark in Settings > Appearance

depends_on: [EPIC-001, EPIC-002]

---

## EPIC-004 — Enhance Existing Settings, MCP, and Channels Pages

Roles: frontend-engineer, backend-engineer, qa
Objective: Enhance the existing Settings, MCP, and Channels pages with health indicators, better connection status visualization, and unified health monitoring — without creating new sidebar tabs or routes.
Lifecycle:
```text
pending → backend-engineer → frontend-engineer → qa ─┬─► passed → signoff
               ▲                    ▲                 │
               │                    └─ frontend-engineer ◄──┤ (on ui bug)
               └───────────── backend-engineer ◄────────────┘ (on api bug)
```

Tasks: The Settings page already has API Configuration, Appearance, and API Keys sections. The MCP page already manages MCP servers. The Channels page already handles Telegram/Discord/Slack setup. This epic enhances each of these with better health monitoring and visual indicators.

### Definition of Done
- [ ] Settings page: API keys section shows live health check status with animated dots
- [ ] Settings page: New "Connected Services" summary section showing quick health overview of all subsystems
- [ ] MCP page: Each server row shows live health indicator (green/amber/red dot with pulse)
- [ ] Channels page: Each platform card shows live connection health + latency
- [ ] Backend: Unified health check endpoint for consolidated status

### Tasks
- [ ] TASK-001 — Backend: Create `/api/health/summary` endpoint:
  - Aggregates health status from all subsystems:
    - External platforms (from `/api/channels`): Telegram, Discord, Slack
    - MCP servers (from `/api/mcp/servers`): all builtin + extensions
    - API keys (from `/api/providers/api-keys`): Gemini, Claude, GPT
  - Returns: `{ platforms: [...], mcp_servers: [...], api_keys: {...}, overall: "healthy"|"degraded"|"error" }`
  - Used by the Home screen connect toolbar and the Settings summary
- [ ] TASK-002 — Backend: Create `/api/mcp/servers/{name}/health` endpoint:
  - For stdio servers: check if PID is alive
  - For HTTP servers: HTTP HEAD to server URL
  - Returns: `{ status, latency_ms, last_checked }`
- [ ] TASK-003 — Frontend: Add "Connected Services" summary to Settings page:
  - New section at the top of Settings (above API Configuration):
  - Grid showing: "Platforms (2/3 connected)", "MCP Servers (4/6 running)", "API Keys (2/3 configured)"
  - Each card links to its management page (Channels, MCP, or scrolls to API Keys section)
  - Uses data from `/api/health/summary`
- [ ] TASK-004 — Frontend: Enhance MCP page server rows with health indicators:
  - Add animated `ConnectionHealthDot` to each server row
  - Show latency (e.g., "12ms") next to healthy servers
  - Auto-refresh health every 30 seconds via SWR
- [ ] TASK-005 — Frontend: Enhance Channels page cards with health details:
  - Add latency display to connected platforms
  - Add "Last seen" timestamp
  - Add health check button with loading animation
- [ ] TASK-006 — Frontend: Create `ConnectionHealthDot.tsx` utility component:
  - Animated status dot used across Settings, MCP, and Channels pages:
  - Green + gentle pulse: connected/healthy
  - Amber + slow pulse: connecting/checking
  - Red + static: error
  - Gray + static: disconnected/not configured
- [ ] TASK-007 — Write tests for health endpoint, health dots, and settings summary

### Acceptance Criteria
- Settings page has a "Connected Services" summary section at the top
- MCP page server rows show live health dots with latency
- Channels page cards show health + latency for connected platforms
- Health auto-refreshes every 30 seconds
- `ConnectionHealthDot` component is reused consistently across all 3 pages
- No new sidebar tabs are created

depends_on: [EPIC-001]

---

## EPIC-005 — Project (Plan) Management Lifecycle

Roles: frontend-engineer, backend-engineer, qa
Objective: Build a comprehensive plan management system with create, view, edit, run, duplicate, archive, and real-time progress tracking — tightly integrated with the sidebar project history.
Lifecycle:
```text
pending → backend-engineer → frontend-engineer → qa ─┬─► passed → signoff
               ▲                    ▲                 │
               │                    └─ frontend-engineer ◄──┤ (on ui bug)
               └───────────── backend-engineer ◄────────────┘ (on api bug)
```

### Definition of Done
- [ ] Plans have full CRUD via API and UI
- [ ] Plan detail page shows epic-level breakdown with progress
- [ ] Running a plan from the UI triggers `ostwin run` with real-time streaming
- [ ] Sidebar project history updates in real-time when plans change
- [ ] Plan creation supports template, freeform, and natural-language modes

### Tasks
- [ ] TASK-001 — Backend: Extend `routes/plans.py`:
  - `POST /api/plans` — Create from template, freeform markdown, or auto-generate via plan_agent
  - `PUT /api/plans/{id}` — Update plan content/metadata
  - `POST /api/plans/{id}/run` — Execute plan via `ostwin run`; track PID
  - `POST /api/plans/{id}/stop` — Kill all war-rooms for plan
  - `POST /api/plans/{id}/duplicate` — Clone with new plan ID
  - `POST /api/plans/{id}/archive` — Move to `.agents/plans/.archive/`
  - `GET /api/plans/{id}/status` — Real-time: epic progress, active rooms, agent states
  - `GET /api/plans/recent` — Returns plans sorted by last-modified for sidebar history
- [ ] TASK-002 — Backend: Create `PlanExecutor` in `dashboard/plan_executor.py`:
  - Wraps `ostwin run <plan.md>` as async subprocess
  - Tracks PID in `<plan-id>.run.pid`
  - Streams stdout/stderr via WebSocket events
  - Parses war-room state changes to update epic progress
- [ ] TASK-003 — Backend: Create `PlanTemplateEngine` in `dashboard/plan_templates.py`:
  - Lists templates from `.agents/plans/PLAN.template.md`
  - `generate(description, roles, epics)` → produces plan markdown
  - Validates plan structure (EPICs, lifecycle, tasks)
- [ ] TASK-004 — Frontend: Create `PlanCreationWizard.tsx`:
  - Multi-step wizard modal:
    - Step 1: Choose mode (Template / Freeform / "Describe what you need")
    - Step 2: Configure — name, description, roles, epics
    - Step 3: Preview rendered plan as formatted markdown
    - Step 4: Confirm & create → redirects to plan detail page
  - "Describe what you need" mode: text area → POST to `/api/command` → auto-generates plan
- [ ] TASK-005 — Frontend: Create `PlanDetailPage.tsx` at `/plans/[id]/page.tsx`:
  - Header: Plan title, status badge, action buttons (Run ▶, Stop ⏹, Edit ✏, Duplicate 📋, Archive 📁)
  - Epic list: Accordion of EpicCards with progress bars
  - Activity panel: Right-side live feed from war-room channels
  - Dependencies: Visual graph of epic dependencies
- [ ] TASK-006 — Frontend: Create `EpicCard.tsx`:
  - Expandable card: epic name, role badges (color-coded), progress bar, lifecycle diagram
  - Task list with live status updates via WebSocket
  - Status: pending (gray), running (blue+pulse), passed (green), failed (red)
- [ ] TASK-007 — Frontend: Create `PlanActionsBar.tsx`:
  - Floating action bar: ▶ Run, ⏸ Pause, ⏹ Stop, 📋 Duplicate, 📁 Archive, ✏ Edit
  - Context-aware: shows "Run" for draft, "Stop" for running
- [ ] TASK-008 — Frontend: Update `PlanGrid.tsx` + `PlanCard.tsx`:
  - Card: plan title, epic count, progress ring, status badge, last activity
  - Hover: glass lift + glow border
  - Toggle between grid view and list view
- [ ] TASK-009 — Frontend: Wire sidebar `SidebarHistory` to plan events:
  - SWR polling `/api/plans/recent` every 10s or WebSocket `plan_updated` events
  - Sidebar history auto-reorders when plans change
  - Running plan shows animated pulse dot in sidebar
- [ ] TASK-010 — Write tests for plan CRUD, execution, and sidebar integration

### Acceptance Criteria
- Plans can be created via template, freeform, or natural language
- Plan detail page shows real-time epic progress
- Running a plan from UI starts war-rooms and streams progress
- Sidebar project history reflects plan changes in real-time
- Duplicate and archive operations work correctly
- Plan list supports grid/list toggle with sort and filter

depends_on: [EPIC-002, EPIC-003]

---

## EPIC-006 — Real-Time Communication & Agent Interaction

Roles: backend-engineer, frontend-engineer, qa
Objective: Build a WebSocket-powered layer that enables the Home prompt to interact with Ostwin agents, streams responses in real-time, and surfaces system-wide activity.
Lifecycle:
```text
pending → backend-engineer → frontend-engineer → qa ─┬─► passed → signoff
               ▲                    ▲                 │
               │                    └─ frontend-engineer ◄──┤ (on ui bug)
               └───────────── backend-engineer ◄────────────┘ (on api bug)
```

### Definition of Done
- [ ] Home prompt commands dispatch to agents and stream responses into the active conversation
- [ ] Conversations persist server-side — survive page refresh, accessible via permalink `/c/{id}`
- [ ] Sidebar history shows conversations alongside plans, navigable by click
- [ ] War-room events broadcast and appear in UI activity feeds
- [ ] Chat-like response display with markdown support

### Tasks
- [ ] TASK-001 — Backend: Create `ConversationStore` in `dashboard/conversation_store.py`:
  - Storage: `.agents/conversations/{id}.json` (one file per conversation, persisted to disk)
  - Schema:
    ```json
    {
      "id": "conv-abc123",
      "title": "Deploy a Telegram bot",
      "created_at": "...",
      "last_activity_at": "...",
      "messages": [
        { "id": "msg-001", "role": "user", "content": "...", "created_at": "..." },
        { "id": "msg-002", "role": "assistant", "content": "...", "created_at": "..." }
      ]
    }
    ```
  - `create(first_message)` — generates ID, auto-generates title from first 50 chars of message
  - `get(id)` — reads conversation file
  - `append_message(id, role, content)` — appends a message and updates `last_activity_at`
  - `list(limit)` — reads all conversation files, returns sorted by `last_activity_at` desc
  - `delete(id)` — removes conversation file
  - `rename(id, title)` — updates title
- [ ] TASK-002 — Backend: Create `/api/conversations` routes in `dashboard/routes/conversations.py`:
  - `GET /api/conversations?limit=50` — list conversations (id, title, last_activity_at, message_count)
  - `GET /api/conversations/{id}` — full conversation with all messages
  - `POST /api/conversations` — create new conversation; body: `{ first_message: string }`; returns full conversation object
  - `DELETE /api/conversations/{id}` — delete conversation
  - `PATCH /api/conversations/{id}` — rename conversation; body: `{ title: string }`
- [ ] TASK-003 — Backend: Extend `/api/command` to accept `conversation_id`:
  - Updated payload: `POST { message, mode, conversation_id? }`
  - If `conversation_id` provided: appends user message to existing conversation, streams response, appends assistant message on completion
  - If no `conversation_id`: creates new conversation automatically, returns `conversation_id` in response header so frontend can redirect
- [ ] TASK-004 — Backend: Extend WebSocket protocol (`ws_router.py`):
  - New events: `command_response`, `agent_stream`, `epic_progress`, `connection_health`
  - `command_request` handler: receives `{ prompt, conversation_id }` → dispatches to `CommandDispatcher`, streams tokens back via `agent_stream` event
  - Token-level streaming for agent responses
- [ ] TASK-005 — Backend: Create `CommandDispatcher` (`dashboard/command_dispatcher.py`):
  - Intent parser: "create plan for X" → `create_plan`, "status" → `get_status`, "connect telegram" → `connect_platform`
  - Routes to: plan_agent, plan_executor, mcp installer, status aggregator
  - Returns structured responses with suggested follow-ups
- [ ] TASK-006 — Frontend: Create `ChatHistory.tsx`:
  - Renders the scrollable list of `Message` objects from `useConversation`
  - Auto-scrolls to bottom on new messages
  - Groups consecutive assistant messages with a single avatar
  - Shows a typing indicator (`▌`) while streaming is in progress
  - "Jump to bottom" FAB appears when user scrolls up
- [ ] TASK-007 — Frontend: Create `AgentResponse.tsx`:
  - Chat-bubble style display for assistant messages
  - Markdown rendering (headers, code blocks, lists)
  - Streaming text with animated cursor `▌`
  - Inline action buttons: "View Plan", "Run Now", "Open Settings"
- [ ] TASK-008 — Frontend: Create `ActivityFeed.tsx`:
  - Real-time event feed: plan started, epic passed, agent error, connection changed
  - Each event: timestamp + icon + message + link to relevant page
  - Filters: All, Plans, Agents, System
- [ ] TASK-009 — Frontend: Wire `SidebarHistory` to conversation events:
  - SWR polling `GET /api/conversations?limit=50` every 10s
  - When a new conversation is created, it immediately appears at the top of the sidebar history
  - Active conversation (`/c/{id}`) highlighted in sidebar with left accent bar
- [ ] TASK-010 — Write tests for ConversationStore, API routes, WebSocket handling, and ChatHistory rendering
- [ ] TASK-011 — Frontend: Extend `SearchModal` with conversation search:
  - The existing `SearchModal` (Cmd+K / Ctrl+K) currently searches plans, skills, and MCP servers
  - Add a new **"Conversations"** result group that queries `GET /api/conversations/search?q={query}`
  - Backend: Add `GET /api/conversations/search?q=` endpoint to `dashboard/routes/conversations.py`:
    - Full-text search across conversation `title` and message `content` fields
    - Returns `[{ id, title, matched_message_preview, last_activity_at }]`
    - Uses simple case-insensitive substring match on content (BM25 optional)
  - Frontend result rendering:
    - Each result shows: chat bubble icon + conversation title + matched text snippet (up to 100 chars, keywords bolded)
    - Pressing Enter or clicking navigates to `/c/{id}`
  - Result ordering: conversations ranked above plans when query matches title, below when only body match
  - Empty state: "No conversations match \"query\"" — shown only when conversations tab is active or results are zero across all groups

### Acceptance Criteria
- Conversations persist to disk in `.agents/conversations/` — survive server restarts and page refreshes
- `/c/{id}` is a true permalink — full chat history restored from API on load
- Sidebar history shows conversations alongside plans, merged by last activity
- Clicking a conversation in the sidebar navigates to `/c/{id}` and restores the chat
- Streaming agent responses appear token-by-token in the chat
- Deleting a conversation removes it from sidebar and redirects to home

depends_on: [EPIC-003, EPIC-004, EPIC-005]

---

## EPIC-007 — Theme System & Visual Polish

Roles: frontend-engineer, ui-designer, qa
Objective: Apply glassmorphism effects and micro-animations to all new components using the **existing Ostwin theme** (`globals.css` CSS variables). No new theme tokens are created. Dark mode is already handled by `[data-theme="dark"]` in `globals.css`.
Working_dir: dashboard/fe
Lifecycle:
```text
pending → frontend-engineer → ui-designer → qa ─┬─► passed → signoff
               ▲                 ▲               │
               │                 └── ui-designer ◄┤ (on design issue)
               └─── frontend-engineer ◄──────────┘ (on implementation bug)
```

### Definition of Done
- [ ] All new components use the existing Ostwin CSS variables — zero hardcoded colors
- [ ] Glassmorphism effects (GlassCard, CommandPrompt) use `var(--color-surface)` + `var(--shadow-card)` so they work in both light and dark automatically
- [ ] All interactions have micro-animations
- [ ] WCAG 2.1 AA compliance verified in both light (default) and dark modes

### Tasks
- [ ] TASK-001 — Verify all new components strictly use existing Ostwin CSS variables:
  - Lint/grep `dashboard/fe/src` for any hardcoded hex values or raw Tailwind colors in new files
  - Raise a PR comment for anything not using a `var(--color-*)`, `var(--shadow-*)`, or `var(--radius-*)` token
  - The only exception is decorative gradients in plan card icons (not a surface color)
- [ ] TASK-002 — Create `GlassCard.tsx` — reusable glassmorphism container using existing tokens:
  - `background: var(--color-surface)` with `backdrop-filter: blur(12px)`
  - `box-shadow: var(--shadow-card)` (hover: `var(--shadow-card-hover)`)
  - `border: 1px solid var(--color-border)`
  - Dark mode: automatic, because `[data-theme="dark"]` already overrides `--color-surface` and `--color-border`
- [ ] TASK-003 — Create `BrandIcon.tsx` — reusable ⬡ hexagon brand mark component:
  - Renders the existing Ostwin hexagon logo SVG at configurable sizes (used in WorkspaceBadge, RecentPlanCard, sidebar)
  - Uses `var(--color-primary)` as base fill color, accepts optional `accentColor` prop for per-plan variants
  - Optional slow CSS `rotate` animation on a gradient overlay (enabled via `animated` prop, used in plan cards)
- [ ] TASK-004 — Micro-animations:
  - Sidebar tab hover: subtle translateX(2px) + opacity change
  - Card hover: translateY(-2px) + shadow expansion + border glow
  - Button click: scale-95 spring
  - Page transitions: staggered fade-in-up
  - Status dots: gentle pulse for active states
  - Prompt focus: border glow transition (blue in light, softer in dark)
- [ ] TASK-005 — Theme persistence: already handled by `useUIStore` + `localStorage` in the existing codebase — no new work needed; just ensure new components respond to the `data-theme` attribute on `<html>`
- [ ] TASK-006 — Typography: use `var(--font-display)` for all UI text, `var(--font-mono)` for code/IDs. Font sizes: greeting 38px, prompt 16px, sidebar tabs 13px, sidebar history 12px, badges 10px
- [ ] TASK-007 — Responsive breakpoints: mobile (<768px), tablet (768-1024px), desktop (>1024px)
- [ ] TASK-008 — Accessibility audit: contrast ≥4.5:1 using existing token values, focus outlines, aria labels, keyboard nav
- [ ] TASK-009 — Visual regression tests: snapshot both light (default) and dark states

### Acceptance Criteria
- Every new component uses only `var(--color-*)` / `var(--shadow-*)` / `var(--radius-*)` tokens — no hardcoded values
- GlassCard and CommandPrompt look correct in both light and dark without any extra CSS
- All interactions are smooth and polished
- WCAG 2.1 AA compliant in both themes

depends_on: [EPIC-002, EPIC-003, EPIC-004, EPIC-005]

---

## EPIC-008 — Integration Testing & Documentation

Roles: test-engineer, technical-writer
Objective: End-to-end testing, user documentation, and contributor guide updates.
Lifecycle:
```text
pending → test-engineer → technical-writer ─┬─► passed → signoff
               ▲                ▲            │
               │                └────────────┤ (on doc issues)
               └───── test-engineer ◄────────┘ (on test failures)
```

### Definition of Done
- [ ] All Cypress E2E tests pass
- [ ] User guide covers all new features
- [ ] Contributor docs updated

### Tasks
- [ ] TASK-001 — Cypress E2E tests:
  - Home screen: greeting (dynamic username), prompt bar submission, category carousel, example chip rotation, recent plans grid
  - Sidebar: 5 tabs navigation, history zone shows conversations + plans, collapse behavior
  - Conversation flow: submit prompt → navigate to `/c/{id}` → refresh page → chat history fully restored
  - Conversation management: rename conversation, delete conversation (sidebar item removed, redirect to home)
  - **Search (Cmd+K)**: type a query → conversations appear in results → clicking navigates to `/c/{id}`
  - Settings: connected services summary, API key status
  - MCP page: health indicators on server rows
  - Channels page: health indicators on platform cards
  - Plan lifecycle: create, view, run, duplicate, archive
  - Command prompt on `/c/[id]`: follow-up message appended to existing conversation
- [ ] TASK-002 — API integration tests:
  - `/api/command` (base + with `conversation_id`), `/api/auth/me`, `/api/health/summary`
  - `/api/conversations` CRUD (create, get, list, delete, rename)
  - `/api/conversations/search?q=` — results contain matching title and message snippet
  - `/api/plans` CRUD (create, update, run, stop, duplicate, archive)
  - `/api/mcp/servers/{name}/health`
  - WebSocket event handling (`agent_stream`, `command_response`, `epic_progress`)
- [ ] TASK-003 — User guide (`docs/user-guide/dashboard-v2.md`):
  - Home screen overview and command prompt usage
  - Sidebar navigation and project history
  - Settings: API keys, appearance, connected services overview
  - Plan management workflow
  - Keyboard shortcuts
- [ ] TASK-004 — Contributor docs (`CONTRIBUTE.md` update):
  - Updated component architecture
  - New API endpoint reference
  - Design token reference
- [ ] TASK-005 — Architecture Decision Record (`docs/adr/007-dashboard-v2.md`)

### Acceptance Criteria
- ≥ 90% test coverage for new endpoints
- All Cypress E2E tests pass
- User guide complete and reviewed
- Contributor docs include architecture diagrams

depends_on: [EPIC-003, EPIC-004, EPIC-005, EPIC-006, EPIC-007]

---

## EPIC-009 — Long Memory (Persistent Knowledge Layer)

Roles: backend-engineer, qa
Objective: Build a persistent, cross-session knowledge layer that survives beyond individual plan runs. The existing shared memory (`ledger.jsonl` + `memory-core.py`) is session-scoped with aggressive time decay (30min–24hr half-lives) — past learnings are effectively forgotten. This EPIC creates a durable knowledge store that agents can query at the start of every new task, so Ostwin *learns* from every project it works on. **Backend-only: no UI changes.**
Working_dir: .agents
Lifecycle:
```text
pending → backend-engineer → qa ─┬─► passed → signoff
               ▲                  │
               └─ backend-engineer ◄┘ (on fail → fixing)
```

### Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     Existing (Session Memory)                       │
│                                                                     │
│  War Room A ──publish──► ledger.jsonl ◄──query── War Room B        │
│                          (BM25 search, time decay, ephemeral)       │
│                                                                     │
├─────────────────────── NEW: Long Memory ────────────────────────────┤
│                                                                     │
│  Plan Run ends ──► Distiller ──► knowledge/                         │
│                    (LLM-powered   ├── items/                        │
│                     summarise &   │   ├── ki-001.json               │
│                     extract)      │   ├── ki-002.json               │
│                                   │   └── ...                       │
│                                   ├── embeddings.db (SQLite+vec)    │
│                                   └── index.json                    │
│                                                                     │
│  New task starts ──► Auto-Retrieval ──► inject relevant KIs into    │
│                      (semantic search    agent context)              │
│                       + BM25 hybrid)                                │
│                                                                     │
│  CLI: `memory distill`, `memory knowledge search/list/add`          │
└─────────────────────────────────────────────────────────────────────┘
```

### What Becomes a Knowledge Item (KI)?

| Source | Distilled Into | Example |
|--------|---------------|---------|
| `decision` entries from session memory | **Architectural Decision** KI | "JWT stateless auth over sessions — multiple services need independent verification" |
| `convention` entries | **Convention** KI | "All API errors return `{detail, code, errors[]}` format" |
| `warning` entries | **Gotcha** KI | "cats.status has a CHECK constraint — adding new statuses needs a migration" |
| `code` entries for key files | **Pattern** KI | "FastAPI router pattern: router = APIRouter(prefix=..., tags=[...])" |
| Failed plan runs (post-mortem) | **Lesson Learned** KI | "Telegram 409 Conflict — only one poller can run at a time per bot token" |
| Repeated agent corrections | **Best Practice** KI | "Always use `var(--color-*)` tokens in dashboard components, never hardcoded hex" |

### Definition of Done
- [ ] Knowledge Items (KIs) persist in `.agents/memory/knowledge/` as JSON files — survive indefinitely across plan runs
- [ ] Auto-distillation runs when a plan completes, extracting durable learnings from session memory
- [ ] Semantic search over KIs via embeddings (SQLite + sqlite-vec or existing pgvector)
- [ ] Agents automatically retrieve relevant KIs at task start (injected into agent context)
- [ ] `memory` CLI extended with `memory distill` and `memory knowledge` commands
- [ ] No dashboard UI changes — this EPIC is backend-only

### Tasks

#### Backend: Knowledge Item Storage
- [ ] TASK-001 — Create `KnowledgeStore` in `.agents/mcp/knowledge-store.py`:
  - KI schema:
    ```json
    {
      "id": "ki-001",
      "created_at": "2026-04-01T12:00:00Z",
      "updated_at": "2026-04-01T12:00:00Z",
      "kind": "decision|convention|gotcha|pattern|lesson|best-practice",
      "title": "Short descriptive title",
      "content": "Full knowledge content — the actual learning",
      "tags": ["auth", "jwt", "architecture"],
      "source_refs": ["mem-dec-1774690708220102000-82008"],
      "source_plan": "ostwin-dashboard-v2",
      "confidence": 0.85,
      "access_count": 12,
      "last_accessed": "2026-04-01T14:00:00Z",
      "status": "active|archived|superseded",
      "superseded_by": null
    }
    ```
  - Storage: one JSON file per KI in `.agents/memory/knowledge/items/`
  - Index: `.agents/memory/knowledge/index.json` — lightweight lookup array (id, title, kind, tags, status)
  - CRUD: `create_ki()`, `get_ki()`, `update_ki()`, `archive_ki()`, `list_kis()`
  - Deduplication: before creating, check if a similar KI exists (by title similarity or tag overlap)
- [ ] TASK-002 — Create `KnowledgeEmbedder` in `.agents/mcp/knowledge-embedder.py`:
  - Embeds KI content using Gemini embedding API (same model as `code_index.py`: `gemini-embedding-2-preview`)
  - Storage option A (**preferred, lightweight**): SQLite + `sqlite-vec` extension (no Postgres dependency)
  - Storage option B (if pgvector already available): reuse existing CocoIndex Postgres
  - `embed_ki(ki_id)` — embed a single KI and upsert into vector store
  - `search_similar(query, top_k=5)` — hybrid search: BM25 on index.json + cosine similarity on embeddings, merged with RRF (Reciprocal Rank Fusion)
  - `rebuild_embeddings()` — re-embed all active KIs (for model upgrades)
- [ ] TASK-003 — Create `MemoryDistiller` in `.agents/mcp/memory-distiller.py`:
  - Triggered when a plan run completes (via lifecycle hook or manual `memory distill`)
  - Reads the session `ledger.jsonl` for the completed plan
  - Groups entries by kind and deduplicates
  - Uses LLM (Gemini) to:
    1. Identify entries worth preserving long-term (not all session memory is valuable)
    2. Summarise/consolidate related entries into a single KI
    3. Merge with existing KIs if overlapping (update rather than duplicate)
  - Prompt template:
    ```
    You are a knowledge curator for an AI agent system. Review these session memory
    entries from a completed plan run and extract durable knowledge items.
    
    Only extract items that would be valuable for future plan runs:
    - Architectural decisions and their rationale
    - Coding conventions and patterns specific to this project
    - Gotchas, warnings, and things that broke
    - Lessons learned from failures
    
    Do NOT extract: temporary file lists, one-off debug artifacts, or context-specific
    implementation details that won't apply to future work.
    ```
  - Outputs: list of KIs to create/update, passed to `KnowledgeStore`
  - Dry-run mode: `memory distill --dry-run` — shows what would be extracted without writing
- [ ] TASK-004 — Create `AutoRetriever` in `.agents/mcp/auto-retriever.py`:
  - Called at the start of each agent task in a war room
  - Input: task brief text + room keywords
  - Process:
    1. Semantic search over KIs using `KnowledgeEmbedder.search_similar()`
    2. BM25 fallback search over KI index for tag/keyword matches
    3. Merge results using RRF, deduplicate, limit to top 5-8 KIs
  - Output: formatted context block injected into agent prompt:
    ```
    ## Long-Term Knowledge (auto-retrieved)
    
    ### Decisions
    - **JWT stateless auth**: Multiple services verify auth independently. Token in localStorage, 24h expiry.
    
    ### Conventions
    - **Error format**: All APIs return {detail, code, errors[]}. Status codes: 400/401/403/404/409.
    
    ### Gotchas
    - **cats.status CHECK constraint**: Adding new statuses requires an Alembic migration.
    ```
  - Integration point: modify `.agents/roles/_base/Invoke-Agent.ps1` or the agent briefing pipeline to call `auto-retriever.py` before spawning the agent

#### Backend: API Endpoints
- [ ] TASK-005 — Create `/api/memory/knowledge` endpoints in `dashboard/routes/memory.py`:
  - `GET /api/memory/knowledge` — list all KIs (filterable by kind, tags, status)
  - `GET /api/memory/knowledge/{id}` — get single KI with full content
  - `POST /api/memory/knowledge` — create new KI manually
  - `PUT /api/memory/knowledge/{id}` — update KI content/tags
  - `DELETE /api/memory/knowledge/{id}` — archive KI (soft delete, sets status: "archived")
  - `GET /api/memory/knowledge/search?q=...` — hybrid search (BM25 + vector)
  - `POST /api/memory/distill` — trigger distillation from latest session memory
  - `GET /api/memory/stats` — count by kind, total KIs, last distillation time, most accessed
- [ ] TASK-006 — Extend `memory` CLI (`memory-cli.py`) with long memory commands:
  - `memory distill [--plan <plan-name>] [--dry-run]` — run distillation
  - `memory knowledge list [--kind decision] [--tags auth]` — list KIs
  - `memory knowledge search "<query>"` — semantic search
  - `memory knowledge add "<title>" --kind decision --tags auth,jwt --content "..."` — manually add a KI
  - `memory knowledge archive <ki-id>` — archive a KI
- [ ] TASK-007 — Extend MCP memory server (`memory-server.py`) with long memory tools:
  - `knowledge_search` tool — agents can search long-term memory during their work
  - `knowledge_publish` tool — agents can contribute new KIs during a plan run
  - `knowledge_context` tool — returns formatted context block for agent briefing

#### Backend: Lifecycle Integration
- [ ] TASK-008 — Add distillation hook to plan lifecycle:
  - When a plan transitions to `completed` or `failed-final` status:
    1. Run `MemoryDistiller` on the session ledger for that plan
    2. Create/update KIs in knowledge store
    3. Embed new KIs
    4. Log distillation results to `.agents/memory/knowledge/distill-log.jsonl`
  - Integration point: `.agents/lifecycle/` scripts or `plan_executor.py`
  - Configurable in `.agents/config.json`: `"auto_distill": true|false` (default: true)
- [ ] TASK-009 — Add auto-retrieval hook to agent spawning:
  - Before an agent starts work in a war room:
    1. Extract keywords from the task brief / EPIC description
    2. Call `AutoRetriever` to get relevant KIs
    3. Prepend the formatted context block to the agent's system prompt
  - Integration point: `.agents/roles/_base/Invoke-Agent.ps1` or the wrapper script that prepares the agent brief
  - Configurable: `"auto_retrieve": true|false` (default: true)

#### Tests
- [ ] TASK-010 — Write backend tests:
  - `KnowledgeStore` CRUD operations
  - `KnowledgeEmbedder` embedding and search
  - `MemoryDistiller` with mock LLM responses (dry-run mode)
  - `AutoRetriever` context generation — assert relevant KIs injected into agent prompt
  - `/api/memory/knowledge` endpoint integration tests
  - `/api/memory/distill` trigger test

### Acceptance Criteria
- Knowledge Items persist in `.agents/memory/knowledge/` as individual JSON files — not lost between plan runs
- Running `memory distill` after a plan completion extracts 3-10 meaningful KIs from session memory
- Semantic search returns relevant KIs when agents query by topic (e.g., "auth" returns JWT decision)
- Agents automatically receive relevant KIs in their context at task start (visible in agent logs)
- `memory knowledge search` CLI command returns ranked results
- Auto-distillation triggers on plan completion when `auto_distill: true` in config
- Existing session memory (`ledger.jsonl`, `memory-core.py`, shared-memory skill) is untouched — long memory is additive
- **No UI changes**: zero new dashboard pages, routes, or sidebar tabs

depends_on: [EPIC-002, EPIC-003, EPIC-006]
