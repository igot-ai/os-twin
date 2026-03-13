# deepagents CLI Reference

> Version: v0.0.31
> Docs: https://docs.langchain.com/oss/python/deepagents/cli
> Install: `pip install deepagents-cli`

## Modes

### Interactive (default)
```bash
deepagents                        # Start interactive thread
deepagents -a coder               # Use specific agent
deepagents -r                     # Resume most recent thread
deepagents -r <ID>                # Resume specific thread
```

### Non-Interactive
```bash
deepagents -n "Summarize README.md"                          # Single task, exit
deepagents -n "Fix tests" --shell-allow-list all             # With shell access
deepagents -n "List files" --shell-allow-list recommended    # Safe commands
deepagents -n "Search logs" --shell-allow-list ls,cat,grep   # Custom allowlist
deepagents -n "Analyze code" -q                              # Quiet/clean output for piping
```

### ACP Server
```bash
deepagents --acp                  # Run as ACP server over stdio
```

## Full Options Reference

| Flag | Description |
|------|-------------|
| `-r, --resume [ID]` | Resume thread: `-r` for most recent, `-r ID` for specific |
| `-a, --agent NAME` | Agent to use (e.g., `coder`, `researcher`) |
| `-M, --model MODEL` | Model to use (e.g., `gemini-3.1-pro-preview`) |
| `--model-params JSON` | Extra model kwargs (e.g., `'{"temperature": 0.7}'`) |
| `--profile-override JSON` | Override model profile fields as JSON |
| `-m, --message TEXT` | Initial prompt to auto-submit on start |
| `--auto-approve` | Auto-approve all tool calls (toggle: Shift+Tab) |
| `--ask-user` | Enable `ask_user` interactive questions |
| `--sandbox TYPE` | Remote sandbox for execution |
| `--sandbox-id ID` | Reuse existing sandbox (skips creation/cleanup) |
| `--sandbox-setup PATH` | Setup script to run in sandbox after creation |
| `--mcp-config PATH` | Load MCP tools from config file (merged on top of auto-discovered configs) |
| `--no-mcp` | Disable all MCP tool loading |
| `--trust-project-mcp` | Trust project MCP configs (skip approval prompt) |
| `-n, --non-interactive MSG` | Run a single task and exit |
| `-q, --quiet` | Clean output for piping (needs `-n`) |
| `--no-stream` | Buffer full response instead of streaming |
| `--shell-allow-list CMDS` | Comma-separated commands, `recommended`, or `all` |
| `--default-model [MODEL]` | Set, show, or manage the default model |
| `--clear-default-model` | Clear the default model |
| `-v, --version` | Show deepagents CLI and SDK versions |
| `-h, --help` | Show help message and exit |

## Subcommands

```bash
deepagents list                                # List all available agents
deepagents reset --agent AGENT [--target SRC]  # Reset an agent's prompt
deepagents skills <list|create|info|delete>    # Manage agent skills
deepagents threads <list|delete>               # Manage conversation threads
```

## Shell Access Levels

| Level | Description |
|-------|-------------|
| `all` | Unrestricted shell access — full read/write |
| `recommended` | Curated set of safe commands |
| Custom list | Comma-separated: `ls,cat,grep,find,head,tree,wc,file` |

## Usage in Ostwin

### Engineer Role (task execution — full access)
```bash
$ENGINEER_CLI -n "$PROMPT" \
    --auto-approve \
    --shell-allow-list all \
    --model "$MODEL"
```
Source: `.agents/roles/engineer/run.sh`

### Plan Generation (read-only analysis)
```bash
$ENGINEER_CLI -n "$PROMPT" \
    --auto-approve \
    --shell-allow-list "ls,find,cat,head,tree,wc,file" \
    --model "$MODEL" \
    -q
```
Source: `.agents/plan.sh`

### Release Signoff (limited access)
```bash
$ENGINEER_CLI -n "$PROMPT" \
    --auto-approve \
    --shell-allow-list recommended \
    --model "$MODEL"
```
Source: `.agents/release/signoff.sh`
