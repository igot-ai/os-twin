# CLAUDE.md — Project Context for os-twin / ostwin

This file gives Claude (or any future engineer) the operating context for working on **os-twin**, the source repo for the **ostwin** multi-agent war-room orchestrator.

## Rules for merging and modifying files

1. **Never delete or remove a file without verifying its current state on the target branch.** Before removing any file, run `git show origin/main:<path>` (or the relevant branch) to confirm whether it actually exists there. Do NOT rely on `git stash pop` output, merge diffs, or old commit history to decide a file should be deleted.

2. **Merges only resolve conflicts — do not make additional deletions or renames during a merge.** If a merge completes cleanly, every file that exists on main should remain. If `git stash pop` shows a file as deleted, investigate why — do not assume it should be removed.

3. **Check the current state, not old commits.** When investigating a file's status, look at `HEAD` or `origin/main` first. Do not dig into old commits to justify a deletion. A file may have been deleted and restored multiple times — only the current state matters.

4. **When a file appears in unexpected git output (deleted, modified, untracked) after a merge or stash operation, stop and investigate before staging it.** Run `git diff`, `git log --oneline -5 -- <file>`, or `git show origin/main:<file>` to understand what happened. Do not blindly `git add -A`.

5. **Multiple contributors work on this repo.** Always check recent commit history (`git log --oneline -10 -- <file>`) before modifying or removing any file to understand who else has been working on it and why.

## What this project is

**ostwin** is a multi-agent orchestrator that runs LLM agents in parallel "war-rooms" to execute development plans. A plan is a markdown file with multiple `EPIC-NNN` sections; ostwin spawns one agent per epic, manages dependencies via a DAG, and routes results between roles (architect, engineer, qa, etc.).

The repo contains three major components:

| Path | Role |
|---|---|
| `.agents/` | Agent OS — roles, scripts, MCP, war-room orchestration (PowerShell + bash + Python) |
| `dashboard/` | FastAPI backend (`api.py`) + Next.js frontend (`fe/`) at `localhost:9000` |
| `A-mem-sys/` | Agentic Memory MCP server — semantic note storage with vector search |

## Source vs installed layout

There are **two** copies of every script. Confusing the two will burn an afternoon.

| | Source (dev) | Installed (runtime) |
|---|---|---|
| Repo | `~/os-twin/` | `~/.ostwin/.agents/` (and `~/.ostwin/A-mem-sys/`) |
| Updated by | `git pull`, manual edits | `~/os-twin/.agents/install.sh` |
| What ostwin actually runs | ❌ | ✅ |

After every code change in `~/os-twin/`, you must either:
1. Run `~/os-twin/.agents/install.sh` to copy everything, OR
2. Manually `cp ~/os-twin/.agents/<file> ~/.ostwin/.agents/<file>`

The dashboard imports from `~/os-twin/dashboard/` (not the installed copy) when run from the source repo. The dashboard's `routes/` directory is at `~/os-twin/dashboard/routes/` — the `~/.ostwin/dashboard/routes/` directory is empty.

## Major migration (April 2026): deepagents-cli → opencode

Main branch switched the agent runtime from **`deepagents-cli`** to **`opencode`**. Everything related to the old runtime is legacy now.

### What changed

- `.agents/bin/agent` now wraps `opencode run` instead of `deepagents`
- `.agents/mcp/mcp-builtin.json` and `mcp-config.json` use **OpenCode format**:
  - Top-level `"mcp"` key (was `"mcpServers"`)
  - `"command": [...]` array (was `command: str` + `args: list`)
  - `"environment": {...}` (was `"env"`)
  - `{env:VAR}` syntax (was `${VAR}`)
  - `"type": "local"` / `"remote"` annotations
- Each role now has a `default_model` like `google-vertex/gemini-3.1-pro-preview` (provider-prefixed)
- Compile step generates `.opencode/opencode.json` per project — that's what opencode reads
- The deepagents-cli `ClosedResourceError` MCP bug (extensively documented in `A-mem-sys/DEEPAGENTS-MCP-BUG.md`) **does not affect opencode** — opencode handles MCP sessions correctly. The patch in `A-mem-sys/patches/patch-deepagents-mcp.sh` is only needed if you fall back to deepagents-cli.

### Pipeline (current)

```
ostwin run plan.md
  └─► Start-Plan.ps1 — spawns rooms with CWD = plan's working_dir
        └─► Invoke-Agent.ps1 — generates prompt, exec agent
              └─► .agents/bin/agent — wraps opencode run
                    └─► opencode reads .opencode/opencode.json from CWD
                          └─► spawns memory/channel/warroom MCP servers (stdio)
```

## MCP config flow

Three layers:

1. **Source templates** in `~/os-twin/.agents/mcp/`:
   - `mcp-builtin.json` — uses `{env:AGENT_DIR}` for dev mode
   - `mcp-config.json` — deploy template with `{env:HOME}` / `{env:OSTWIN_PYTHON}`

2. **Home config** at `~/.ostwin/.agents/mcp/config.json` — written by `install.sh patch_mcp_config`. Acts as the per-machine source of truth that `compile` reads.

3. **Project config** at `<project>/.agents/mcp/config.json` and `<project>/.opencode/opencode.json` — written by `mcp-extension.sh compile` (called during `ostwin init`).

`config_resolver.py` (in `.agents/mcp/`) resolves placeholders during compile:

- **`${VAR}` and `${VAR:-default}`** — bash-style (legacy)
- **`{env:VAR}`** — OpenCode-style
- **Sources** for var values (in order):
  1. Hardcoded: `HOME`, `AGENT_DIR`, `PROJECT_DIR`, `AGENT_OS_PROJECT_DIR`, `OSTWIN_PYTHON`
  2. `os.environ`
  3. `~/.ostwin/.env`
  4. `<agent_dir>/.env`
  5. `<project_dir>/.env`
  6. `~/.ostwin/.agents/mcp/.env.mcp`
  7. Shell rc files: `~/.bashrc`, `~/.zshrc`, `~/.profile`, `~/.bash_profile` (for `export VAR=value` lines)
- **Relative paths** in env values (e.g. `MEMORY_PERSIST_DIR=./.memory`) are resolved to `<project_dir>/.memory` so MCP servers find the right dir even when spawned from `/tmp/`.
- **Unresolved entries are dropped** (so OpenCode never sees a literal `{env:FOO}` string as an env value).

The compile output (`opencode.json`) also resolves all `{env:*}` references in `command` arrays to absolute paths (e.g. `python` → `/home/user/.ostwin/.venv/bin/python`).

## Memory MCP server (A-mem-sys)

Runs as a stdio MCP server. **All persistence is synchronous** — `save_memory` does the LLM analysis + vector index update + disk write before returning, then exits. This is required because in stdio mode opencode kills the process as soon as the response is sent.

### Key files

- `A-mem-sys/mcp_server.py` — MCP entry point
- `A-mem-sys/agentic_memory/memory_system.py` — `AgenticMemorySystem` class
- `A-mem-sys/agentic_memory/retrievers.py` — `ZvecRetriever` (vector backend)
- `A-mem-sys/memory-cli.py` — CLI fallback when MCP isn't available

### Critical implementation details (don't undo these)

1. **`save_memory` is synchronous, not background-threaded.** Earlier versions used `threading.Thread(daemon=True)` to return "queued" fast, but daemon threads die with the stdio process before the disk write completes. Result: zero notes saved. Fixed by running `add_note()` synchronously (~10s latency, but data actually persists). See `mcp_server.py` `save_memory()`.

2. **`ZvecRetriever.__init__` retries on lock contention.** zvec uses a single-writer file lock on `.memory/vectordb/`. When multiple agents (architect, engineer, qa, etc.) spawn concurrent MCP server processes, only one can hold the lock — the others used to fail with `RuntimeError: Can't lock read-write collection`. Fixed with a 30-second retry loop. See `retrievers.py` `ZvecRetriever.__init__()`.

3. **Memory persistence path resolution** is in `_find_project_root()` in `mcp_server.py`. It checks (in order): `AGENT_OS_ROOT`, `AGENT_OS_PROJECT_DIR`, `MEMORY_PERSIST_DIR` parent, then CWD. The compile step resolves `MEMORY_PERSIST_DIR=./.memory` to an absolute project path, so this fallback chain rarely runs.

4. **Lazy ML imports.** `agentic_memory/memory_system.py` defers `torch`/`transformers`/`sentence-transformers`/`litellm` imports to first use, so the MCP server starts in <1s instead of ~9s. See `_ensure_ml_imports()`.

### Where memories live

```
<project>/
├── .memory/
│   ├── notes/                  ← .md files (auto-organized into directories)
│   │   └── architecture/database/postgresql/postgres-jsonb-indexing.md
│   ├── vectordb/               ← zvec store with file lock
│   ├── mcp_server.log          ← server activity log
│   └── (no daemon files — stdio mode)
```

Each note is a markdown file with frontmatter-style metadata (Tags, Keywords, Links) — auto-generated by Gemini analysis on save.

## Project setup (per-project)

```bash
cd ~/ostwin-workingdir/<project>
ostwin init        # Compiles .opencode/opencode.json with all env vars resolved
ostwin run /path/to/plan.md
```

`ostwin init` does:
1. Scaffolds `.agents/mcp/` from templates
2. Calls `mcp-extension.sh compile` which:
   - Reads `~/.ostwin/.agents/mcp/config.json` (the home config)
   - Resolves all placeholders via `config_resolver.py`
   - Writes `.agents/mcp/config.json` (intermediate, fully resolved)
   - Writes `.opencode/opencode.json` (final, what opencode reads)
3. The `.opencode/opencode.json` includes:
   - `mcp` block with all servers (memory, channel, warroom, etc.) — env vars literal
   - `permission.external_directory` — allows agents to read `~/ostwin-workingdir/*` (where plan files live) and `~/.ostwin/*`
   - `agent` block — opencode agent definitions for every ostwin role (so `--agent architect` doesn't fall back to "build")

## Plan file format

Plans live in `~/ostwin-workingdir/<name>.plan.md`. Format:

```markdown
# Plan: <Title>

> Project: /home/user/ostwin-workingdir/<name>

## Config
working_dir: /home/user/ostwin-workingdir/<name>

## EPIC-001 — <Title>
Roles: architect, database-architect
Objective: ...
Lifecycle: ...
#### Definition of Done
- [ ] ...
#### Tasks
- [ ] TASK-001 — ...
depends_on: []

## EPIC-002 — ...
depends_on: [EPIC-001]
```

**Don't use duplicate EPIC labels.** Each `## EPIC-NNN` heading must be unique. Two `## EPIC-003` headings will confuse the dependency checker and cause rooms to start before their actual upstream is done.

## Dashboard (localhost:9000)

- Backend: FastAPI at `~/os-twin/dashboard/api.py`, port 9000
- Frontend: Next.js at `~/os-twin/dashboard/fe/`
- Plans registry: `~/os-twin/.agents/plans/<hash>.{md,meta.json,roles.json}`
- The dashboard only sees plans in its registry — standalone plan files (`~/ostwin-workingdir/foo.plan.md`) won't show up unless you copy them in or create them via `POST /api/plans/create`

### Memory visualizer tab (added in this branch)

- Backend: `dashboard/routes/amem.py` — endpoints under `/api/amem/{plan_id}/...` (graph, notes, stats)
- Frontend: `dashboard/fe/src/components/plan/MemoryTab.tsx` — three-pane visualizer (note list, force-directed graph, detail panel)
- Wired into `WorkspaceTabs.tsx` and `PlanSidebar.tsx` as the "Memory" tab
- Reads from `<plan.working_dir>/.memory/notes/` directly (no MCP call needed)
- Tests: `dashboard/tests/test_amem_api.py` (33 backend tests), `dashboard/fe/src/__tests__/MemoryTab.test.tsx` (26 frontend tests)

## Vertex AI authentication

Most agent roles use `google-vertex/gemini-*` models. To run agents successfully:

```bash
gcloud auth application-default login --project igot-studio
gcloud auth application-default set-quota-project igot-studio
export GOOGLE_VERTEX_LOCATION=global
```

**Do NOT set:**
- `GOOGLE_APPLICATION_CREDENTIALS` (causes `invalid_scope` — opencode partner-model auth has a bug with service account keys)
- `VERTEX_ACCESS_TOKEN` (not needed)
- `GOOGLE_CLOUD_LOCATION` (conflicts with `GOOGLE_VERTEX_LOCATION`)

Without ADC set up, agents crash immediately with `Request had insufficient authentication scopes.` and never reach the tool call stage. See `A-mem-sys/OPENCODE-VERTEX-SETUP.md` for full details.

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `agent "X" not found. Falling back to default agent` | OpenCode doesn't know about ostwin roles | `mcp-extension.sh compile` injects an `agent` block in `opencode.json` from `~/.ostwin/.agents/config.json` and `~/.ostwin/.agents/roles/*/role.json`. Re-run `ostwin init`. |
| `Model not found: gemini-3-flash-preview/.` | Bare model name without provider prefix | `Invoke-Agent.ps1` auto-prefixes bare names: `gemini*` → `google-vertex/`, `claude*` → `anthropic/`, `gpt*` → `openai/`. role.json files have been batch-fixed too. |
| `Request had insufficient authentication scopes` | ADC not set up | Run gcloud auth steps above |
| `RuntimeError: Can't lock read-write collection` | Concurrent zvec writers | Already fixed with 30s retry in `retrievers.py` |
| `Memory queued for save` but no notes appear | Old version with daemon background thread | Already fixed — `save_memory` is synchronous now |
| `permission requested: external_directory` (auto-rejecting) | Agent tried to read outside the project | `opencode.json` `permission.external_directory` allows `~/ostwin-workingdir/*` and `~/.ostwin/*` |
| `WARROOMS_DIR` points to wrong place | `Start-Plan.ps1` resolved `$warRoomsDir` before parsing the plan's `working_dir` | Fixed: re-resolves `$warRoomsDir` after parsing the plan, unless explicitly set via env |
| War-rooms in `~/os-twin/.war-rooms/` instead of project dir | Same as above |
| `{env:VAR}` placeholder visible in compiled config | Var not in shell, .env, or shell rc files | Set the var in `~/.ostwin/.env` and re-run `ostwin init` (compile auto-loads .env files) |
| `mcp-config.json` (legacy file) shows up unresolved in project | `init.sh` was copying source template directly | Fixed: only `config.json` is generated; `mcp-config.json` is no longer copied to projects |

## Useful one-liners

```bash
# Verify everything is installed
diff -q ~/os-twin/.agents/mcp/config_resolver.py ~/.ostwin/.agents/mcp/config_resolver.py
diff -q ~/os-twin/A-mem-sys/mcp_server.py ~/.ostwin/A-mem-sys/mcp_server.py

# Test memory MCP standalone (bypasses opencode/agent)
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"save_memory","arguments":{"content":"test note with enough content to be meaningful"}}}' | \
  MEMORY_PERSIST_DIR=/tmp/test/.memory \
  GOOGLE_API_KEY=$(grep GOOGLE_API_KEY ~/.ostwin/.env | cut -d= -f2) \
  ~/.ostwin/.venv/bin/python ~/.ostwin/A-mem-sys/mcp_server.py

# See what tools an opencode-launched agent actually called
grep "Calling tool\|⚙\|memory_save" ~/ostwin-workingdir/<project>/.war-rooms/room-*/artifacts/*-output.txt

# See memory server activity
cat ~/ostwin-workingdir/<project>/.memory/mcp_server.log

# Find where war-rooms went (should be in project dir)
find ~/ostwin-workingdir ~/os-twin -name "DAG.json" -path "*/.war-rooms/*" 2>/dev/null

# Recompile a project's opencode config without re-running init
cd ~/ostwin-workingdir/<project> && bash ~/.ostwin/.agents/mcp/mcp-extension.sh compile --project-dir "$(pwd)"

# Test the memory MCP server lock-retry under concurrency
for i in 1 2 3; do
  echo '...save_memory request...' | python ~/.ostwin/A-mem-sys/mcp_server.py &
done
wait
```

## Branch state notes

This is `fix/mcp-memory-fix` branched from `main`. Recent merge from `main` brought in the opencode migration (`691b9cc`, `ee37f67`, `5400c7e`, `19fff58`, `49f34fb`). Conflicts resolved in:

- `init.sh` — adopted main's mcp-config.json priority order
- `install.sh` — kept main's OpenCode env injection but with reference-aware filtering
- `config_resolver.py` — merged main's `mcp` key + `{env:VAR}` syntax with our `${VAR}` resolution and relative path handling
- `mcp-extension.sh`, `Invoke-Agent.ps1` — accepted main (full opencode rewrite), then added back our fixes (env resolution, agent generation, permission rules, model prefixing)
- `mcp-builtin.json`, `mcp-config.json` — pointed memory server to A-mem-sys instead of the deprecated `memory-server.py` (the old shared-memory system)
- `dashboard/api.py` — kept both `amem` and `files` routers
- `WorkspaceTabs.tsx` — kept both `MemoryTab` and `FileBrowser`

## Files that should NOT exist (deprecated)

- `~/os-twin/.agents/mcp/memory-server.py` — old shared-memory system, replaced by A-mem-sys (file is renamed to `memory-server.deprecated.py`)
- `<project>/.agents/mcp/mcp-config.json` — legacy intermediate file, no longer copied during init
- `~/ostwin-workingdir/<project>/.opencode/opencode.json` containing `{env:FOO}` literal strings — should be fully resolved after init
