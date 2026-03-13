# Agent OS — TODO (Phase 1: Foundation v0.2)

> **Plan**: [PLAN.md](file:///Users/paulaan/.gemini/antigravity/brain/915fd618-ee0f-4d47-bd52-6020a79babdb/PLAN.md)
> **Status**: Phase 1 — Foundation
> **Target**: v0.2

---

## Epic 1: PowerShell Migration — Core Infrastructure

> Migrate all bash scripts to PowerShell with full Pester unit tests.

### Lib Module
- [x] `lib/Log.psm1` — Structured logging (replace `log.sh`)
- [x] `lib/Log.Tests.ps1` — Pester tests for logging
- [x] `lib/Utils.psm1` — Shared utilities (replace `utils.sh`)
- [x] `lib/Utils.Tests.ps1` — Pester tests for utilities
- [x] `lib/Config.psm1` — Config loading, validation, merging
- [x] `lib/Config.Tests.ps1` — Pester tests for config

### Channel Module
- [x] `channel/Post-Message.ps1` — Post JSONL message (replace `post.sh`)
- [x] `channel/Post-Message.Tests.ps1`
- [x] `channel/Read-Messages.ps1` — Read/filter messages (replace `read.sh`)
- [x] `channel/Read-Messages.Tests.ps1`
- [x] `channel/Wait-ForMessage.ps1` — Block until message type (replace `wait-for.sh`)
- [x] `channel/Wait-ForMessage.Tests.ps1`

### War-Room Module
- [x] `war-rooms/New-WarRoom.ps1` — Create war-room with `config.json` (replace `create.sh`)
- [x] `war-rooms/New-WarRoom.Tests.ps1`
- [x] `war-rooms/Get-WarRoomStatus.ps1` — Status of all rooms (replace `status.sh`)
- [x] `war-rooms/Get-WarRoomStatus.Tests.ps1`
- [x] `war-rooms/Remove-WarRoom.ps1` — Teardown (replace `teardown.sh`)
- [x] `war-rooms/Remove-WarRoom.Tests.ps1`

---

## Epic 2: PowerShell Migration — Roles & Orchestration

> Migrate role runners and manager loop to PowerShell.

### Base Role Launcher
- [x] `roles/_base/Invoke-Agent.ps1` — Universal deepagents wrapper
- [x] `roles/_base/Invoke-Agent.Tests.ps1`

### Engineer Role
- [x] `roles/engineer/Start-Engineer.ps1` — Engineer runner (replace `run.sh`)
- [x] `roles/engineer/Start-Engineer.Tests.ps1`

### QA Role
- [x] `roles/qa/Start-QA.ps1` — QA runner (replace `run.sh`)
- [x] `roles/qa/Start-QA.Tests.ps1`

### Manager Loop
- [x] `roles/manager/Start-ManagerLoop.ps1` — Main orchestration loop (replace `loop.sh`)
- [x] `roles/manager/Start-ManagerLoop.Tests.ps1`

### Entry Points
- [x] `plan/New-Plan.ps1` — AI-assisted plan creation (replace `plan.sh`)
- [x] `plan/New-Plan.Tests.ps1`
- [x] `plan/Start-Plan.ps1` — Parse plan → spawn rooms (replace `run.sh`)
- [x] `plan/Start-Plan.Tests.ps1`
- [x] `bin/ostwin` — Update CLI to call PowerShell

---

## Epic 3: War-Room Goal Config

> Implement per-war-room `config.json` with goal definitions and cross-checking.

- [x] Define `config.json` schema (JSON Schema: `war-rooms/config-schema.json`)
- [x] `New-WarRoom.ps1` creates `config.json` with goals from plan
- [x] Plan parser extracts `definition_of_done` and `acceptance_criteria` per epic/task
- [x] `Test-GoalCompletion.ps1` — Cross-check goals vs engineer output
- [x] `Test-GoalCompletion.Tests.ps1`
- [x] `New-GoalReport.ps1` — Generate `goal-verification.json` per room
- [x] `New-GoalReport.Tests.ps1`
- [x] Manager loop calls goal verification after QA pass (before final `passed` status)

---

## Epic 4: Extensible Role Engine

> Declarative role definitions with `role.yaml`, skill mounting, and context injection.

- [x] Define `role.json` schema (declarative role definitions)
- [x] `Get-RoleDefinition.ps1` — Load and validate role config
- [x] `Get-RoleDefinition.Tests.ps1`
- [x] `Build-SystemPrompt.ps1` — Compose prompt from ROLE.md + skills + context
- [x] `Build-SystemPrompt.Tests.ps1`
- [x] `roles/registry.json` — Role catalog
- [x] Convert existing `ROLE.md` files to work with new `role.json` alongside
- [x] Create sample `role.json` for engineer, qa, architect

---

## Epic 5: Enhanced Observability

> Structured tracing with trace/span IDs and SQLite queryable storage.

- [x] `lib/Observability.psm1` — Full module: tracing, spans, events, metrics
- [x] `lib/Observability.Tests.ps1`
- [x] `New-Trace` / `Start-Span` / `Complete-Span` — Distributed tracing
- [x] `Write-TraceEvent` — Structured events with trace context
- [x] `Add-Metric` / `Get-MetricValue` — Counter, gauge, histogram metrics
- [x] `Export-TraceReport` — JSON trace report export
- [x] `observe/exporters/Export-ToSqlite.ps1` — SQLite exporter
- [x] `observe/exporters/Export-ToSqlite.Tests.ps1`
- [x] JSONL trace log schema (trace.jsonl)

---

## Epic 6: Dashboard WebSocket Updates

> Upgrade dashboard from polling to real-time WebSocket push.

- [x] `dashboard/api.py` — FastAPI + WebSocket handler + REST endpoints
- [x] `dashboard/frontend/index.html` — Real-time dark-mode dashboard with WebSocket
- [x] WebSocket: file-system watcher broadcasts status_change + new_message events
- [x] Add goal tracker view (progress bars on cards + ✅🟡❌ in detail modal)
- [x] Add war-room `config.json` goals display in room detail view

---

## Epic 7: Installer Packaging

> Cross-platform installer that sets up all dependencies on macOS and Linux.

- [x] `install.sh` — Rewrite with Python, PowerShell, uv, deepagents-cli auto-install
- [x] `uninstall.sh` — Clean removal with PATH cleanup
- [x] Cross-platform support: macOS (arm64/x86_64), Ubuntu/Debian, Fedora/RHEL
- [x] Interactive & non-interactive (`--yes`) modes
- [x] Updated `init.sh` — Scaffold all 22 PS files + role registry + _base engine
- [x] Verification summary with component status display

---

## Release Notes

### v0.2.0-alpha — Phase 1 Foundation (2026-03-13)

**Epic 1 — PS Migration Core ✅**
- Migrated Log, Utils, Config modules to PowerShell with full Pester tests
- Migrated Channel module (Post, Read, Wait) with JSONL locking and filter support
- Migrated War-Room module (New, Status, Remove) with config.json goal contracts

**Epic 2 — PS Migration Roles ✅**
- Created universal `Invoke-Agent.ps1` launcher with PID tracking and timeout
- Migrated Engineer and QA role runners with Epic/Task-aware prompts
- Full Manager orchestration loop with state machine, deadlock detection, retry management
- Plan creation and parsing with goal extraction from markdown
- CLI updated with `ps_dispatch()` for PowerShell-first, bash-fallback

**Epic 3 — War-Room Goal Config ✅**
- JSON Schema for per-war-room config.json
- Goal verification engine with multi-strategy matching (exact → key term → score)
- Goal report generation (goal-verification.json) with per-goal evidence
- TASKS.md completion tracking for epics

**Epic 4 — Extensible Role Engine ✅**
- Declarative role.json definitions for engineer, qa, architect
- Role definition loader with auto-defaults from ROLE.md
- Build-SystemPrompt composer: ROLE.md + capabilities + quality gates + skills + war-room context + QA feedback
- Role registry (roles/registry.json) with auto-discovery support

**Epic 5 — Enhanced Observability ✅**
- Full Observability.psm1 module: distributed tracing, spans, metrics
- Trace context propagation through events
- JSONL trace log export and JSON report generation
- SQLite exporter with indexed tables (events, spans, metrics, messages, rooms)

**Epic 6 — Dashboard WebSocket ✅**
- FastAPI backend with REST + WebSocket endpoints
- File-system watcher broadcasts real-time status changes and new messages
- Dark-mode responsive dashboard with animated room cards and goal progress bars
- Room detail modal with goals (✅🟡❌), messages, and config display
- REST fallback polling + keyboard shortcuts

**Epic 7 — Installer Packaging ✅**
- Cross-platform `install.sh` — macOS (arm64/x86_64) + Linux (apt/dnf/pacman/zypper)
- Auto-installs: Python 3.10+, PowerShell 7+, uv, deepagents-cli, Pester 5+
- Interactive & non-interactive (`--yes`) modes with colored output
- Clean `uninstall.sh` with PATH cleanup
- Updated `init.sh` to scaffold all 22 PowerShell files + role registry
- Cross-platform `sed` (macOS `-i ''` vs Linux `-i`)

---

| Epic | Items | Status |
|------|-------|--------|
| 1. PS Migration — Core | 18 items | ✅ Complete |
| 2. PS Migration — Roles | 13 items | ✅ Complete |
| 3. War-Room Goal Config | 8 items | ✅ Complete |
| 4. Extensible Role Engine | 8 items | ✅ Complete |
| 5. Enhanced Observability | 9 items | ✅ Complete |
| 6. Dashboard WebSocket | 5 items | ✅ Complete |
| 7. Installer Packaging | 6 items | ✅ Complete |
| **Total** | **67 items** | **67 done ✅** |

