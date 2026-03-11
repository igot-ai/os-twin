# Task: TASK-001

Backend API Foundation (Node.js/Express)

Create a mock engineer bash script (`mock-agent-backend.sh`) that uses heredocs to build the backend layer of the application. The backend must be a well-structured Node.js Express REST API that manages the student's courses and semester tasks. 

Requirements:
- Initialize `package.json` with required dependencies (express, cors, body-parser).
- Create `server.js` with structured routing.
- Implement API endpoints: `GET /api/courses`, `POST /api/courses`, `GET /api/tasks`, `POST /api/tasks`.
- Use a lightweight local storage solution (e.g., in-memory array or local JSON file) to store mocked university data.
- The backend should run on port 3000.

Acceptance criteria:
- Running `bash mock-agent-backend.sh` generates the complete backend source code.
- `npm install` executes without errors.
- The Express server starts successfully and listens on port 3000.
- QA Step: A mock QA script `qa-backend.sh` successfully curls `/api/courses` and receives a 200 OK JSON response.

## Working Directory
/Users/paulaan/PycharmProjects/agent-os/projects/semester-planner

## Created
2026-03-11T07:52:15Z
