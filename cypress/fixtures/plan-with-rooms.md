# Plan: Cypress War-Room Test

## Config
working_dir: /tmp/cypress-warroom-test

## Epic: EPIC-CY01 — Auth module

Build the authentication module with JWT tokens.

Acceptance criteria:
- [ ] Login endpoint returns a token
- [ ] Token validation works
- [ ] Refresh tokens supported

## Epic: EPIC-CY02 — User API

Build CRUD endpoints for users.

Acceptance criteria:
- [ ] POST /users creates a user
- [ ] GET /users lists all users
- [ ] DELETE /users/:id removes a user

## Epic: EPIC-CY03 — Test suite

Write pytest tests with full coverage.

Acceptance criteria:
- [ ] All endpoints tested
- [ ] 90%+ coverage
