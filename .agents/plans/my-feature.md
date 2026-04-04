# Plan: Example Feature

## Config
working_dir: .

## Agent Roles

| Role | Description | Skills |
|------|-------------|--------|
| engineer | General full-stack engineer | python, javascript, powershell |
| engineer:fe | Frontend specialist | javascript, typescript, css, html |
| engineer:be | Backend specialist | python, sql, docker, powershell |
| qa | Code review & test validation | testing, security-audit |
| architect | System design & tech decisions | architecture, documentation |

---

## EPIC-001 - Build React dashboard UI

Role: frontend-engineer
Objective: Build a responsive real-time dashboard with polished UX and accessibility
Skills: react, typescript, tailwindcss, websockets, a11y
Working_dir: dashboard

Create the dashboard frontend with real-time status cards:
- War-room status grid with color-coded states
- SSE connection for live updates
- Theme toggle (dark/light mode)

#### Definition of Done
- [ ] Responsive UI
- [ ] SSE integration
- [ ] Theme support
- [ ] Accessible
- [ ] Unit tests pass

#### Acceptance Criteria
- [ ] Grid displays rooms
- [ ] Colors update
- [ ] Reconnects on failure
- [ ] Dark mode works
- [ ] Lighthouse score > 90

depends_on: []


## EPIC-002 - Build FastAPI backend

Role: api-engineer
Objective: Design and implement a robust REST + WebSocket API layer with clean separation of concerns
Skills: python, fastapi, websockets, pydantic, cors
Working_dir: api

Create the REST + WebSocket API layer:
- GET /warrooms endpoint returning room state
- SSE /stream endpoint for real-time broadcasts
- CORS configuration

#### Definition of Done
- [ ] API routes implemented
- [ ] SSE streaming active
- [ ] Pydantic models defined
- [ ] CORS set
- [ ] Documentation auto-generated

#### Acceptance Criteria
- [ ] /warrooms returns JSON
- [ ] /stream events under 2s
- [ ] Frontend can connect via CORS
- [ ] Swagger UI accessible
- [ ] All endpoints tested

depends_on: []


## EPIC-003 - Integration testing and documentation

Role: test-engineer
Objective: Ensure end-to-end quality with comprehensive integration tests and clear documentation
Skills: cypress, pytest, technical-writing, ci-cd
Working_dir: .

End-to-end integration between frontend and backend:
- Cypress test suite for dashboard
- API endpoint tests
- README with setup instructions

#### Definition of Done
- [ ] Cypress tests integrated
- [ ] Integration scenarios covered
- [ ] README complete
- [ ] CI pipeline config
- [ ] Sign-off from QA

#### Acceptance Criteria
- [ ] All tests pass
- [ ] README covers setup
- [ ] Dashboard works with Backend
- [ ] Coverage > 80%
- [ ] Documentation is clear

depends_on: [EPIC-001, EPIC-002]



