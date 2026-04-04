# Developer Context

This note is for developers who need to understand how this repo actually behaves in day-to-day use, especially when running plans, debugging dashboard issues, or working with the memory system.

It reflects hands-on investigation of the codebase and real runs, not just intended architecture.

## What This Repo Is

OS Twin is an orchestration layer for agent-driven work.

At a high level it:

- reads a markdown plan
- creates one war-room per epic/task
- runs a manager loop that advances room state
- launches role-specific agents like engineer, qa, architect
- optionally exposes a dashboard for plans, rooms, and operations

The main entrypoint is:

- `.agents/run.sh`

That script extracts `working_dir:` from the plan and passes control to:

- `.agents/plan/Start-Plan.ps1`

## Core Concepts

### `working_dir`

`working_dir` is the target code workspace from the plan file.

Example:

```md
working_dir: /home/tcuong1000/ostwin-workingdir/youtube-clone
```

This is where agents are expected to edit code.

### War-Rooms

War-rooms are per-epic execution folders. In source-mode plan runs, they live under:

```text
<working_dir>/.war-rooms
```

Example:

```text
/home/tcuong1000/ostwin-workingdir/youtube-clone/.war-rooms
```

Each room usually contains:

- `brief.md`
- `config.json`
- `channel.jsonl`
- `status`
- `artifacts/`
- `pids/`
- `contexts/`

### `.agents`

The repo’s `.agents` directory is the framework/runtime side of OS Twin. It contains:

- scripts
- manager loop
- role definitions
- plan tooling
- dashboard launcher
- memory store
- some global logs and metadata

## Source Mode vs Installed Mode

There are two important operating modes.

### Source Mode

Use this when developing OS Twin from the repo checkout.

Paths:

- repo: `/home/tcuong1000/os-twin`
- scripts/runtime: `/home/tcuong1000/os-twin/.agents`
- target project: from plan `working_dir`
- war-rooms: `<working_dir>/.war-rooms`

Typical command:

```bash
cd /home/tcuong1000/os-twin
.agents/run.sh .agents/plans/my-plan.md
```

### Installed Mode

This means running the installed runtime under:

```text
~/.ostwin
```

That tree may contain its own:

- `.venv`
- `dashboard/`
- `memory/`
- `war-rooms/`
- `.env`
- `config.json`

Installed mode is useful for using OS Twin as a tool. Source mode is what you want for developing the project itself.

## Important Path Reality

For a normal source-mode run, think in three zones:

1. The code workspace

```text
<working_dir>
```

2. The room workspace

```text
<working_dir>/.war-rooms
```

3. The framework/runtime workspace

```text
/home/tcuong1000/os-twin/.agents
```

This matters because not everything follows `working_dir`.

Examples:

- code edits happen in `working_dir`
- room artifacts happen in `working_dir/.war-rooms`
- memory store lives in `.agents/memory`
- some global logs and manager metadata live in `.agents`

## How Plan Execution Works

Execution path:

1. `.agents/run.sh` reads `working_dir`
2. `.agents/plan/Start-Plan.ps1` parses the plan
3. room-000 is created for plan negotiation/review
4. one room per epic/task is created
5. a DAG is written into `<working_dir>/.war-rooms/DAG.json`
6. `.agents/roles/manager/Start-ManagerLoop.ps1` starts polling rooms

### Iteration Count in Logs

When you see:

```text
Progress: 2/3 passed, 0 failed, 0 blocked (iteration 225)
```

`iteration` means one pass through the manager main loop, not one task attempt.

The manager loop:

- increments an iteration counter
- scans all `room-*` directories
- checks each room’s state and dependencies
- logs throttled progress updates
- sleeps for the configured poll interval

In this repo, the default poll interval is 5 seconds.

That is why progress logs often show odd-numbered iterations only: progress logging is throttled to 10-second intervals.

## Dashboard: Build Mode vs Dev Mode

This project has two distinct dashboard modes.

### Build Mode

This is the mode the repo supports best out of the box.

Flow:

- build Next frontend to `dashboard/fe/out`
- run FastAPI backend
- FastAPI serves both static frontend and `/api/*` from the same port

Why it feels smoother:

- no cross-origin browser requests
- SPA fallback can hide missing route files
- frontend and backend share one origin

### Dev Mode

True dev mode means two processes:

1. FastAPI backend on one port, usually `9000`
2. Next.js frontend on another port, usually `3000`

This is more realistic for frontend work, but historically it had several rough edges:

- missing `/plans` route in Next app
- cross-origin auth/CORS issues when the browser hit the backend directly
- inconsistent use of `NEXT_PUBLIC_API_BASE_URL`
- source-mode path handling issues for external `working_dir`
- occasional broken optional frontend dependencies during `npm install`

### Dev Mode Rules

For dev mode, the browser should talk to same-origin `/api`, and Next should proxy to FastAPI.

Do not point browser code directly at `http://localhost:9000/api` unless you deliberately want cross-origin behavior.

Recommended backend command:

```bash
cd /home/tcuong1000/os-twin
OSTWIN_DEV_MODE=1 OSTWIN_API_KEY=DEBUG /home/tcuong1000/os-twin/dashboard/.venv/bin/python \
  /home/tcuong1000/os-twin/dashboard/api.py \
  --project-dir /home/tcuong1000/ostwin-workingdir/youtube-clone \
  --port 9000
```

Recommended frontend command:

```bash
cd /home/tcuong1000/os-twin/dashboard/fe
OSTWIN_BACKEND_URL=http://localhost:9000 npm run dev
```

Open:

```text
http://localhost:3000
```

### If Dev Mode Shows `ECONNREFUSED`

That means the Next proxy cannot reach the backend. It is not a frontend routing issue.

Check:

```bash
curl http://localhost:9000/api/auth/local-key
curl http://localhost:9000/api/plans
```

If those fail, the backend is not running or crashed.

### If Build Mode Shows `{"detail":"Not Found"}` at `/`

That usually means the FastAPI backend is up, but the frontend export does not exist.

Build output expected here:

```text
dashboard/fe/out
```

## Current Source-Mode Dashboard Caveat

There is an important source-mode footgun when `working_dir` points outside the repo.

Pattern:

- repo scripts/runtime come from `/home/tcuong1000/os-twin/.agents`
- actual project is somewhere else, like `/home/tcuong1000/ostwin-workingdir/youtube-clone`
- war-rooms live in the external project’s `.war-rooms`

The dashboard code has historically applied `--project-dir` too late, after some path-sensitive modules are imported.

Effect:

- the backend may print the correct `War-rooms:` path
- but route modules can still hold stale values from the repo root

Symptom:

- dashboard starts
- but rooms/plans may appear empty or wrong for external `working_dir`

If you debug dashboard path issues, inspect:

- `dashboard/api.py`
- `dashboard/api_utils.py`
- `dashboard/routes/rooms.py`
- `dashboard/routes/plans.py`

## Memory System Overview

The memory system is a three-tier design under:

```text
.agents/memory
```

Tiers:

- `working/` = short-term session notes
- `sessions/` = session digests
- `knowledge/` = long-term facts

### How It Works

Before a session:

- memory is resolved from local files
- relevant memory is injected into the system prompt

During a session:

- agent can call memory tools like `memory_note`, `memory_drop`, `memory_recall`

After a session:

- a consolidation step extracts reusable facts and session digests
- long-term memory is updated
- decay/pruning may run

### What Is Good About It

- clear tiering
- file-based storage is inspectable and debuggable
- prompt injection is straightforward
- session digests are compact and readable

### What Is Risky About It

The current implementation has a few important caveats:

- prompt-time recall can inflate access counts
- stale facts can remain highly retrievable
- QA-learning extraction has been fragile
- duplication is common in knowledge files
- some operational noise becomes “memory”

In practice, the memory store is useful, but should not be treated as perfectly clean project truth.

## Memory Store Quality Notes

Observed behavior from real data:

- useful project facts do accumulate
- duplication is significant
- stale constraints can leak into future prompts
- access counts can become inflated

So the system is good as a proof of value, but still needs hygiene work:

- deduplication
- better confidence/access semantics
- stricter filtering of operational noise

## Skill Resolution and Dashboard Dependency

The manager loop can try to auto-discover room-specific skills using the dashboard API.

This means:

- core orchestration can still run without the dashboard
- but skill auto-discovery may warn if the dashboard is unavailable

Typical warning:

```text
Skill resolution failed (dashboard may be offline): Connection refused
```

This is usually non-fatal. It means the room keeps its base role skills, but does not get extra auto-discovered room-level skills.

## Common Git Confusions

### `git pull main` is wrong

Use:

```bash
git pull origin main
```

`main` is a branch, not a remote.

### Merge latest remote main into a feature branch

If already on the feature branch:

```bash
git fetch origin
git merge origin/main
```

### Dirty worktree before merge

If you have local changes, either:

- commit them first
- or stash them first

## Recommended Mental Model

If you are new to the repo, remember:

- `.agents` is the runtime/orchestration brain
- `working_dir` is the code workspace
- `.war-rooms` under the working directory is the per-plan execution state
- dashboard build mode is the most reliable runtime today
- dev mode is possible, but still a moving target
- memory is helpful context, not guaranteed truth

## Suggested Next Docs

If this repo continues evolving, good follow-up internal docs would be:

- a room state-machine reference
- a dashboard architecture note
- a memory hygiene and pruning guide
- a “how to debug a stuck room” playbook
