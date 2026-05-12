---
title: "Pillar 3: MCP Isolation"
description: "Selective MCP server attachment eliminates thousands of wasted tokens per agent session."
sidebar:
  order: 3
  icon: rocket
---

OSTwin's third pillar solves a critical cost and performance problem: **not every agent needs every tool**. MCP (Model Context Protocol) servers expose tool definitions that consume prompt tokens whether or not the agent uses them. MCP Isolation ensures each agent only sees the tools it actually needs.

## The Token Cost Problem

A typical MCP server exposes 5-15 tool definitions. Each tool definition consumes 200-800 tokens in the system prompt. When an agent connects to multiple MCP servers:

- **3 MCP servers** with 10 tools each = ~8,000-12,000 tokens wasted
- **Per-session cost**: $0.02-0.05 in prompt tokens alone
- **Per-plan cost** (30 epics, 4 roles each): $2.40-6.00 in pure overhead

For a QA agent that only reads code and posts verdicts, connecting Unity MCP servers is pure waste. For an architect writing ADRs, filesystem tools are enough.

:::caution[Hidden Cost Multiplier]
Token waste compounds across every message in a conversation. A 20-turn agent session with 10K tokens of unnecessary tool definitions wastes **200K tokens** -- equivalent to reading a 500-page book of irrelevant content.
:::

## The no_mcp Flag

The simplest isolation mechanism is a binary flag in `role.json`:

```json
{
  "name": "architect",
  "no_mcp": true
}
```

When `no_mcp` is `true`, the agent launches with **zero MCP servers**. It can still read files, write code, and use bash -- but through the LLM client's built-in tools, not MCP.

### Resolution Chain

The `no_mcp` flag is resolved through three levels:

1. **Room config** (`config.json`) -- highest priority, per-room override
2. **Role config** (`role.json`) -- role-level default
3. **System default** -- `false` (MCP enabled)

## MCP Config Files

| File | Location | Purpose |
|------|----------|---------|
| `mcp.json` | `.agents/war-rooms/{room}/` | Room-specific MCP servers |
| `mcp.json` | `.agents/plans/{plan}/` | Plan-wide MCP servers |
| `mcp.json` | `.agents/` | Project-level defaults |
| `mcp.json` | `~/.agents/` | User-global preferences |

Each file follows the standard MCP configuration format:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", ".agents/mcp/memory-core.py", "--room", "${room_dir}"],
      "env": {
        "API_KEY": "${vault:memory/api_key}"
      }
    }
  }
}
```

## Vault-Based Secrets

MCP configs support secret references using the `${vault:path}` syntax:

```
${vault:server/key}     → resolves from .agents/vault.json
${vault:openai/api_key} → resolves the OpenAI key
${room_dir}             → expands to the current war-room path
${plan_dir}             → expands to the current plan directory
```

:::note[Security]
The vault file (`.agents/vault.json`) is gitignored by default. Secrets never appear in MCP configs committed to version control. The resolution happens at agent invocation time inside `roles/_base/Invoke-Agent.ps1`.
:::

## Audit Logging

Every MCP tool call is logged to `mcp-tools.jsonl` in the war-room directory:

```jsonl
{"ts":"2025-01-15T10:30:00Z","server":"memory","tool":"publish","duration_ms":45,"status":"ok"}
{"ts":"2025-01-15T10:30:02Z","server":"memory","tool":"query","duration_ms":120,"status":"ok"}
{"ts":"2025-01-15T10:30:05Z","server":"warroom","tool":"post_message","duration_ms":30,"status":"error","error":"channel locked"}
```

This audit trail enables:

- **Cost attribution** per server and per tool
- **Performance profiling** to identify slow MCP servers
- **Error tracking** for reliability monitoring
- **Compliance auditing** for regulated environments

## Built-in MCP Servers

OSTwin ships with four Python-based MCP servers:

| Server | Purpose | Key Tools |
|--------|---------|-----------|
| `.agents/mcp/memory-core.py` | Shared memory ledger | `publish`, `query`, `search`, `get_context` |
| `.agents/mcp/warroom-server.py` | War-room coordination | `post_message`, `read_messages`, `update_status`, `report_progress` |
| `.agents/dashboard.ps1` | Dashboard API bridge | `get_plan_status`, `get_room_state`, `search` |
| `.agents/mcp/global-knowledge-server.py` | Skill discovery | `search_skills`, `install_skill`, `list_installed` |

Each server is a standalone Python process launched via `python script` with room-specific arguments.

## Token Budget Impact

The savings from MCP Isolation are substantial at scale:

| Scenario | Without Isolation | With Isolation | Savings |
|----------|-------------------|----------------|---------|
| QA agent (reads only) | 12K tool tokens | 0 tokens | 12K/session |
| Architect (no tools) | 12K tool tokens | 0 tokens | 12K/session |
| Engineer (memory + warroom) | 12K tool tokens | 4K tokens | 8K/session |
| **10 epics, 4 roles each** | **480K tokens** | **120K-240K tokens** | **240K-360K saved** |

:::tip[Cost at Scale]
For a 30-epic plan with 4 roles per epic, MCP Isolation saves approximately **$3-8 in prompt token costs**. More importantly, it reduces latency -- smaller prompts mean faster first-token times.
:::

## Future Direction: Per-Server Allowlists

The current isolation model is binary (all servers or none, per config). A planned enhancement introduces **per-server tool allowlists**:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", ".agents/mcp/memory-core.py"],
      "allow_tools": ["query", "search"],
      "deny_tools": ["publish"]
    }
  }
}
```

This will allow a QA agent to read from the memory ledger without being able to write to it, further tightening the principle of least privilege.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/mcp/config_resolver.py` | 4-tier MCP config merge |
| `.agents/roles/_base/Invoke-Agent.ps1` | no_mcp flag handling |
| `.agents/memory/` | Shared memory MCP server |
| `.agents/mcp/warroom-server.py` | War-room coordination server |
| `.agents/vault.json` | Secret storage (gitignored) |
