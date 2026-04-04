# Dashboard V2 Wireframe & Design Specification

This document provides a comprehensive design specification for the Dashboard V2 update, heavily inspired by modern AI assistant UIs (Replit Agent, Claude, Cursor), mapping all design elements to the existing Ostwin design tokens.

---

## 1. Global Layout

The global layout consists of a persistent Left Sidebar for navigation and a main content area.

### 1.1 Sidebar Navigation Architecture
The sidebar uses a split-zone architecture:

**Fixed Top Zone (Navigation Tabs)**
- 5 Primary Navigation Tabs:
  - **Home** (`/`)
  - **Plans** (`/plans`)
  - **Skills** (`/skills`)
  - **Roles** (`/roles`)
  - **Settings** (`/settings`)

**Scrollable Bottom Zone (Project/Plan History)**
- Grouped by time period:
  - "Today"
  - "Last 7 days"
  - "Last 30 days"
  - "Older"
- **Project Entry Format**:
  - Plan title (truncated to fit width)
  - Status dot indicator (using `--color-success`, `--color-warning`, `--color-danger`)
  - Last activity timestamp (small, muted text)

**Collapsed Mode**
- Hides the text labels and project history.
- Displays only the icons for the 5 primary tabs to maximize screen space.

---

## 2. Page Wireframes

### 2.1 Home Page (`/`)
The Home Page is the central starting point for user action.

**Top Center Header**
- Workspace/project identity badge: A small pill-shaped element containing the user avatar, workspace name, and a dropdown caret.

**Main Content (Vertically Centered)**
- **Greeting**: Large, bold heading "Hi [User], what do you want to build?"
  - Uses `var(--font-display)`
  - Includes the brand ⬡ hexagon logo SVG using `--color-primary` as its fill.
- **Prompt Bar**: A wide, rounded input field.
  - Left side: `+` button for attachments or context.
  - Right side: "Plan" mode chip selector and a submit arrow.
- **Plan Type Carousel**: A horizontal, scrollable row of circular category icons with labels (e.g., Website, Mobile, Backend).
  - Includes left/right navigation arrows.
- **Example Prompts**: A text button "Try an example prompt 🔄" with rotating suggestion chips below to inspire the user.

**Bottom Section (Below the fold)**
- **Recent Projects**: "Your recent Plans" section header with a "View All →" link on the right.
- **Card Grid**: A CSS grid (e.g., 2 or 3 columns) displaying recent plans as cards.
  - Uses `--shadow-card` with hover effect `--shadow-card-hover`.

### 2.2 Plans Page (`/plans`)
Dedicated page for managing all existing plans and viewing history.
- **Header**: "All Plans" with a "Create New" button.
- **Content**: A comprehensive list or grid of all plans, sortable by status, date, and category.
- **Components**: Reuses the plan cards from the Home screen's "Recent Projects" section.

### 2.3 Skills Page (`/skills`)
Page for viewing and managing agent capabilities.
- **Header**: "Skills Library"
- **Content**: Card grid displaying enabled/available skills.
- **Components**: Each card features an icon, title, description, and an enable/disable toggle.

### 2.4 Roles Page (`/roles`)
Page for assigning and configuring specific agent roles.
- **Header**: "Agent Roles"
- **Content**: List of defined roles (e.g., Researcher, Engineer, UI Designer).
- **Components**: Configuration forms for each role's system prompts and default skills.

### 2.5 Settings Page (`/settings`)
Page for system-wide configuration, merging all connectable subsystems.
- **Header**: "System Settings"
- **Tabs/Sections**:
  - **API Keys**: (Gemini, Claude, GPT)
  - **External Platforms**: (Telegram, Discord, Slack) -> redirecting or merging from `/channels`
  - **MCP Servers & Vault**: (channel, warroom, memory, serena, etc.) -> redirecting or merging from `/mcp`
  - **Appearance**: Dark/Light mode toggle (uses existing `[data-theme="dark"]` override).

---

## 3. Subsystem Mapping References
All connectable subsystems map directly to existing routes to preserve logic:
- **External Platforms** (Telegram, Discord, Slack): Managed via `/channels` (linked from Settings).
- **MCP Servers** (channel, warroom, memory, serena, context7, ai-game-developer, stitch, github): Managed via `/mcp`.
- **MCP Catalog** (chrome-devtools, nanobanana): Managed via `/mcp`.
- **API Keys** (Gemini, Claude, GPT): Managed via `/settings`.
- **Vault Credentials**: Managed via `/mcp` inside the per-server configuration modal.

---

## 4. Design Tokens Specification

All new components **MUST** strictly use the existing CSS variables from `globals.css` with no new tokens introduced.

**Colors**
- Backgrounds: `var(--color-background)`, `var(--color-surface)`, `var(--color-surface-hover)`
- Text: `var(--color-text-main)`, `var(--color-text-muted)`, `var(--color-text-faint)`
- Brand/Accent: `var(--color-primary)`, `var(--color-primary-hover)`, `var(--color-primary-muted)`
- Borders: `var(--color-border)`, `var(--color-border-light)`
- Status Indicators: `var(--color-success)`, `var(--color-warning)`, `var(--color-danger)`

**Typography**
- Headings/UI: `var(--font-display)` (Plus Jakarta Sans)
- Code/Data: `var(--font-mono)` (IBM Plex Mono)

**Layout & Styling**
- Radii: `var(--radius-sm)`, `var(--radius-md)`, `var(--radius-lg)`, `var(--radius-xl)`, `var(--radius-2xl)`, `var(--radius-full)`
- Shadows: `var(--shadow-card)`, `var(--shadow-card-hover)`, `var(--shadow-modal)`

**Dark Mode**
- The entire layout relies on native CSS override swapping defined under `[data-theme="dark"]` in `globals.css`. Do not add inline color overrides for dark mode.