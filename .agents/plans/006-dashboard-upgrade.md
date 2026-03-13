# Plan: Dashboard Upgrade — Real-Time & Rich Views

> Priority: 2 (depends on: Plan 3 queue API, Plan 4 metrics API)
> Parallel: ✅ After dependencies

## Goal

Upgrade the web dashboard with WebSocket real-time updates, plan queue view, goal tracker, dark mode, and interactive controls.

## Epics

### EPIC-001 — WebSocket Real-Time Engine

#### Definition of Done
- [ ] WebSocket handler in `dashboard/ws.py`
- [ ] Real-time war-room state push to all clients
- [ ] Plan queue updates push on change
- [ ] Reconnection logic in frontend

#### Acceptance Criteria
- [ ] War-room status changes appear instantly in browser
- [ ] Multiple browser tabs stay synchronized
- [ ] Connection survives brief network interruptions

#### Tasks
- [ ] TASK-001 — Implement WebSocket handler with room state broadcasting
- [ ] TASK-002 — Add frontend WebSocket client with auto-reconnect
- [ ] TASK-003 — Wire plan queue and goal tracker to WebSocket events

### EPIC-002 — Rich Dashboard Views

#### Definition of Done
- [ ] Plan Queue view: queued → active → completed
- [ ] War-Room Grid: status badges, progress bars, goal completion %
- [ ] Room Detail: channel view, goal checklist, audit log
- [ ] Goal Tracker: cross-room goal completion matrix
- [ ] Dark mode with glassmorphism design

#### Acceptance Criteria
- [ ] Dashboard shows all views from Module 3 spec
- [ ] Dark mode toggle works
- [ ] Mobile-responsive layout
- [ ] Interactive controls: start/stop/pause rooms from browser

#### Tasks
- [ ] TASK-004 — Build plan queue view with status transitions
- [ ] TASK-005 — Build war-room grid with status badges and progress
- [ ] TASK-006 — Build room detail with channel viewer and goal checklist
- [ ] TASK-007 — Build goal tracker cross-room matrix
- [ ] TASK-008 — Implement dark mode and glassmorphism styling

---

## Configuration

```json
{
    "plan_id": "006-dashboard-upgrade",
    "priority": 2,
    "goals": {
        "definition_of_done": [
            "WebSocket real-time updates",
            "Plan queue view",
            "War-room grid with progress",
            "Goal tracker cross-room view",
            "Dark mode glassmorphism design"
        ],
        "acceptance_criteria": [
            "War-room changes appear instantly in browser",
            "All views from Module 3 spec implemented",
            "Mobile-responsive dark mode"
        ]
    }
}
```
