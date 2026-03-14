# Plan: Example Feature

## Config
working_dir: /path/to/your/project

## Agent Roles

<!-- SUGGESTED ROLES — common starting points, not a limit -->
<!-- You are encouraged to invent the ideal specialist for each epic -->

| Role | Description | Skills |
|------|-------------|--------|
| engineer | General full-stack engineer | python, javascript, powershell |
| engineer:fe | Frontend specialist | javascript, typescript, css, html |
| engineer:be | Backend specialist | python, sql, docker, powershell |
| qa | Code review & test validation | testing, security-audit |
| architect | System design & tech decisions | architecture, documentation |

### Defining Custom Roles

You are NOT limited to the roles above. For each epic, define the best-fit agent
for the job. Invent specialized roles that match the work — the more specific the
role, the better the agent performs.

Per-epic format:
```
Role: <role-name>            (preset name OR any custom role you invent)
Objective: <mission>         (what this agent must achieve — be specific)
Skills: <capabilities>       (comma-separated, guides the agent's focus)
Working_dir: <path>          (scope the agent to a subdirectory)
```

Example custom roles you might create:
- `database-architect` — schema design, migrations, query optimization
- `security-auditor` — OWASP review, auth hardening, secrets scanning
- `devops-engineer` — CI/CD pipelines, Docker, deployment automation
- `technical-writer` — API docs, README, architecture decision records
- `performance-engineer` — profiling, caching, load testing
- `data-pipeline-engineer` — ETL, data validation, streaming
- `accessibility-specialist` — WCAG compliance, screen reader testing

Think: **"What kind of expert would I hire specifically for this epic?"**

---

## Epic: EPIC-001 — Build React dashboard UI

Role: frontend-engineer
Objective: Build a responsive real-time dashboard with polished UX and accessibility
Skills: react, typescript, tailwindcss, websockets, a11y
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

Role: api-engineer
Objective: Design and implement a robust REST + WebSocket API layer with clean separation of concerns
Skills: python, fastapi, websockets, pydantic, cors
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

Role: test-engineer
Objective: Ensure end-to-end quality with comprehensive integration tests and clear documentation
Skills: cypress, pytest, technical-writing, ci-cd
Working_dir: .

End-to-end integration between frontend and backend:
- Cypress test suite for dashboard
- API endpoint tests
- README with setup instructions

Acceptance criteria:
- All Cypress tests pass
- README covers installation, running, and architecture
