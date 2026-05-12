# Pillar 3: MCP Isolation Per Role

## The Problem

A single browser-automation MCP server like Playwright exposes 50+ tool
definitions. Add GitHub, database, and memory MCP servers, and an agent that
was supposed to spend its tokens *thinking* is instead spending **8-12K tokens
reading tool catalogs it will never call**.

A planning agent (architect) that only needs to reason about code structure
is paying the same token tax as an engineer that actually needs to call tools.

## The Solution: Binary Opt-Out Per Role

OSTwin controls MCP attachment at the role level via a `no_mcp` flag:

```json
{
  "architect": { "no_mcp": true },
  "engineer":  { "no_mcp": false },
  "qa":        { "no_mcp": false }
}
```

- **Architect**: `no_mcp: true` -- runs with zero MCP servers. A pure planning
  agent. Saves 8-12K tokens per invocation.
- **Engineer/QA**: `no_mcp: false` -- gets the full MCP set (channel, warroom,
  memory, github, browser automation).

### Resolution Chain

From `Invoke-Agent.ps1`:

```
Instance config (per-room) -> Role config (global) -> default (false)
```

If the per-room instance config sets `no_mcp`, that wins. Otherwise the global
role config in `.agents/config.json`. If neither specifies, MCP is enabled.

## Per-Room MCP Environment

When MCP is enabled, each war-room gets its own MCP configuration:

1. MCP config is resolved from a 4-tier priority chain:
   - Pre-compiled `.opencode/opencode.json` in project dir
   - Project-local `.agents/mcp/config.json`
   - Engine-level `mcp/config.json`
   - User-level `$OSTWIN_HOME/.agents/mcp/config.json`
2. Template placeholders (`{env:AGENT_DIR}`, `{env:PROJECT_DIR}`) are expanded
   to absolute paths
3. The resolved config is written as `opencode.json` in the room's `artifacts/`
4. `OPENCODE_CONFIG` env var is set to point at this room-specific config

This means:
- No global MCP registry polluting all agents
- Each room's MCP config is independently inspectable
- A room can be debugged by examining exactly which tools were available

## MCP Configuration Files

| File | Purpose |
|------|---------|
| `.agents/mcp/mcp-builtin.json` | Ships with OSTwin (channel, warroom, memory, etc.) |
| `.agents/mcp/mcp-config.json` | Production config with vault references for secrets |
| `.agents/mcp/mcp-catalog.json` | Installable extension catalog |
| `~/.ostwin/.agents/mcp/config.json` | User-level overrides (highest priority) |

## Vault-Based Secret Resolution

MCP configs can reference secrets via `${vault:server/key}` syntax:

```json
{
  "github": {
    "env": {
      "GITHUB_TOKEN": "${vault:github/token}"
    }
  }
}
```

The `ConfigResolver` class (`.agents/mcp/config_resolver.py`) recursively walks
the config, resolves vault references, and outputs clean configs for the agent.

## MCP Audit Logging

Every MCP tool call is logged to `{room_dir}/mcp-tools.jsonl` via
`mcp-proxy.py`:

```json
{
  "ts": "2026-04-01T10:05:00Z",
  "server": "github",
  "tool": "list_issues",
  "args": {},
  "elapsed_ms": 1234.5,
  "ok": true,
  "result": "...(truncated to 4096 chars)..."
}
```

This enables:
- **Forensics**: Exact tool calls, order, arguments
- **Performance profiling**: Find slow MCP servers
- **Cost attribution**: Count calls per role per task

## Built-in MCP Servers

| Server | Purpose |
|--------|---------|
| `channel-server.py` | Post/read messages to war-room channels |
| `warroom-server.py` | Room status updates, artifact listing, progress reporting |
| `memory-server.py` | Publish/query/search the shared memory ledger |
| `mcp-proxy.py` | Audit proxy that wraps any MCP server with logging |

## Token Budget Impact

| Configuration | Approx. Token Cost |
|---------------|-------------------|
| Full MCP (5 servers, ~100 tools) | 8,000-12,000 tokens in system prompt |
| No MCP (`no_mcp: true`) | 0 tokens for tools |
| Savings per architect invocation | 8,000-12,000 tokens |

For a plan with 10 epics, each requiring 3 architect invocations, that is
240,000-360,000 tokens saved -- just from the tool catalog.

## Future Direction

The current per-role MCP control is binary (all-or-nothing). The architecture
supports but does not yet implement per-server allowlists:

```json
{
  "qa": {
    "mcp_allowed_servers": ["github", "memory", "channel", "warroom"]
  }
}
```

The infrastructure for this (per-room `opencode.json` generation, config
filtering) is already in place.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/roles/_base/Invoke-Agent.ps1` | MCP config resolution and `no_mcp` gating |
| `.agents/mcp/mcp-proxy.py` | Audit proxy with JSONL logging |
| `.agents/mcp/config_resolver.py` | 4-tier config resolution, vault secret expansion |
| `.agents/mcp/memory-server.py` | Memory MCP server |
| `.agents/mcp/channel-server.py` | Channel MCP server |
| `.agents/mcp/warroom-server.py` | War-room MCP server |
| `.agents/mcp/mcp-builtin.json` | Built-in server definitions |
| `.agents/mcp/mcp-config.json` | Production MCP config |
| `dashboard/routes/mcp.py` | REST API for MCP management |
