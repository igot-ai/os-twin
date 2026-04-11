---
title: CLI Commands
description: Complete reference for the OSTwin CLI and utility shell scripts.
sidebar:
  order: 1
---

OSTwin provides the `ostwin` CLI plus a set of shell scripts in `.agents/` for lifecycle management.

## ostwin CLI

The main binary lives at `.agents/bin/ostwin` and delegates to Python subcommands.

### ostwin run

Start a plan execution. This is the primary entry point.

```bash
ostwin run PLAN.md
ostwin run PLAN.md --max-rooms 4
ostwin run PLAN.md --dry-run
```

| Flag | Default | Description |
|------|---------|-------------|
| `--max-rooms` | `50` | Max concurrent war-rooms |
| `--dry-run` | `false` | Parse plan, build DAG, but do not execute |
| `--model` | config default | Override default model for all roles |
| `--timeout` | `2400` | Global timeout in seconds |

### ostwin status

Show the current state of all war-rooms.

```bash
ostwin status
ostwin status --room room-003
ostwin status --json
```

Reads `status`, `state_changed_at`, and `retries` from each room directory.

### ostwin chat

Interactive chat session with a specified role.

```bash
ostwin chat --role engineer
ostwin chat --role architect --model claude-opus-4-6
```

### ostwin skills

Manage skill discovery and installation.

```bash
ostwin skills list
ostwin skills search "web-research"
ostwin skills install <skill-name>
```

## Utility Shell Scripts

These scripts live under `.agents/` and handle system-level operations.

### run.sh

The primary orchestration entry point. Invoked by `ostwin run`.

```bash
.agents/run.sh PLAN.md
```

Execution chain:
1. Sources `.agents/config.sh` for environment
2. Validates the plan file exists
3. Calls the PowerShell manager loop (`Start-ManagerLoop.ps1`)
4. Monitors child processes

### install.sh

First-time setup. Creates directory structure, installs dependencies, and configures the environment.

```bash
.agents/install.sh
```

Actions performed:
- Creates `.agents/war-rooms/`, `roles/`, `skills/`, `logs/`, `memory/`
- Installs Python dependencies for MCP and dashboard
- Validates PowerShell 7+ is available
- Downloads community roles if `auto_discover` is enabled

### init.sh

Initializes a new project for OSTwin. Lighter than `install.sh` -- sets up config files without installing dependencies.

```bash
.agents/init.sh
```

### health.sh

Runs health checks against all running components.

```bash
.agents/health.sh
```

Checks:
- PowerShell engine process
- Dashboard API (FastAPI on port 8000)
- Dashboard frontend (Next.js on port 3000)
- Memory daemon (MCP server)
- Active war-room states

### dashboard.sh

Start or stop the dashboard stack.

```bash
.agents/dashboard.sh start
.agents/dashboard.sh stop
```

Manages both the FastAPI backend and Next.js frontend. Writes PID to `.agents/dashboard.pid`.

### logs.sh

Tail or search log files.

```bash
.agents/logs.sh tail
.agents/logs.sh tail --room room-003
.agents/logs.sh search "error"
```

### sync-skills.sh

Synchronize skills from ClawhHub or a Git repository.

```bash
.agents/sync-skills.sh
.agents/sync-skills.sh --source github
```

### uninstall.sh

Remove OSTwin from the project. Cleans up `.agents/` artifacts but preserves `config.json` by default.

```bash
.agents/uninstall.sh
.agents/uninstall.sh --purge   # removes config.json too
```

## Memory Scripts

Located under `.agents/memory/`:

| Script | Purpose |
|--------|---------|
| `start-memory-daemon.sh` | Launch the MCP memory server |
| `switch-memory-transport.sh` | Toggle between stdio and SSE transport |

## Daemon Scripts

Located under `.agents/daemons/macos-host/`:

| Script | Purpose |
|--------|---------|
| `install.sh` | Register launchd daemon |
| `uninstall.sh` | Remove launchd daemon |
| `host-daemon.sh` | Main daemon process |
| `mcp-server.sh` | MCP server wrapper |

:::tip
Run `ostwin status --json` to get machine-readable output suitable for CI pipelines.
:::

:::note
All shell scripts assume `bash` and require PowerShell 7+ (`pwsh`) to be on the PATH.
:::
