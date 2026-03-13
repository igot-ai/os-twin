# Agent OS — Core Features Vision & Architecture Plan (v2)

## Executive Summary

Agent OS (Ostwin) is an **operating system for AI agent teams** that orchestrates virtual engineering organizations through **war-rooms**, JSONL communication channels, and the **deepagents** CLI. This plan proposes the next-generation architecture to evolve from the current 3-role prototype into a **scalable, observable, quality-gated platform** capable of managing hundreds of concurrent virtual engineers.

> [!IMPORTANT]
> **Three key architectural decisions in v2:**
> 1. **PowerShell migration** — all [.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/run.sh) scripts convert to `.ps1` with full Pester unit tests
> 2. **War-room-centric model** — agents run 24/7, continuously spawning war-rooms from a plan queue (no sprint boundaries)
> 3. **Goal-driven config** — every war-room carries a [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) with explicit goal definitions; final reports are cross-checked against those goals

---

## Current State (v0.1.0)

| Component | Status | Script Count | Notes |
|-----------|--------|-------------|-------|
| War-room orchestration | ✅ Working | [loop.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/roles/manager/loop.sh) (404 lines) | State machine, retry, timeout, deadlock detection |
| Plan creation (AI-assisted) | ✅ Working | [plan.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/plan.sh) (760 lines) | Interactive TUI + AI ideation + feedback loop |
| Roles: manager, engineer, qa | ✅ Working | 3 [run.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/run.sh) + 3 [ROLE.md](file:///Users/paulaan/PycharmProjects/agent-os/.agents/roles/qa/ROLE.md) | Each wraps deepagents CLI |
| JSONL channels | ✅ Working | 3 scripts | [post.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/channel/post.sh), [read.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/channel/read.sh), [wait-for.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/channel/wait-for.sh) |
| MCP servers | ✅ Working | 2 Python | [channel-server.py](file:///Users/paulaan/PycharmProjects/agent-os/.agents/mcp/channel-server.py), [warroom-server.py](file:///Users/paulaan/PycharmProjects/agent-os/.agents/mcp/warroom-server.py) |
| Web dashboard | ✅ Working | [api.py](file:///Users/paulaan/PycharmProjects/agent-os/test_api.py) (25KB) | FastAPI — basic monitoring |
| Tests | ✅ Working | 9 bash tests | e2e, channel, manager, cli, locking |
| CLI ([ostwin](file:///Users/paulaan/PycharmProjects/agent-os/.agents/bin/ostwin)) | ✅ Working | [bin/ostwin](file:///Users/paulaan/PycharmProjects/agent-os/.agents/bin/ostwin) | Entry point |

---

## Vision: Core Feature Modules

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT OS v1.0 PLATFORM                         │
├─────────┬──────────┬───────────┬──────────┬──────────┬────────────────┤
│  ROLES  │ PLANNING │ DASHBOARD │ OBSERVE  │ QUALITY  │ HUMAN-IN-LOOP │
│ Engine  │ & Queue  │ & Control │ Stack    │ Engine   │ Framework     │
├─────────┴──────────┴───────────┴──────────┴──────────┴────────────────┤
│                       CORE ORCHESTRATION LAYER                         │
│       War-Rooms · Channels · State Machine · Plan Queue · Scheduler   │
├───────────────────────────────────────────────────────────────────────┤
│                    POWERSHELL + PESTER TEST LAYER                      │
│         All modules = .ps1 scripts + .Tests.ps1 unit tests            │
├───────────────────────────────────────────────────────────────────────┤
│                       AGENT RUNTIME (deepagents)                       │
│         Sub-agents · Planning · Filesystem · Shell · Context          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Cross-Cutting: PowerShell Migration & Test Strategy

> **Goal**: Every feature is a PowerShell module with matching Pester unit tests, ensuring correctness, extensibility, and cross-platform support.

### Migration Plan

```
.agents/
├── lib/
│   ├── Log.psm1              # Structured logging module
│   ├── Log.Tests.ps1         # Pester tests for logging
│   ├── Utils.psm1            # Shared utilities
│   ├── Utils.Tests.ps1       # Pester tests for utilities
│   ├── Config.psm1           # Config loading & validation
│   └── Config.Tests.ps1
├── channel/
│   ├── Post-Message.ps1      # Post message to channel
│   ├── Post-Message.Tests.ps1
│   ├── Read-Messages.ps1     # Read/filter channel messages
│   ├── Read-Messages.Tests.ps1
│   ├── Wait-ForMessage.ps1   # Block until message type appears
│   └── Wait-ForMessage.Tests.ps1
├── war-rooms/
│   ├── New-WarRoom.ps1       # Create a new war-room
│   ├── New-WarRoom.Tests.ps1
│   ├── Get-WarRoomStatus.ps1 # Show status of all rooms
│   ├── Get-WarRoomStatus.Tests.ps1
│   ├── Remove-WarRoom.ps1    # Teardown a war-room
│   └── Remove-WarRoom.Tests.ps1
├── roles/
│   ├── _base/
│   │   ├── Invoke-Agent.ps1      # Universal deepagents launcher
│   │   └── Invoke-Agent.Tests.ps1
│   ├── engineer/
│   │   ├── Start-Engineer.ps1
│   │   └── Start-Engineer.Tests.ps1
│   ├── qa/
│   │   ├── Start-QA.ps1
│   │   └── Start-QA.Tests.ps1
│   └── manager/
│       ├── Start-ManagerLoop.ps1
│       └── Start-ManagerLoop.Tests.ps1
├── plan/
│   ├── New-Plan.ps1          # AI-assisted plan creation
│   ├── New-Plan.Tests.ps1
│   ├── Start-Plan.ps1        # Parse plan → spawn war-rooms
│   └── Start-Plan.Tests.ps1
└── run.ps1                   # Entry point
```

### Testing Standards

```powershell
# Example: Post-Message.Tests.ps1
Describe "Post-Message" {
    BeforeAll {
        . "$PSScriptRoot/Post-Message.ps1"
        $TestRoom = New-Item -ItemType Directory -Path (Join-Path $TestDrive "room-test")
    }

    It "creates channel.jsonl if it doesn't exist" {
        Post-Message -RoomDir $TestRoom -From "manager" -To "engineer" `
                     -Type "task" -Ref "TASK-001" -Body "Implement feature"
        Test-Path (Join-Path $TestRoom "channel.jsonl") | Should -BeTrue
    }

    It "writes valid JSON with required fields" {
        $messages = Get-Content (Join-Path $TestRoom "channel.jsonl") |
                    ForEach-Object { $_ | ConvertFrom-Json }
        $messages[0].from | Should -Be "manager"
        $messages[0].type | Should -Be "task"
        $messages[0].ts   | Should -Not -BeNullOrEmpty
    }

    It "rejects messages exceeding max size" {
        $bigBody = "x" * 100000
        { Post-Message -RoomDir $TestRoom -From "manager" -To "engineer" `
                       -Type "task" -Ref "TASK-002" -Body $bigBody } |
            Should -Throw "*exceeds max*"
    }
}
```

### Why PowerShell

| Concern | Bash | PowerShell |
|---------|------|------------|
| Structured data | Needs `jq` / `python -c` | Native objects, `ConvertFrom-Json` |
| Error handling | `set -e`, fragile traps | `try/catch/finally`, `$ErrorActionPreference` |
| Testing | No native framework | **Pester** — industry-standard, mocking, code coverage |
| Cross-platform | Unix only | Windows, macOS, Linux |
| Modularity | Source scripts, no namespace | Modules (`.psm1`), `Import-Module`, proper scoping |
| Parameter validation | Manual parsing | `[CmdletBinding()]`, `[ValidateNotNull()]`, typed params |
| JSON handling | External tools | Built-in `ConvertTo-Json` / `ConvertFrom-Json` |

---

## Module 1: Extensible Role Engine

> **Goal**: Any role can be defined declaratively and plugged into the system with its own context, skills, and capabilities.

### Proposed Structure

```
roles/
├── registry.json             # Role catalog with capabilities
├── _base/
│   ├── Invoke-Agent.ps1      # Universal deepagents launcher
│   ├── Invoke-Agent.Tests.ps1
│   └── ROLE.template.md      # Base role template
├── engineer/
│   ├── role.yaml             # Declarative role config
│   ├── ROLE.md               # System prompt
│   ├── Start-Engineer.ps1    # Role launcher
│   ├── Start-Engineer.Tests.ps1
│   ├── skills/               # Role-specific skills
│   │   ├── code-generation.md
│   │   ├── debugging.md
│   │   └── refactoring.md
│   └── context/              # Default context injected at spawn
│       ├── project-conventions.md
│       └── tech-stack.md
├── qa/
│   ├── role.yaml
│   ├── ROLE.md
│   ├── Start-QA.ps1
│   ├── Start-QA.Tests.ps1
│   ├── skills/
│   │   ├── test-writing.md
│   │   ├── security-review.md
│   │   └── review-checklist.md
│   └── context/
├── architect/                # [NEW]
├── devops/                   # [NEW]
├── tech-writer/              # [NEW]
├── security/                 # [NEW]
└── product-owner/            # [NEW]
```

#### `role.yaml` — Declarative Role Definition

```yaml
name: engineer
display_name: "Software Engineer"
version: "1.0"

# Runtime
cli: deepagents
model: gemini-3-flash-preview
timeout_seconds: 600
auto_approve: true
max_prompt_bytes: 102400

# Skills — composable abilities loaded into system prompt
skills:
  - code-generation
  - debugging
  - unit-testing

# Context — project-specific files injected at spawn
context_files:
  - project-conventions.md
  - tech-stack.md
  - architecture-overview.md

# Capabilities — fine-grained permissions
capabilities:
  read_files: true
  write_files: true
  execute_shell: true
  spawn_subagents: true
  modify_tests: true
  delete_files: false       # Engineers can't delete — must be explicit

# Communication contract
messages:
  receives: [task, fix, review-request]
  sends: [done, progress, question, error]

# Quality expectations
quality_gates:
  pre_submit:               # Gates the engineer must pass before posting "done"
    - tests_pass
    - no_lint_errors
    - code_compiles
```

### `Invoke-Agent.ps1` — Universal Agent Launcher

```powershell
function Invoke-Agent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RoomDir,

        [Parameter(Mandatory)]
        [string]$RoleName,

        [Parameter(Mandatory)]
        [string]$Prompt,

        [string]$Model,
        [int]$TimeoutSeconds = 600
    )

    # Load role config
    $roleConfig = Get-RoleConfig -RoleName $RoleName
    $model = if ($Model) { $Model } else { $roleConfig.model }

    # Build context from role skills + context files
    $systemPrompt = Build-SystemPrompt -RoleName $RoleName -RoleConfig $roleConfig

    # Inject war-room specific context
    $warRoomConfig = Get-Content (Join-Path $RoomDir "config.json") | ConvertFrom-Json
    $systemPrompt += "`n`n## War-Room Goals`n$($warRoomConfig.goals | ConvertTo-Json)"

    # Launch deepagents with role-specific settings
    $agentArgs = @(
        "-n", "`"$systemPrompt`n`n$Prompt`""
        "--model", $model
        "--auto-approve"
        "-q"
    )

    if ($roleConfig.capabilities.execute_shell) {
        $agentArgs += @("--shell-allow-list", "all")
    }

    # Execute with timeout
    $process = Start-Process -FilePath $roleConfig.cli -ArgumentList $agentArgs `
                             -WorkingDirectory $warRoomConfig.working_dir `
                             -PassThru -NoNewWindow

    # Track PID
    $process.Id | Out-File (Join-Path $RoomDir "pids/$RoleName.pid")

    # Wait with timeout
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill()
        throw "Agent $RoleName timed out after ${TimeoutSeconds}s"
    }

    return $process.ExitCode
}
```

### Key Features
- **Role Registry** (`registry.json`): Discover/list all available roles, their capabilities, and health
- **Skill Mounting**: Skills are composable markdown files loaded into the system prompt at spawn time — mix and match per project
- **Context Injection**: Project-specific context files (conventions, architecture, tech stack) injected so every agent understands the codebase
- **Capability Permissions**: Fine-grained control — QA gets read-only access, engineer gets full access, architect can read but not modify tests
- **Hot-reload**: Change `role.yaml` → next war-room spawn picks up the new config without restart

---

## Module 2: War-Room-Centric Planning Engine

> **Goal**: Agents run 24/7. Plans are queued. War-rooms are continuously spawned to process the queue. Every war-room has a [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) with explicit goals, and final reports are cross-checked against those goals.

### Key Design Principle

> **No sprints. No time-boxes.** Agents don't sleep, don't go home, don't take weekends. The system is a **continuous execution engine** — plans enter a queue, war-rooms are opened to process them, and new war-rooms open as capacity allows. The only boundaries are plans and their goals.

### Architecture

```
plans/
├── PLAN.schema.yaml          # Plan validation schema
├── templates/
│   ├── feature.md            # Feature-scoped plan
│   ├── release.md            # Release-scoped plan (multiple epics)
│   └── hotfix.md             # Single-fix plan
├── queue/                    # ★ Plan queue — FIFO with priority
│   ├── 001-auth-system.md    # Queued plan (priority by filename prefix)
│   ├── 002-dashboard-v2.md
│   └── 003-api-refactor.md
├── active/                   # Currently executing plans
│   └── 001-auth-system/
│       ├── plan.md           # Accepted plan
│       ├── queue-config.json # Queue metadata (priority, submitted_at, etc.)
│       └── war-rooms/        # War-rooms for this plan
│           ├── room-001/
│           ├── room-002/
│           └── room-003/
├── completed/                # Finished plans (archive)
│   └── 2026-03-12-auth-system/
│       ├── plan.md
│       ├── RELEASE.md
│       └── quality-report.md
└── failed/                   # Failed plans (for human review)
```

### War-Room [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) — The Goal Contract

Every war-room is born with a [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) that defines **exactly what success looks like**. Final reports are cross-checked against these goals.

```json
{
  "room_id": "room-001",
  "task_ref": "EPIC-001",
  "plan_id": "001-auth-system",
  "created_at": "2026-03-13T01:30:00Z",
  "working_dir": "/path/to/project",

  "assignment": {
    "title": "User Authentication System",
    "description": "Implement JWT-based authentication with login, register, and session management",
    "assigned_role": "engineer",
    "type": "epic"
  },

  "goals": {
    "definition_of_done": [
      "JWT token generation and validation working",
      "Login endpoint returns valid token on correct credentials",
      "Register endpoint creates user and returns token",
      "Session middleware rejects expired/invalid tokens",
      "All endpoints have unit tests with >80% coverage",
      "No hardcoded secrets in codebase"
    ],
    "acceptance_criteria": [
      "POST /auth/login returns 200 with token for valid credentials",
      "POST /auth/login returns 401 for invalid credentials",
      "POST /auth/register creates user in database",
      "GET /protected returns 401 without token",
      "GET /protected returns 200 with valid token",
      "Token expires after configured TTL"
    ],
    "quality_requirements": {
      "test_coverage_min": 80,
      "lint_clean": true,
      "security_scan_pass": true
    }
  },

  "constraints": {
    "max_retries": 3,
    "timeout_seconds": 900,
    "budget_tokens_max": 500000
  },

  "status": {
    "current": "engineering",
    "retries": 0,
    "started_at": "2026-03-13T01:31:00Z",
    "last_state_change": "2026-03-13T01:31:00Z"
  }
}
```

### Goal Cross-Check in Final Report

When a war-room reaches `passed`, the system generates a **Goal Verification Report** by cross-checking the engineer's output against [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) goals:

```powershell
function Test-WarRoomGoals {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RoomDir
    )

    $config = Get-Content (Join-Path $RoomDir "config.json") | ConvertFrom-Json
    $doneMessage = Read-Messages -RoomDir $RoomDir -Type "done" -Last 1
    $qaVerdict = Read-Messages -RoomDir $RoomDir -Type "pass" -Last 1

    $report = @{
        room_id    = $config.room_id
        task_ref   = $config.task_ref
        verified_at = (Get-Date -Format "o")
        goals      = @()
    }

    foreach ($goal in $config.goals.definition_of_done) {
        $report.goals += @{
            goal        = $goal
            status      = "pending_verification"
            evidence    = ""
        }
    }

    # Use deepagents to verify each goal against the actual output
    $verificationPrompt = @"
You are a Goal Verification Agent. Cross-check these goals against the evidence.

GOALS (Definition of Done):
$($config.goals.definition_of_done | ConvertTo-Json)

ENGINEER REPORT:
$($doneMessage.body)

QA VERDICT:
$($qaVerdict.body)

For each goal, output JSON: {"goal": "...", "status": "met|not_met|partial", "evidence": "..."}
"@

    # ... invoke deepagents for verification ...

    $report | ConvertTo-Json -Depth 10 |
        Out-File (Join-Path $RoomDir "goal-verification.json")

    return $report
}
```

#### Goal Verification Report (`goal-verification.json`)

```json
{
  "room_id": "room-001",
  "task_ref": "EPIC-001",
  "verified_at": "2026-03-13T02:15:00Z",
  "overall_status": "all_goals_met",
  "goals": [
    {
      "goal": "JWT token generation and validation working",
      "status": "met",
      "evidence": "auth/jwt.py implements generate_token() and validate_token(). Tests in tests/test_jwt.py pass."
    },
    {
      "goal": "All endpoints have unit tests with >80% coverage",
      "status": "met",
      "evidence": "Coverage report shows 87% coverage for auth/ module."
    },
    {
      "goal": "No hardcoded secrets in codebase",
      "status": "met",
      "evidence": "Security scan passed. All secrets loaded from environment variables."
    }
  ],
  "quality_checks": {
    "test_coverage": { "required": 80, "actual": 87, "passed": true },
    "lint_clean": { "passed": true },
    "security_scan": { "passed": true }
  }
}
```

### Plan Queue Processing

```
                          PLAN QUEUE (FIFO + priority)
                    ┌─────────────────────────────────────┐
                    │  priority:1  auth-system.md          │
                    │  priority:2  dashboard-v2.md         │
                    │  priority:3  api-refactor.md         │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │      PLAN SCHEDULER (24/7)          │
                    │                                      │
                    │  while (true) {                      │
                    │    if (active_rooms < max_rooms) {   │
                    │      plan = dequeue_next_plan()      │
                    │      parse_plan_into_war_rooms(plan) │
                    │      spawn_war_rooms()               │
                    │    }                                  │
                    │    poll_active_rooms()                │
                    │    archive_completed_plans()          │
                    │    sleep(poll_interval)               │
                    │  }                                    │
                    └─────────────────────────────────────┘
                         │              │             │
                    ┌────▼────┐  ┌─────▼─────┐  ┌───▼──────┐
                    │ room-001│  │  room-002  │  │ room-003 │
                    │ EPIC-001│  │  EPIC-002  │  │ EPIC-003 │
                    │ config: │  │  config:   │  │ config:  │
                    │ {goals} │  │  {goals}   │  │ {goals}  │
                    └─────────┘  └───────────┘  └──────────┘
```

### Key Features
- **Continuous Queue**: Plans dropped into `plans/queue/` are automatically picked up — no manual `ostwin plan start` needed
- **Priority Ordering**: Filename prefix (`001-`, `002-`) determines priority; critical plans jump the queue
- **War-Room Config Contract**: Every room's [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) carries the full goal definition — engineers know exactly what "done" means
- **Goal Cross-Check**: Automated verification that final reports match every goal in `definition_of_done`
- **Plan Archival**: Completed plans move to `completed/` with full history; failed plans go to `failed/` for human review
- **Backlog Rollover**: Unfinished tasks from a failed plan automatically re-queue at higher priority
- **Dependency Graph**: Tasks can declare `depends_on: [TASK-001]` — scheduler resolves ordering before spawning rooms

---

## Module 3: Real-Time Dashboard & Control Center

> **Goal**: A rich web dashboard to monitor, control, and interact with all war-rooms in real-time.

### Proposed Structure

```
dashboard/
├── api.py                    # FastAPI backend (enhanced)
├── ws.py                     # WebSocket handler for real-time updates
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── views/
    ├── plan-queue.html       # Plan queue + active plans
    ├── war-room-grid.html    # All rooms at a glance
    ├── war-room-detail.html  # Single room deep-dive
    ├── team-roster.html      # All roles + assignments + health
    ├── goal-tracker.html     # Goal completion across all rooms
    ├── log-viewer.html       # Structured log viewer with filters
    ├── timeline.html         # Gantt-style execution timeline
    └── metrics.html          # Quality & performance metrics
```

### Key Views

| View | Description |
|------|-------------|
| **Plan Queue** | Queued → Active → Completed plans; drag to re-prioritize |
| **War-Room Grid** | All rooms at a glance: status badge, progress bar, role assignment, goal completion % |
| **Room Detail** | Full channel view, goal checklist (✅/❌), audit log, file diff, retry history |
| **Team Roster** | All active roles, their current war-room, agent model, token usage |
| **Goal Tracker** | Cross-room view: which goals are met/unmet across the plan |
| **Execution Timeline** | Gantt chart with dependency arrows, time-per-state breakdown |
| **Quality Metrics** | Pass rate, retry rate, time-to-pass, cost trends, goal completion rate |
| **Control Panel** | Start/stop/pause rooms, force re-assign, override verdict, inject human feedback |

### Key Features
- **WebSocket real-time updates** — war-room state changes push instantly to all connected clients
- **Interactive controls** — start/stop/pause/re-assign/override from the browser
- **Multi-plan monitoring** — watch multiple active plans simultaneously
- **Goal tracking overlay** — see which `definition_of_done` items are verified per room
- **Dark mode** with glassmorphism aesthetics
- **Mobile-responsive** — check team status from phone
- **Export** — download quality reports, timeline data, and cost summaries as PDF/CSV

---

## Module 4: Observability Stack (Logging, Tracing, Metrics)

> **Goal**: Full observability into every agent action, decision, and handoff.

### Proposed Structure

```
observe/
├── Write-Log.ps1             # Enhanced structured logging
├── Write-Log.Tests.ps1
├── New-Trace.ps1             # Distributed tracing (trace-id per plan run)
├── New-Trace.Tests.ps1
├── Write-Metric.ps1          # Metrics collection
├── Write-Metric.Tests.ps1
├── exporters/
│   ├── Export-ToFile.ps1     # Local file export (default)
│   ├── Export-ToSqlite.ps1   # SQLite for queryable history
│   └── Export-ToOtel.ps1     # OpenTelemetry export
└── schemas/
    ├── log-event.json
    ├── trace-span.json
    └── metric-point.json
```

### Tracing Model

```
Plan Run (trace_id: "run-abc123", plan: "001-auth-system")
  └── Span: Manager Loop (span_id: "mgr-001")
        ├── Span: War-Room room-001 (span_id: "wr-001")
        │     ├── Span: Engineer Session (span_id: "eng-001")
        │     │     ├── Event: "prompt_sent" {tokens: 4200, model: "gemini-3-flash"}
        │     │     ├── Event: "tool_call"   {tool: "write_file", file: "api.py"}
        │     │     ├── Event: "tool_call"   {tool: "execute", cmd: "pytest"}
        │     │     └── Event: "completion"  {status: "done", duration_s: 45}
        │     ├── Span: Quality Gates (span_id: "gate-001")
        │     │     ├── Event: "lint_check"  {passed: true, warnings: 2}
        │     │     ├── Event: "test_suite"  {passed: 12, failed: 0}
        │     │     └── Event: "coverage"    {percent: 87}
        │     ├── Span: QA Session (span_id: "qa-001")
        │     │     ├── Event: "review_started"
        │     │     └── Event: "verdict"     {result: "pass"}
        │     └── Span: Goal Verification (span_id: "gv-001")
        │           └── Event: "goals_checked" {met: 6, total: 6}
        └── Span: War-Room room-002 ...
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `room_duration_seconds` | Histogram | Time from pending → passed per room |
| `retry_count_total` | Counter | Total retries across all rooms |
| `qa_pass_rate` | Gauge | % of rooms that pass on first review |
| `goal_completion_rate` | Gauge | % of goals met across plan |
| `agent_token_usage` | Counter | Token consumption per role per run |
| `cost_per_task_usd` | Counter | Estimated cost per war-room |
| `active_rooms` | Gauge | Currently active war-rooms |
| `plan_queue_depth` | Gauge | Plans waiting in queue |
| `time_to_first_pass` | Histogram | Time from engineer start to first QA pass |
| `plan_throughput` | Counter | Plans completed per day |

### Key Features
- **Trace correlation**: Every log line carries `trace_id`, `span_id`, `room_id`, `plan_id`
- **Cost tracking**: Token spend per role, per task, per plan; alert on budget exceeded
- **SQLite queryable**: `ostwin observe query "SELECT * FROM spans WHERE duration_s > 120"`
- **OpenTelemetry export**: Push to Jaeger, Grafana, Datadog
- **Replay**: Re-read any historical trace to debug what happened
- **Alerting**: Configurable thresholds (e.g., "alert if cost > $50 per plan")

---

## Module 5: Quality Engine

> **Goal**: Systematic quality control with automated gates, goal verification, benchmarks, and continuous improvement.

### Proposed Structure

```
quality/
├── gates/
│   ├── Invoke-LintGate.ps1          # Run linters
│   ├── Invoke-LintGate.Tests.ps1
│   ├── Invoke-TestGate.ps1          # Run project tests
│   ├── Invoke-TestGate.Tests.ps1
│   ├── Invoke-CoverageGate.ps1      # Check coverage thresholds
│   ├── Invoke-CoverageGate.Tests.ps1
│   ├── Invoke-SecurityGate.ps1      # Security scanning
│   ├── Invoke-SecurityGate.Tests.ps1
│   └── Invoke-CustomGate.ps1        # Project-specific gates
├── goals/
│   ├── Test-GoalCompletion.ps1      # Cross-check goals vs output
│   ├── Test-GoalCompletion.Tests.ps1
│   └── New-GoalReport.ps1           # Generate goal verification report
├── benchmarks/
│   ├── rubric.yaml                  # Scoring rubric
│   ├── Invoke-Benchmark.ps1         # Score agent output against rubric
│   └── history.json                 # Historical scores
├── feedback/
│   ├── Get-FeedbackPatterns.ps1     # Analyze recurring QA failures
│   └── Get-Recommendations.ps1     # Suggest prompt/skill improvements
└── reports/
    ├── New-QualityReport.ps1        # Generate quality summary
    └── templates/
        └── report.md
```

### Quality Gate Pipeline

```
Engineer Posts "done"
  │
  ├── Gate 1: Code Compiles/Parses      (auto — fast)
  ├── Gate 2: Lint Check                 (auto — configurable rules)
  ├── Gate 3: Test Suite                 (auto — runs project tests)
  ├── Gate 4: Coverage Threshold         (auto — from config.json goals)
  ├── Gate 5: Security Scan              (auto — SAST/dependency check)
  │
  ├── Gate 6: Goal Pre-Check             (auto — verify config.json goals)
  │           ↳ "Did the engineer address every definition_of_done item?"
  │
  ├── Gate 7: QA Agent Review            (agent — deep code review)
  │
  ├── Gate 8: Goal Verification          (auto — cross-check final report with goals)
  │           ↳ Generate goal-verification.json
  │
  └── Gate 9: Human Approval             (optional — for critical path tasks)
  │
  └── PASS / FAIL
```

### Key Features
- **Automated gates** run before QA review — catch obvious issues cheaply
- **Goal pre-check** — verify engineer addressed every `definition_of_done` item _before_ sending to QA
- **Goal verification** — automated cross-check generates `goal-verification.json` per room
- **Scoring rubric** — quantify agent output quality (0-100)
- **Historical tracking** — track quality scores per role, per model, per project over time
- **Feedback loop analysis** — identify recurring QA failures → suggest prompt improvements
- **A/B testing** — compare models/prompts for the same task type
- **Quality reports** — `ostwin quality report --plan auth-system` for stakeholders

---

## Module 6: Human-in-the-Loop Framework

> **Goal**: Seamless human intervention points without breaking the autonomous 24/7 flow.

### Proposed Structure

```
human/
├── Invoke-Escalation.ps1     # Escalation rules engine
├── Invoke-Escalation.Tests.ps1
├── Request-Approval.ps1      # Approval workflow
├── Request-Approval.Tests.ps1
├── notifiers/
│   ├── Send-TerminalNotice.ps1
│   ├── Send-SlackNotice.ps1
│   ├── Send-EmailNotice.ps1
│   └── Send-WebhookNotice.ps1
└── policies/
    ├── auto-approve.yaml     # What can be auto-approved
    ├── escalation.yaml       # When to escalate to human
    └── review-gates.yaml     # Which tasks need human review
```

### Intervention Points

```
PLAN QUEUE                    EXECUTION                    COMPLETION
    │                             │                             │
    ▼                             ▼                             ▼
Queue Plan ── [HUMAN?] ──► Room Created                        │
                               │                               │
                         Engineer Works                        │
                               │                               │
                        Quality Gates (auto)                   │
                               │                               │
                           QA Review                           │
                               │                               │
              Critical Path ─ [HUMAN] ─ Approve/Override       │
                               │                               │
                      failed-final ── [HUMAN] ── Escalation    │
                               │                               │
                     Budget Alert ── [HUMAN] ── Continue/Stop  │
                               │                               │
                         Goal Verified                         │
                               │                               │
                       Release Draft ── [HUMAN] ── Sign-off    │
```

### Escalation Policies

```yaml
# escalation.yaml
rules:
  - trigger: "failed-final"
    action: "block_and_notify"
    channels: [terminal, slack]
    message: "Task {task_ref} failed after {max_retries} retries in room {room_id}"
    include_context: [last_error, qa_feedback, goal_status]

  - trigger: "security_gate_fail"
    action: "block_and_notify"
    severity: critical
    channels: [slack, email]
    message: "Security vulnerability found in {task_ref}"

  - trigger: "goal_verification_partial"
    action: "notify_and_continue"
    channels: [terminal]
    message: "{unmet_count} goals not met in {task_ref}. Review goal-verification.json"

  - trigger: "cost_threshold_exceeded"
    action: "pause_and_notify"
    threshold_usd: 50.00
    channels: [terminal, slack]
    message: "Token spend exceeded $50 for plan {plan_id}"

  - trigger: "human_review_tag"
    tag: "critical-path"
    action: "block_until_approved"
    channels: [terminal, dashboard]
    message: "Task {task_ref} tagged as critical-path — human approval required"

  - trigger: "plan_completed"
    action: "notify"
    channels: [terminal, slack]
    message: "Plan {plan_id} completed. {passed_count}/{total_count} rooms passed."
```

### Key Features
- **Policy-driven**: YAML policies define when humans must intervene
- **Non-blocking by default**: System continues processing other rooms while waiting for human
- **Multi-channel**: Terminal, Slack, email, webhook — configurable per trigger
- **Approval from dashboard**: Accept/reject/modify from browser or CLI
- **Cost controls**: Automatic pause when token spend exceeds threshold per plan
- **Override capability**: Human can force-pass, force-fail, re-assign, or inject guidance
- **Audit trail**: All human decisions logged with timestamp, decision, and reasoning

---

## Module 7: Advanced Orchestration Features

> **Goal**: Production-grade scheduling, multi-project support, and extensibility.

### 7.1 — Multi-Project Orchestration

```powershell
# Queue plans from different projects
ostwin queue add /path/to/frontend/plans/dashboard-v2.md --priority 1
ostwin queue add /path/to/backend/plans/api-refactor.md --priority 2
ostwin queue add /path/to/mobile/plans/ios-release.md --priority 3

# Or run everything in the queue
ostwin run --continuous   # 24/7 mode: process queue forever
```

### 7.2 — Team Templates

```yaml
# teams/full-stack.yaml
name: "Full-Stack Team"
roles:
  - engineer: { count: 2, model: "gemini-3-flash" }
  - qa: { count: 1, model: "gemini-3-flash" }
  - architect: { count: 1, model: "gemini-3.1-pro" }
  - devops: { count: 1, model: "gemini-3-flash" }
war_room_composition:
  default: [engineer, qa]           # Standard pair
  infra: [devops, qa]              # Infra tasks
  design: [architect, engineer]    # Architecture tasks
```

### 7.3 — Plugin System

```
plugins/
├── git-integration/          # Auto-commit, branch per task, PR creation
├── ci-bridge/                # Trigger CI/CD pipelines after QA pass
├── code-review/              # GitHub PR review integration
├── knowledge-base/           # Shared knowledge across roles and runs
└── custom/                   # User-defined plugins
```

### 7.4 — Agent Memory & Learning
- **Cross-run memory**: Agents remember patterns from previous runs via knowledge base
- **Project knowledge base**: Shared context that persists across plan runs
- **Skill evolution**: Analyze QA feedback patterns → auto-refine role skills
- **Model routing**: Cheaper models for simple tasks, premium models for complex epics

---

## Implementation Roadmap

### Phase 1: Foundation (v0.2) — 2-3 weeks
- [ ] PowerShell migration of all core scripts (channel, war-rooms, roles)
- [ ] Pester test suite for every module
- [ ] War-room [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) with goal definitions
- [ ] Goal verification report (`goal-verification.json`)
- [ ] Role engine with `role.yaml` declarative config

### Phase 2: Intelligence (v0.3) — 3-4 weeks
- [ ] Plan queue with priority ordering
- [ ] Continuous execution mode (`ostwin run --continuous`)
- [ ] Quality gate pipeline (lint → test → coverage → security → goal-check)
- [ ] Enhanced observability (structured tracing, SQLite storage)
- [ ] Dashboard WebSocket real-time updates
- [ ] Role-specific skills and context injection

### Phase 3: Scale (v0.4) — 3-4 weeks
- [ ] Multi-project orchestration
- [ ] Human-in-the-loop escalation policies
- [ ] Team templates and role composition
- [ ] Cost tracking and budget controls
- [ ] Advanced dashboard (Kanban, timeline, goal tracker, metrics)
- [ ] Multi-channel notifications (Slack, webhook)

### Phase 4: Production (v1.0) — 4-6 weeks
- [ ] Plugin system architecture
- [ ] Agent memory and cross-run learning
- [ ] Model routing and optimization
- [ ] OpenTelemetry export
- [ ] Git integration plugin
- [ ] CI/CD bridge plugin
- [ ] Full documentation and examples

---

## Architecture Decision Records

### ADR-001: PowerShell as Orchestration Language
**Decision**: Migrate all [.sh](file:///Users/paulaan/PycharmProjects/agent-os/.agents/run.sh) scripts to PowerShell (`.ps1`) with Pester unit tests.
**Rationale**:
- Native structured data handling (`ConvertFrom-Json`, objects)
- Proper error handling (`try/catch/finally`)
- Industry-standard testing via Pester with mocking and code coverage
- Cross-platform: Windows, macOS, Linux
- Module system with proper scoping and namespacing
- Parameter validation built into the language (`[ValidateNotNull()]`)
- deepagents CLI invocation is identical (subprocess call)

### ADR-002: deepagents as Agent Runtime
**Decision**: Use deepagents CLI for all agent roles.
**Rationale**:
- Built-in planning, filesystem, shell, and sub-agent tools
- LangGraph-native — streaming, persistence, checkpointing
- Provider-agnostic — any LLM with tool calling
- MIT licensed, fully extensible
- MCP support via langchain-mcp-adapters

### ADR-003: JSONL Channels for Communication
**Decision**: Keep file-based JSONL channels.
**Rationale**:
- No external infrastructure (no Redis, no Kafka)
- Fully auditable — every message on disk
- Crash-resilient — state survives restarts
- PowerShell natively reads/writes JSON (`ConvertTo-Json`)

### ADR-004: War-Room Config as Goal Contract
**Decision**: Every war-room carries a [config.json](file:///Users/paulaan/PycharmProjects/agent-os/.agents/config.json) with explicit goal definitions.
**Rationale**:
- Definition of Done is **machine-readable**, not just prose in a plan markdown
- Enables **automated goal verification** at completion
- Cross-checking ensures nothing is missed — no "I thought it was done" gaps
- Config persists with the war-room archive for full audit trail
- Quality gates reference the same goals — single source of truth

### ADR-005: Continuous Queue Over Time-Boxed Sprints
**Decision**: Use a plan queue with continuous execution instead of sprint boundaries.
**Rationale**:
- AI agents don't need rest — 24/7 execution maximizes throughput
- Queue model is simpler than sprint planning ceremonies
- Priority ordering replaces sprint commitment — critical plans jump the queue
- Completed plans archive automatically with full history
- Failed plans re-queue at higher priority — no manual triage needed
- Scales naturally: add more rooms (capacity), not more sprints (time)
