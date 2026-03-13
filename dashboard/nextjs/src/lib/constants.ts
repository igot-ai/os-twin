import { RoomStatus, MessageType } from '@/types';

export const STATUS_COLOR: Record<string, string> = {
  pending: '#555',
  engineering: '#00d4ff',
  'qa-review': '#ffd93d',
  fixing: '#ff9f43',
  passed: '#00ff88',
  'failed-final': '#ff6b6b',
  paused: '#ffd93d',
};

export const STATUS_LABEL: Record<string, string> = {
  pending: 'PENDING',
  engineering: 'ENGINEERING',
  'qa-review': 'QA REVIEW',
  fixing: 'FIXING',
  passed: 'PASSED',
  'failed-final': 'FAILED',
  paused: 'PAUSED',
};

export const MSG_ICON: Record<string, string> = {
  task: '📋',
  done: '✓',
  review: '🔍',
  pass: '✅',
  fail: '✗',
  fix: '🔧',
  signoff: '✍',
  release: '🚀',
  error: '⚠',
};

export const PROGRESS_PCT: Record<string, number> = {
  pending: 5,
  engineering: 35,
  'qa-review': 65,
  fixing: 45,
  passed: 100,
  'failed-final': 100,
  paused: 50,
};

export const TEMPLATES: Record<string, string> = {
  hello: `# Plan: Hello World

## Config
working_dir: .

## Epic: EPIC-001 — Hello module with tests

Build hello.py with a greet() function and full pytest test suite.

Acceptance criteria:
- greet("World") returns "Hello, World!"
- Module is importable
- pytest passes with 3+ assertions
`,

  api: `# Plan: REST API

## Config
working_dir: .

## Epic: EPIC-001 — API foundation

Create FastAPI app with health endpoint, Pydantic models, and CRUD endpoints for items.

Acceptance criteria:
- GET /health returns {"status":"ok"}
- POST /items creates item, GET /items lists all
- Pydantic validation on all inputs

## Epic: EPIC-002 — Test suite

Write pytest tests for all endpoints with full coverage.

Acceptance criteria:
- All endpoints tested
- 90%+ coverage
`,

  fullstack: `# Plan: Full-Stack App

## Config
working_dir: .

## Epic: EPIC-001 — Backend API

FastAPI backend with SQLite, auth, and CRUD endpoints.

Acceptance criteria:
- Auth flow works end-to-end
- All CRUD endpoints functional

## Epic: EPIC-002 — Frontend SPA

React SPA with login, data views, and API integration.

Acceptance criteria:
- Login/logout works
- Data views render from API

## Epic: EPIC-003 — Deployment

Docker compose for frontend + backend, GitHub Actions CI pipeline.

Acceptance criteria:
- docker compose up runs the full stack
- CI runs lint, test, build
`,
};

export const ACTIVE_STATUSES: RoomStatus[] = ['engineering', 'qa-review', 'fixing'];

export const PIPELINE_MAP: Record<string, RoomStatus[]> = {
  'pipe-manager': ['pending'],
  'pipe-engineer': ['engineering', 'fixing'],
  'pipe-qa': ['qa-review'],
  'pipe-release': ['passed'],
};
