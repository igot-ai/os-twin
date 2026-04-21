# Update OS Twin (Ostwin) -- Multi-Agent War-Room Orchestration

An operating system for AI agents where an **Engineering Manager** orchestrates parallel **War-Rooms**, each containing an **Engineer** and a **QA Engineer** collaborating through shared JSONL channels until all tasks pass quality gates.

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

---

## Prerequisites

| Dependency       | Min Version | Notes                                           |
|------------------|-------------|-------------------------------------------------|
| Python           | 3.10+       | 3.12 recommended; auto-installed if missing     |
| PowerShell       | 7+          | `pwsh`; auto-installed if missing               |
| Node.js          | 18+         | For dashboard UI; auto-installed if missing     |
| opencode         | latest      | Agent execution engine; auto-installed           |
| uv               | latest      | Fast Python package manager (optional, recommended) |
| AI Provider Key  | --          | At least one: Google, OpenAI, Anthropic, etc.   |

The installer will attempt to install all missing dependencies automatically.

---

## Installation

### macOS

**Supported:** macOS (arm64 / Apple Silicon, x86_64 / Intel)

```bash
# Clone the repository
git clone https://github.com/AnomalyCo/agent-os.git
cd agent-os

# Run the installer (interactive -- prompts before each step)
.agents/install.sh

# Or non-interactive (auto-approve all)
.agents/install.sh --yes
```

The installer uses **Homebrew** as the primary package manager. If Homebrew is not installed, it will be installed automatically.

**What happens:**
1. Detects macOS platform and architecture
2. Installs `uv`, Python 3.12, PowerShell 7+, Node.js, `opencode`, and Pester
3. Copies framework files to `~/.ostwin/`
4. Creates a Python virtual environment at `~/.ostwin/.venv/`
5. Installs all Python dependencies (MCP servers, dashboard API)
6. Creates `~/.ostwin/.env` with API key placeholders
7. Patches MCP config and syncs agent definitions to `~/.config/opencode/agents/`
8. Builds the dashboard frontend
9. Adds `ostwin` to your shell PATH (`~/.zshrc` or `~/.bashrc`)
10. Starts the dashboard on port 9000

After installation, open a new terminal (or run `source ~/.zshrc`) and use:

```bash
ostwin run plans/my-feature.md
ostwin status
ostwin --help
```

---

### Linux

**Supported distributions:**
- Ubuntu / Debian / Pop!_OS / Linux Mint / elementary OS (apt)
- Fedora / RHEL / CentOS / Rocky / AlmaLinux (dnf/yum)
- Arch / Manjaro (pacman)
- openSUSE / SLES (zypper)

```bash
# Clone the repository
git clone https://github.com/AnomalyCo/agent-os.git
cd agent-os

# Run the installer
.agents/install.sh

# Or non-interactive
.agents/install.sh --yes
```

The installer auto-detects your Linux distribution and uses the appropriate package manager (`apt`, `dnf`, `yum`, `pacman`, or `zypper`).

PowerShell is installed via Microsoft APT/RPM repositories, or via `snap` as a fallback.

After installation:

```bash
source ~/.bashrc   # or open a new terminal
ostwin run plans/my-feature.md
```

---

### Windows

**Supported:** Windows 10 (build 10240+), Windows 11  
**No dependency on WSL, Cygwin, or Git Bash** -- fully native PowerShell.

#### Option 1: PowerShell Installer (Recommended)

Open **PowerShell 7+** (or Windows PowerShell 5.1) as Administrator:

```powershell
# Clone the repository
git clone https://github.com/AnomalyCo/agent-os.git
cd agent-os

# Run the installer (interactive)
.agents\install.ps1

# Or non-interactive
.agents\install.ps1 -Yes
```

The installer auto-detects available package managers and uses them in this priority order:
1. **winget** (built-in on Windows 11, available on Windows 10)
2. **Chocolatey** (`choco`)
3. **Scoop**
4. **Direct download** (fallback -- downloads installers from official sources)

**What gets installed:**
- Python 3.12 (via winget/choco/scoop or python.org MSI)
- PowerShell 7+ (via winget/choco or GitHub MSI)
- uv (fast Python package manager)
- Node.js (for dashboard UI)
- opencode (agent execution engine)
- Pester 5+ (PowerShell test framework)
- MCP dependencies (fastapi, uvicorn, etc.)

**What happens:**
1. Detects Windows version and architecture
2. Installs all missing dependencies
3. Copies framework files to `%USERPROFILE%\.ostwin\`
4. Creates a Python venv at `%USERPROFILE%\.ostwin\.venv\`
5. Installs Python dependencies
6. Creates `%USERPROFILE%\.ostwin\.env` for API keys
7. Patches MCP config and syncs agents
8. Builds the dashboard frontend
9. Adds `ostwin` to your User PATH
10. Starts the dashboard

#### Option 2: Using ostwin from CMD

After installation, a `ostwin.cmd` wrapper is available so you can use `ostwin` from `cmd.exe`:

```cmd
ostwin run plans\my-feature.md
ostwin status --watch
ostwin --help
```

This wrapper auto-detects `pwsh` (PowerShell 7+) and falls back to `powershell.exe` (5.1).

#### Option 3: Run Directly (No Install)

If you prefer not to run the installer:

```powershell
.agents\bin\ostwin.ps1 run plans\my-feature.md
```

**Manual prerequisites:** `pwsh`, `python3`, `opencode` must be installed and on PATH.  
Put API keys in `.agents\.env` (project-local) instead of `~\.ostwin\.env`.

#### Windows Installer Options

```powershell
# Full install with all defaults
.agents\install.ps1 -Yes

# Custom install directory
.agents\install.ps1 -Dir C:\MyOstwin

# Custom dashboard port
.agents\install.ps1 -Port 8080

# Dashboard-only (no agent tooling)
.agents\install.ps1 -DashboardOnly

# Skip optional components (Pester, etc.)
.agents\install.ps1 -SkipOptional

# Include channel connectors (Telegram + Discord + Slack)
.agents\install.ps1 -Channel
```

---

## Installer Options (macOS / Linux)

```bash
.agents/install.sh               # Interactive mode
.agents/install.sh --yes         # Non-interactive (auto-approve)
.agents/install.sh --dir /path   # Custom install location (default: ~/.ostwin)
.agents/install.sh --channel     # Also install & start channel connectors
.agents/install.sh --dashboard-only  # Dashboard API + frontend only
.agents/install.sh --help        # Show help
```

---

## Post-Install: API Keys

After installation, edit `~/.ostwin/.env` (or `%USERPROFILE%\.ostwin\.env` on Windows) to add your AI provider key(s):

```bash
# Set at least one:
GOOGLE_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
# OPENROUTER_API_KEY=
# AZURE_OPENAI_API_KEY=
```

The installer will prompt you to configure a provider during setup (interactive mode only).

---

## Quick Start

```bash
# Run a plan
ostwin run plans/my-feature.md

# Run without installing (from source)
.agents/bin/ostwin run plans/my-feature.md    # macOS/Linux
.agents\bin\ostwin.ps1 run plans\my-feature.md  # Windows

# Check status
ostwin status
ostwin status --watch

# View logs
ostwin logs room-001 --follow

# Stop running agents
ostwin stop

# Launch the web dashboard
ostwin dashboard
```

---

## Dev Mode

**Prerequisites:** Python 3.10+, Node.js 18+, pnpm

```bash
# Dashboard backend (FastAPI)
cd dashboard && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Dashboard frontend
cd dashboard/fe && pnpm install

# MCP servers (memory, channel, warroom)
cd .agents && python3 -m venv .venv && source .venv/bin/activate && pip install "mcp[cli]" fastmcp
```

```bash
source dashboard/.venv/bin/activate && python dashboard/api.py   # Backend  -> :9000
cd dashboard/fe && pnpm dev                                      # Frontend -> :3000
.agents/run.sh path/to/plan.md                                   # Launch a plan
```

Custom ports: `python dashboard/api.py --port 9069` + `OSTWIN_BACKEND_URL=http://localhost:9069 pnpm dev -p 3069`

---

## Data Layout

**Project-local** (follows `working_dir` in plan):

| Location | What |
|---|---|
| `<project>/.war-rooms/room-*/` | War-room state: `channel.jsonl`, `config.json`, `artifacts/` |
| `.agents/memory/` | Shared cross-room memory: `ledger.jsonl`, `index.json` |

**Global** (fixed at `~/.ostwin/` or `%USERPROFILE%\.ostwin\`):

| Location | What |
|---|---|
| `~/.ostwin/plans/` | Plan files + `.meta.json` |
| `~/.ostwin/.zvec/` | Vector store (embeddings cache) |
| `~/.ostwin/.env` | API keys & secrets |
| `~/.ostwin/dashboard/` | Dashboard server + logs |

Runtime writes (nothing touches `~/.ostwin/` in no-install mode):
- `.war-rooms/` -- room state, artifacts, channels (gitignored)
- `.agents/manager.pid` -- manager process PID (gitignored)
- `.agents/logs/` -- `ostwin.log`, `ostwin.jsonl` (gitignored)

---

## Memory (Cross-Room Shared Context)

Agents share context via MCP memory server -- `publish`/`query`/`search` tools backed by an append-only JSONL ledger.

```bash
# macOS / Linux
.agents/memory-monitor.sh status   # Check ON/OFF + ledger stats
.agents/memory-monitor.sh watch    # Live stream new entries

# Windows (PowerShell)
.agents\memory-monitor.ps1 status
```

---

## Troubleshooting

### macOS / Linux

| Problem | Fix |
|---|---|
| `ostwin: command not found` | Run `source ~/.zshrc` (or `~/.bashrc`) or open a new terminal |
| `opencode not found` | Run `brew install anomalyco/tap/opencode` or `curl -fsSL https://opencode.ai/install \| bash` |
| Python version too old | Install 3.12: `uv python install 3.12` or `brew install python@3.12` |
| Dashboard not starting | Check port 9000 is free: `lsof -i :9000` |

### Windows

| Problem | Fix |
|---|---|
| `ostwin` not recognized in CMD | Restart terminal, or run `refreshenv` (Chocolatey), or use full path `.agents\bin\ostwin.cmd` |
| Execution policy error | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass` in PowerShell |
| `pwsh` not found | Install PowerShell 7+: `winget install Microsoft.PowerShell` or download from [aka.ms/install-powershell](https://aka.ms/install-powershell) |
| Python not found after install | Restart terminal to pick up PATH changes |
| Permission denied (symlinks) | Enable Developer Mode in Settings > Privacy & Security > For developers |
