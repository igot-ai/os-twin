# OS Twin — Multi-Agent War-Room Orchestration

An operating system for AI agents where an **Engineer Manager** orchestrates parallel **War-Rooms**, each containing an **Engineer** and a **QA Engineer** collaborating through shared JSONL channels until all tasks pass quality gates.

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

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

### With install (adds `ostwin` to PATH, installs all deps)

```bash
.agents/install.sh
ostwin run plans/my-feature.md
```

### Without install (run directly from source)

```bash
.agents/bin/ostwin run plans/my-feature.md
```

**Requires:** `pwsh`, `python3`, `deepagents-cli` installed manually.
Put API keys in `.agents/.env` (project-local) instead of `~/.ostwin/.env`.

Runtime writes (nothing touches `~/.ostwin/`):
- `.war-rooms/` — room state, artifacts, channels (gitignored)
- `.agents/manager.pid` — manager process PID (gitignored via `*pid`)
- `.agents/logs/` — `ostwin.log`, `ostwin.jsonl` (gitignored)
- `.agents/skills/` — fetched SKILL.md, only if dashboard API is connected
- Input `plan.md` may be modified in-place on approval/expansion

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

`ostwin run` dispatches to `Start-Plan.ps1` (via `ps_dispatch`) → parses plan → spawns war-rooms → starts manager loop. No files written outside the project. The legacy `run.sh` fallback (no pwsh) also registers plans to `~/.ostwin/plans/` for dashboard discovery.

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
=======
## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
>>>>>>> 76d4bb8 (add Vite React frontend scaffold and update configs)
