# OS Twin — Multi-Agent War-Room Orchestration

An operating system for AI agents where an **Engineer Manager** orchestrates parallel **War-Rooms**, each containing an **Engineer** and a **QA Engineer** collaborating through shared JSONL channels until all tasks pass quality gates.

## Architecture

```
          ┌─────────────────────────────────┐
          │       ENGINEER MANAGER          │
          │    reads PLAN → spawns rooms    │
          │    monitors → routes → releases │
          └──────┬──────────┬──────────┬────┘
                 ▼          ▼          ▼
           WAR-ROOM 1  WAR-ROOM 2  WAR-ROOM N
           ┌────────┐  ┌────────┐  ┌────────┐
           │Engineer│  │Engineer│  │Engineer│
           │   ↕    │  │   ↕    │  │   ↕    │
           │  QA    │  │  QA    │  │  QA    │
           └────────┘  └────────┘  └────────┘
```

## Quick Start

```bash
cp .agents/plans/PLAN.template.md .agents/plans/my-feature.md   # 1. Create a plan
.agents/run.sh .agents/plans/my-feature.md                       # 2. Launch
.agents/war-rooms/status.sh                                      # 3. Monitor
```

## Dev Mode

**Prerequisites:** Python 3.10+, Node.js 18+, pnpm

### Setup

```bash
# Dashboard backend (FastAPI)
cd dashboard && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Dashboard frontend (Next.js)
cd dashboard/fe && pnpm install

# MCP servers (memory, channel, warroom)
cd .agents && python3 -m venv .venv && source .venv/bin/activate && pip install "mcp[cli]" fastmcp
```

### Run

```bash
source dashboard/.venv/bin/activate && python dashboard/api.py   # Backend  → :9000
cd dashboard/fe && pnpm dev                                      # Frontend → :3000
.agents/run.sh path/to/plan.md                                   # Launch a plan
```

Custom ports: `python dashboard/api.py --port 9069` + `OSTWIN_BACKEND_URL=http://localhost:9069 pnpm dev -p 3069`

> **AI assistants:** You MUST activate the venv (`source dashboard/.venv/bin/activate`) before any `pip` or `python` command.

### Memory (cross-room shared context)

Agents share context via MCP memory server — `publish`/`query`/`search` tools backed by an append-only JSONL ledger. Without memory, agents in later rooms guess function names and API contracts from earlier rooms.

```bash
.agents/memory-monitor.sh status   # Check ON/OFF + ledger stats
.agents/memory-monitor.sh watch    # Live stream new entries
.agents/memory-monitor.sh on       # Enable (restore .venv)
.agents/memory-monitor.sh off      # Disable (move .venv)
```

Inspect MCP server directly:
```bash
AGENT_OS_ROOT=/home/tcuong1000/os-twin \
npx @modelcontextprotocol/inspector \
  /home/tcuong1000/os-twin/dashboard/.venv/bin/python \
  /home/tcuong1000/os-twin/.agents/mcp/memory-server.py
```

## How It Works

All entry points (CLI, dashboard, Telegram) execute `.agents/run.sh` → reads `working_dir` from plan → registers to `~/.ostwin/plans/` → spawns war-rooms → starts manager loop.

Dashboard connects via **file polling** (1s interval): agents write `channel.jsonl`/`status` → backend detects changes → broadcasts via WebSocket/SSE → frontend receives via SWR.

## Data Layout

**Project-local** (follows `working_dir` in plan, overridable via `--project-dir`):

| Location | What |
|---|---|
| `<project>/.war-rooms/room-*/` | War-room state: `channel.jsonl`, `config.json`, `artifacts/` |
| `.agents/memory/` | Shared cross-room memory: `ledger.jsonl`, `index.json` |

**Global** (fixed at `~/.ostwin/`):

| Location | What |
|---|---|
| `~/.ostwin/plans/` | Plan files + `.meta.json` |
| `~/.ostwin/.zvec/` | Vector store (embeddings cache) |
| `~/.ostwin/.env` | API keys & secrets |
| `~/.ostwin/dashboard/debug.log` | Dashboard log |
