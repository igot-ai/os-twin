# OS Twin Dashboard v2 User Guide

Welcome to the **OS Twin Dashboard v2**! The new Dashboard provides a completely overhauled layout tailored for prompt-first planning and unified chat history.

## 1. Home Screen & Command Prompt Usage

The core of Dashboard v2 is the dynamic **Home Screen**. 
When you load the dashboard, you will be greeted dynamically.

- **Command Prompt**: A centralized search/prompt bar allows you to directly engage with OS Twin. Simply type "What do you want to build?" and press Enter. This will create a new conversation and seamlessly transition you to the chat interface.
- **Category Carousel**: Provides pre-made prompt collections (e.g., Software, Marketing, DevTools) that you can swipe through.
- **Example Chips**: Click "Try an example prompt" to cycle through randomized suggestions to kickstart your session.
- **Recent Plans**: Quickly jump back into your most recently created `Plans` via the dashboard grid.

## 2. Sidebar Navigation & Project History

The new collapsible sidebar keeps your workspace clean.

### Navigation Tabs
1. **Home**: Return to the main dashboard.
2. **Plans**: Access your complete plan repository (`/plans`). Here you can search, filter, and sort all your projects.
3. **Skills**: Manage OS Twin capabilities.
4. **Roles**: View configured roles.
5. **Settings**: System configurations.

### History Zone
Below the tabs, your past work is organized chronologically (e.g., "Today", "Last 7 days").
- Click any **Conversation** to restore its context.
- Hover over an item and click the `...` menu to **Rename** or **Delete** it.
- **Collapse/Expand**: Click the collapse button to minimize the sidebar into a slim icon view.

## 3. Keyboard Shortcuts

Boost your productivity with quick actions:
- **Search (Cmd+K / Ctrl+K)**: Instantly opens the global search modal. Type any keyword to search across all your past conversation titles and snippets.

## 4. Settings & Connected Services

The Settings tab (`/settings`) is your command center for integrations:
- **Connected Services**: At a glance, view live health indicators for your Platforms, MCP Servers, and API Keys.
- **API Keys**: Manage the core platform tokens.
- **Appearance**: Toggle between Light and Dark mode globally. 

*(Health indicators utilize a real-time pulsing dot: Green for Healthy, Amber for Degraded, Red for Offline).*

## 5. Plan Management Workflow

Managing complex projects is easier than ever:
- **Create**: Use the Plan Creation Wizard (`/plans/new`) to scaffold a plan "From Template" or "Freeform".
- **View & Edit**: Open any plan to view its markdown content and assigned roles/epics.
- **Run / Stop**: Trigger execution via the `PlanActionsBar` pinned to the bottom of the screen.
- **Duplicate**: Clone an existing plan layout to start a similar project.
- **Archive**: Move old plans out of your active workspace without fully deleting them.

## 6. MCP & Channels Monitoring

- **MCP Page** (`/mcp`): Lists your Model Context Protocol servers. Each row displays real-time connection status and latency.
- **Channels Page** (`/channels`): Monitor external platforms (e.g., Telegram, Slack). Cards indicate live connection health.
