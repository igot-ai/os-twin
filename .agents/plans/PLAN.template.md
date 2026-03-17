# Plan: Example Feature

> Created: 2026-03-17T00:00:00+00:00
> Status: draft
> Project: /path/to/your/project

## Config

working_dir: /path/to/your/project

---

## Goal

A clear, concise description of what this plan aims to achieve and the problem it solves.

## EPIC-001 - Foundation & Core Setup

Tasks: Set up the project structure, dependencies, and configuration. Define data models and database schemas. Implement the core domain logic and foundational services that all other epics will depend on.

#### Definition of Done
- [ ] Core functionality implemented

#### Tasks
- [ ] TASK-001 — Design and plan implementation

Acceptance criteria:
- Project structure is scaffolded and all dependencies are installed.
- Core data models and schemas are defined and migrated.
- Foundational services are implemented and unit-tested.

depends_on: []

## EPIC-002 - Feature Implementation

Tasks: Build the main feature logic on top of the foundation. Expose the necessary API endpoints or interfaces. Integrate with external services if required.

#### Definition of Done
- [ ] Core functionality implemented

#### Tasks
- [ ] TASK-001 — Design and plan implementation

Acceptance criteria:
- All API endpoints return correct responses for happy-path and edge-case inputs.
- Integration with external services is verified with mock/test credentials.
- Feature behaves correctly end-to-end as described in the Goal.

depends_on: [EPIC-001]

## EPIC-003 - Testing & Delivery

Tasks: Write end-to-end and integration tests covering the main user journeys. Fix any bugs surfaced during testing. Prepare documentation and deploy to the target environment.

#### Definition of Done
- [ ] Core functionality implemented

#### Tasks
- [ ] TASK-001 — Design and plan implementation

Acceptance criteria:
- All automated tests pass with no critical failures.
- README documents setup, usage, and architecture decisions.
- Application is successfully deployed and verified in the target environment.

depends_on: [EPIC-001, EPIC-002]
