export interface PlanTemplate {
  label: string;
  title: string;
  content: string;
}

export const PLAN_TEMPLATES: Record<string, PlanTemplate> = {
  hello: {
    label: 'Hello World',
    title: 'Hello World',
    content: `# Plan: Hello World

## Config
working_dir: .

## EPIC-001 - Hello module with tests

Role: python-engineer
Objective: Build a clean, well-tested Python module following best practices
Skills: python, pytest, packaging

Build hello.py with a greet() function and full pytest test suite.

Acceptance criteria:
- greet("World") returns "Hello, World!"
- Module is importable
- pytest passes with 3+ assertions
`,
  },
  api: {
    label: 'REST API',
    title: 'REST API',
    content: `# Plan: REST API

## Config
working_dir: .

## EPIC-001 - API foundation

Role: api-engineer
Objective: Design and implement a robust REST API with clean endpoint structure
Skills: python, fastapi, pydantic, rest-api-design

Create FastAPI app with health endpoint, Pydantic models, and CRUD endpoints for items.

Acceptance criteria:
- GET /health returns {"status":"ok"}
- POST /items creates item, GET /items lists all
- Pydantic validation on all inputs

## EPIC-002 - Test suite

Role: test-engineer
Objective: Achieve comprehensive test coverage with meaningful assertions
Skills: pytest, httpx, test-design, coverage

Write pytest tests for all endpoints with full coverage.

Acceptance criteria:
- All endpoints tested
- 90%+ coverage

## EPIC-003 - Documentation & deployment

Role: devops-engineer
Objective: Set up API docs and containerized deployment
Skills: docker, openapi, ci-cd

Add OpenAPI docs, Dockerfile, and basic CI pipeline.

Acceptance criteria:
- /docs serves interactive API documentation
- Docker build succeeds and container runs
`,
  },
  fullstack: {
    label: 'Full-Stack App',
    title: 'Full-Stack App',
    content: `# Plan: Full-Stack App

## Config
working_dir: .

## EPIC-001 - Backend API

Role: backend-engineer
Objective: Build a secure, well-structured API with auth and data persistence
Skills: python, fastapi, sqlite, jwt-auth, pydantic

FastAPI backend with SQLite, auth, and CRUD endpoints.

Acceptance criteria:
- Auth flow works end-to-end
- All CRUD endpoints functional

## EPIC-002 - Frontend SPA

Role: frontend-engineer
Objective: Create a responsive, accessible SPA with smooth API integration
Skills: react, typescript, tailwindcss, fetch-api, responsive-design

React SPA with login, data views, and API integration.

Acceptance criteria:
- Login/logout works
- Data views render from API

## EPIC-003 - Integration & testing

Role: test-engineer
Objective: End-to-end test coverage across the full stack
Skills: pytest, playwright, test-design

Integration tests for API and E2E tests for the frontend.

Acceptance criteria:
- API integration tests pass
- E2E tests cover core user flows

## EPIC-004 - Deployment

Role: devops-engineer
Objective: Containerize the full stack and set up automated CI/CD
Skills: docker, docker-compose, github-actions, nginx, ci-cd

Docker compose for frontend + backend, GitHub Actions CI pipeline.

Acceptance criteria:
- docker compose up runs the full stack
- CI runs lint, test, build
`,
  },
};
