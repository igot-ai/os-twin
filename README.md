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

## Dev Mode (Dashboard)

**Prerequisites:** Python 3.10+, Node.js 18+, pnpm

```bash
# First-time setup
cd dashboard && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd fe && pnpm install

# Run (two terminals)
source dashboard/.venv/bin/activate && python dashboard/api.py   # Backend  → :9000
cd dashboard/fe && pnpm dev                                      # Frontend → :3000
```

Custom ports — set `OSTWIN_BACKEND_URL` so the frontend proxy follows:
```bash
python dashboard/api.py --port 9069
OSTWIN_BACKEND_URL=http://localhost:9069 pnpm dev -p 3069
```

Override project directory: `python dashboard/api.py --project-dir /path/to/project`

> **AI assistants (Claude, Codex, etc.):** You MUST activate the venv (`source dashboard/.venv/bin/activate`) before any `pip` or `python` command. Do NOT install packages globally.

## Data Layout

| Location | What |
|---|---|
| `.war-rooms/room-*/` | War-room state: `channel.jsonl`, `config.json`, `artifacts/` |
| `.agents/memory/` | Shared cross-room memory: `ledger.jsonl`, `index.json` |
| `~/.ostwin/plans/` | Plan files + `.meta.json` |
| `~/.ostwin/.zvec/` | Vector store (embeddings cache) |
| `~/.ostwin/.env` | API keys & secrets |
| `~/.ostwin/dashboard/debug.log` | Dashboard log |

Project-local data (`.war-rooms/`, `.agents/memory/`) lives under the repo root. Global data (`plans`, `logs`, `vector store`) lives under `~/.ostwin/`.
