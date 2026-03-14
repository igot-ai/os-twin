# Plan: Example Feature

## Config
working_dir: /path/to/your/project

## Available Roles

<!-- The planner MUST assign roles from this list to each epic -->
<!-- Use colon syntax for instances: engineer:fe, engineer:be -->

| Role | Instance | Description | Skills |
|------|----------|-------------|--------|
| engineer | (default) | Full-stack engineer | python, javascript, powershell |
| engineer:fe | Frontend Engineer | UI/UX, components, styling | javascript, typescript, css, html |
| engineer:be | Backend Engineer | APIs, databases, infra | python, sql, docker, powershell |
| qa | (auto) | Code review & test validation | testing, security-audit |
| architect | (optional) | System design & tech decisions | architecture, documentation |

## Epic: EPIC-001 — Build React dashboard UI

Roles: engineer:fe
Working_dir: dashboard

Create the dashboard frontend with real-time status cards:
- War-room status grid with color-coded states
- SSE connection for live updates
- Theme toggle (dark/light mode)

The engineer will decompose this into sub-tasks and create TASKS.md.

Acceptance criteria:
- Dashboard renders all active war-rooms
- Status colors match state (blue=engineering, green=passed, red=failed)
- SSE reconnects automatically on disconnect

## Epic: EPIC-002 — Build FastAPI backend

Roles: engineer:be
Working_dir: api

Create the REST + WebSocket API layer:
- GET /warrooms endpoint returning room state
- SSE /stream endpoint for real-time broadcasts
- CORS configuration

Acceptance criteria:
- API returns valid JSON for all war-rooms
- SSE stream emits events within 2s of state change
- CORS allows dashboard origin

## Epic: EPIC-003 — Integration testing and documentation

Roles: engineer
Working_dir: .

End-to-end integration between frontend and backend:
- Cypress test suite for dashboard
- API endpoint tests
- README with setup instructions

Acceptance criteria:
- All Cypress tests pass
- README covers installation, running, and architecture
