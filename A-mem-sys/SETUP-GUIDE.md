# Memory MCP Server — Setup Guide

This guide explains how to set up the Agentic Memory MCP server for use with ostwin agents, Codex, Claude Code, and OpenCode.

If you want to run OpenCode against Vertex AI partner models such as `zai-org/glm-5-maas`, see [`OPENCODE-VERTEX-SETUP.md`](OPENCODE-VERTEX-SETUP.md) for the required ADC and region configuration.

## Prerequisites

- Python 3.12+ with `~/.ostwin/.venv/`
- `ostwin` CLI installed (`~/.ostwin/.agents/`)
- `GOOGLE_API_KEY` set in `~/.ostwin/.env` (for Gemini embedding/LLM)

## Step 1: Install

Run from the os-twin source repo:

```bash
cd ~/os-twin
.agents/install.sh
```

This does:
- Copies `A-mem-sys/` to `~/.ostwin/A-mem-sys/`
- Sets up MCP builtin config to point to `~/.ostwin/A-mem-sys/mcp_server.py`
- Installs Python dependencies

## Step 2: Patch deepagents-cli

> **Skip this step if you only use Codex or Claude Code.** They don't have the bug.

deepagents-cli v0.0.34 has a bug where MCP tool calls crash with `ClosedResourceError`. Apply the fix:

```bash
bash ~/.ostwin/A-mem-sys/patches/patch-deepagents-mcp.sh
```

What it does:
- Adds `stateless=True` mode to MCP tool loading
- Each tool call creates a fresh session instead of reusing a dead one
- Only affects the LangGraph server path; CLI and ACP paths are unchanged

> **Note**: Re-run this after `uv tool upgrade deepagents-cli`.

For full details, see [patches/README.md](patches/README.md) and [DEEPAGENTS-MCP-BUG.md](DEEPAGENTS-MCP-BUG.md).

## Step 3: Initialize a project

```bash
cd ~/ostwin-workingdir/my-project
ostwin init
```

This creates `.agents/mcp/config.json` with the memory server configured in **stdio mode** (default).

## Step 4: Verify

```bash
ostwin mcp test --all
```

Expected output:
```
channel    ✓ Connected   3 tools
memory     ✓ Connected   5 tools
warroom    ✓ Connected   3 tools
```

## Step 5: Enable MCP for agents

In `~/.ostwin/.agents/config.json`, ensure all roles have:

```json
"no_mcp": false
```

> With `no_mcp: true`, agents cannot see or use any MCP tools.

---

## Transport Modes

The memory server supports two transport modes. You can switch between them at any time.

### Stdio (default)

Each tool call spawns a new server process, calls the tool, and exits.

| Pros | Cons |
|------|------|
| No setup needed | Each call takes ~8-10s (loading ML libraries) |
| Works out of the box | No persistent server |
| No daemon to manage | No background auto-sync |

**When to use**: Development, testing, infrequent memory calls.

### SSE Daemon (recommended for production)

A persistent background HTTP server. Tool calls connect via SSE — instant response.

| Pros | Cons |
|------|------|
| Fast tool calls (<1s) | Must start daemon before running agents |
| Persistent server | One daemon per project |
| Auto-syncs to disk every 60s | Uses a network port |

**When to use**: Running `ostwin run` with plans, heavy memory usage, multiple agents.

---

## Using Stdio Mode

This is the default. After `ostwin init`, your project is already configured for stdio.

```bash
# Verify
cd ~/ostwin-workingdir/my-project
~/os-twin/A-mem-sys/switch-memory-transport.sh status .
# Output: Transport: stdio

# Run agents
ostwin run my-plan.md
```

To switch back to stdio from SSE:

```bash
~/os-twin/A-mem-sys/switch-memory-transport.sh stdio ~/ostwin-workingdir/my-project
```

---

## Using SSE Daemon Mode

### Start the daemon

```bash
~/os-twin/A-mem-sys/start-memory-daemon.sh ~/ostwin-workingdir/my-project
```

Output:
```
Starting memory daemon...
  Project: /home/user/ostwin-workingdir/my-project
  Persist: /home/user/ostwin-workingdir/my-project/.memory
  Port:    6487
  URL:     http://127.0.0.1:6487/sse
  PID:     12345
```

The port is automatically derived from the project path. Same project always gets the same port.

### Switch the project to SSE

The `start-memory-daemon.sh` automatically updates the project's MCP config. But you can also switch manually:

```bash
~/os-twin/A-mem-sys/switch-memory-transport.sh sse ~/ostwin-workingdir/my-project
```

### Run agents

```bash
cd ~/ostwin-workingdir/my-project
ostwin run my-plan.md
```

### Check status

```bash
~/os-twin/A-mem-sys/start-memory-daemon.sh --status ~/ostwin-workingdir/my-project
# Output: Running (PID 12345, port 6487)
```

### Stop the daemon

```bash
# Stop one project's daemon
~/os-twin/A-mem-sys/start-memory-daemon.sh --stop ~/ostwin-workingdir/my-project

# Stop ALL daemons
~/os-twin/A-mem-sys/start-memory-daemon.sh --stop-all
```

### Multiple projects simultaneously

Each project gets its own daemon on a unique port:

```bash
~/os-twin/A-mem-sys/start-memory-daemon.sh ~/ostwin-workingdir/project-a
# → port 6487

~/os-twin/A-mem-sys/start-memory-daemon.sh ~/ostwin-workingdir/project-b
# → port 6521

# Both running independently, each with their own .memory/
```

---

## Where Memories Are Stored

```
my-project/
├── .agents/mcp/config.json       ← MCP config (stdio or SSE)
├── .memory/                      ← All memory data lives here
│   ├── notes/                    ← Markdown files (one per memory)
│   │   └── architecture/
│   │       └── database-schema.md
│   ├── vectordb/                 ← Embedding vectors for search
│   ├── mcp_server.log            ← Server log (stdio mode)
│   ├── daemon.log                ← Daemon log (SSE mode)
│   ├── .daemon.pid               ← Daemon PID file (SSE mode)
│   └── .daemon.port              ← Daemon port file (SSE mode)
```

---

## Available MCP Tools

| Tool | Description | Example |
|------|-------------|---------|
| `save_memory` | Save a new memory | `save_memory(content="...", name="API design", path="architecture/api", tags=["api"])` |
| `search_memory` | Semantic search | `search_memory(query="database indexing", k=5)` |
| `memory_tree` | Show directory tree | `memory_tree()` |
| `grep_memory` | Full-text search | `grep_memory("PostgreSQL", "-i")` |
| `find_memory` | Find by filename | `find_memory("-name '*database*'")` |

### Writing good memories

Write **detailed** content (3-10 sentences). Include:
- **WHAT** was decided or built
- **WHY** it was chosen over alternatives
- **HOW** it works in practice
- **GOTCHAS** or edge cases

Bad: `"Use PostgreSQL JSONB for products."`

Good: `"PostgreSQL's JSONB type stores semi-structured data with full indexing support via GIN indexes. We chose it over MongoDB because our data has relational aspects (user→orders→items) but product attributes vary per category. The GIN index on product.attributes reduced catalog search from 800ms to 12ms. Key gotcha: JSONB equality checks are exact-match, so normalize data before insertion."`

---

## Troubleshooting

### `ClosedResourceError` on tool calls

The deepagents-cli patch is not applied:
```bash
bash ~/.ostwin/A-mem-sys/patches/patch-deepagents-mcp.sh
```

### `ostwin mcp test` shows 0 tools for memory

The daemon may not be running (SSE mode), or the `notifications/initialized` handshake is missing (test limitation). Try calling a tool directly to verify.

### `.memory/` not created

The server hasn't started yet. Verify with:
```bash
ostwin mcp test memory
```

### Agents don't call `save_memory`

Check `no_mcp` in `~/.ostwin/.agents/config.json`. Must be `false` for the agent's role.

Check wrapper logs:
```bash
grep "Calling tool" .war-rooms/room-*/artifacts/*.wrapper.log
```

### Slow tool calls (8-10s)

Expected with stdio mode. Each call loads the full ML stack. Switch to SSE daemon:
```bash
~/os-twin/A-mem-sys/start-memory-daemon.sh .
~/os-twin/A-mem-sys/switch-memory-transport.sh sse .
```

### Port already in use

```bash
~/os-twin/A-mem-sys/start-memory-daemon.sh --stop-all
```

---

## Clients Compatibility

| Client | stdio | SSE | Patch needed? |
|--------|-------|-----|---------------|
| Codex (OpenAI) | ✅ | ✅ | No |
| Claude Code | ✅ | ✅ | No |
| deepagents-cli (ostwin) | ✅ | ✅ | Yes — [patch](patches/README.md) |
