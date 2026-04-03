# EPIC: Fix All Known Manager Loop Deadlock Risks

> Created: 2026-04-02T12:30:00+07:00
> Status: draft → **already implemented**
> Project: agent-os

## Goal

Eliminate the 4 remaining known exploitation risks in `Start-ManagerLoop.ps1` that cause permanent deadlocks or incorrect agent spawning, as documented in `Deadlock.Tests.ps1`.

---

## User Review Required

> [!IMPORTANT]
> **All 4 fixes are already applied in production code.**
>
> After thorough analysis of the current codebase, every proposed fix from this EPIC is **already implemented** in [Start-ManagerLoop.ps1](file:///Users/paulaan/PycharmProjects/agent-os/.agents/roles/manager/Start-ManagerLoop.ps1). The deadlock recovery section (lines 1094–1181) already:
>
> - Calls `Stop-RoomProcesses $rd` before transition (Risk 2)
> - Spawns workers via `Start-WorkerJob` immediately (Risk 2)
> - Does **not** increment `retries` — only `deadlock_recoveries` (Risk 3+4)
> - Resolves role from `$dlStateDef.role` first, falling back to `config.json` (Risk 6)

> [!NOTE]
> **Test suites already verify the fixed behavior.** Both [Deadlock.Tests.ps1](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1) and [Start-ManagerLoop.Tests.ps1](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Start-ManagerLoop.Tests.ps1) assert the correct (post-fix) semantics. No test updates are needed.

---

## Risk Summary & Current State

| Risk | Severity | Root Cause | Status | Evidence |
|---|---|---|---|---|
| **Risk 2** | 🔴 High | Deadlock recovery doesn't spawn worker + leaves stale PIDs | ✅ **FIXED** | Lines 1154, 1170–1175 |
| **Risk 3** | 🔴 Critical | Deadlock recovery increments `retries` → done-count gate unsatisfiable | ✅ **FIXED** | Lines 1156–1160 (comment-only, no write) |
| **Risk 4** | 🟡 Medium | QA deadlock cascades into Risk 3 via triage → fixing | ✅ **FIXED** | Same as Risk 3 — no retry increment |
| **Risk 6** | 🟡 Medium | Deadlock recovery uses `config.json` role instead of lifecycle state role | ✅ **FIXED** | Lines 1127–1138 |

---

## EPIC-001 — Risk 2: Stale PID Cleanup + Worker Spawn

**Phase:** 1
**Priority:** P0
**Estimated Effort:** Already done
**Status:** ✅ FIXED

Roles: engineer
Objective: Deadlock recovery must clean stale PIDs and spawn the correct worker immediately.

### Description

**Problem:** Deadlock recovery transitions to `restartState` but doesn't call `Start-WorkerJob` or clean stale PIDs. On the next iteration, the stale PID blocks the respawn branch, and the "PID dead" branch increments retries again (double increment).

**Applied Fix (lines 1153–1175):**

```powershell
# Risk 2 fix: Clean stale PIDs before transition (prevents double retry increment)
Stop-RoomProcesses $rd

# ... role resolution ...

Write-RoomStatus $rd $restartState

# Risk 2 fix: Spawn worker immediately (don't rely on next iteration's respawn branch)
$dlResolveRole = Join-Path $agentsDir "roles" "_base" "Resolve-Role.ps1"
if (Test-Path $dlResolveRole) {
    $dlResolved = & $dlResolveRole -RoleName ($restartStateDef.role) -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
    Start-WorkerJob -RoomDir $rd -Role $dlRestartRole -Script $dlResolved.Runner -TaskRef $lt -SkipLockCheck
}
```

### Test Coverage

- [Deadlock.Tests.ps1:270–288](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1#L270-L288) — `Invoke-DeadlockRecovery` helper cleans PIDs, asserts `Test-Path ... | Should -BeFalse`
- [Start-ManagerLoop.Tests.ps1:1884–1900](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Start-ManagerLoop.Tests.ps1#L1884-L1900) — Static analysis: confirms `Stop-RoomProcesses $rd` and `Start-WorkerJob -RoomDir $rd ... -SkipLockCheck` exist in production code

depends_on: []

---

## EPIC-002 — Risk 3+4: Done-Count Gate Corruption

**Phase:** 1
**Priority:** P0
**Estimated Effort:** Already done
**Status:** ✅ FIXED

Roles: engineer
Objective: Deadlock recovery must NOT increment `retries`. Exhaustion is handled by `deadlock_recoveries` cap (line 1113), not lifecycle retries.

### Description

**Problem:** Deadlock recovery increments `retries`, which raises the done-count `expected` value (`retries + 1`). Since workers don't know about historical done messages, the gate becomes permanently unsatisfiable. Risk 4 compounds this: QA deadlock recovery cascades into Risk 3 via triage → fixing.

**Applied Fix (lines 1156–1160):**

```powershell
# Risk 3+4 fix: DO NOT increment retries here.
# Retries should only be incremented by lifecycle signal actions (e.g. increment_retries on QA fail).
# Incrementing retries during deadlock recovery corrupts the done-count gate (Risk 3)
# and compounds into QA cascade deadlocks (Risk 4).
# Exhaustion is handled by the deadlock_recoveries cap (line 1113), not by lifecycle retries.
```

**Key design decision:** The old `if ($lr -lt $dlMaxRetries)` gate was replaced with the `deadlock_recoveries` cap at line 1113 (`if ($dlCount -ge 3)` → early return to `failed-final`). This decouples deadlock budgets from lifecycle retry budgets entirely.

### Test Coverage

- [Deadlock.Tests.ps1:117–168](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1#L117-L168) — Risk 3 tests: `retries | Should -Be 0` after recovery, `WouldTransition | Should -BeTrue`
- [Deadlock.Tests.ps1:177–206](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1#L177-L206) — Risk 4 test: QA cascade doesn't inflate retries
- [Deadlock.Tests.ps1:359–386](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1#L359-L386) — Integration: 7 recoveries, `retries | Should -Be 0`, `expected | Should -Be 1`
- [Start-ManagerLoop.Tests.ps1:1902–1908](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Start-ManagerLoop.Tests.ps1#L1902-L1908) — Static analysis: no `($lr + 1)` write to retries

depends_on: []

---

## EPIC-003 — Risk 6: Wrong Runner for Multi-Role Lifecycles

**Phase:** 1
**Priority:** P1
**Estimated Effort:** Already done
**Status:** ✅ FIXED

Roles: engineer
Objective: Deadlock recovery must resolve the role from lifecycle state definition, not from `config.json`'s `assigned_role`.

### Description

**Problem:** In a multi-role lifecycle (e.g., `developing → reporting` where `reporting.role = "reporter"`), deadlock recovery would restart with the wrong runner because it read from `config.json` instead of lifecycle state.

**Applied Fix (lines 1121–1138):**

```powershell
# Risk 6 fix: Resolve role from lifecycle state, not config.json.
# Multi-role lifecycles (e.g. reporting.role=reporter) need the state's role.
$dlRole = "engineer"
if ($dlStateDef -and $dlStateDef.role) {
    $dlRole = ($dlStateDef.role -replace ':.*$', '')
} else {
    $dlRoomConfig = Join-Path $rd "config.json"
    if (Test-Path $dlRoomConfig) {
        $dlRc = Get-Content $dlRoomConfig -Raw | ConvertFrom-Json
        if ($dlRc.assignment -and $dlRc.assignment.assigned_role) {
            $dlRole = $dlRc.assignment.assigned_role -replace ':.*$', ''
        }
    }
}
```

And the restart state's role is also resolved from lifecycle (lines 1162–1164):
```powershell
$restartStateDef = if ($dlLifecycle.states.$restartState) { $dlLifecycle.states.$restartState } else { $null }
$dlRestartRole = if ($restartStateDef -and $restartStateDef.role) { ($restartStateDef.role -replace ':.*$', '') } else { $dlRole }
```

### Test Coverage

- [Deadlock.Tests.ps1:214–262](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Deadlock.Tests.ps1#L214-L262) — Risk 6: `reporting.role` should be `reporter`, not `engineer`
- [Start-ManagerLoop.Tests.ps1:1911–1917](file:///Users/paulaan/PycharmProjects/agent-os/.agents/tests/roles/manager/Start-ManagerLoop.Tests.ps1#L1911-L1917) — Static analysis: `$dlStateDef.role` pattern found in production

depends_on: []

---

## Open Questions

> [!IMPORTANT]
> **Q1: Should `retries` be completely independent from deadlock recoveries?**
>
> Currently `retries` is shared between normal fail→retry cycles and deadlock recovery. The fix removes the deadlock recovery increment, but should we also add a separate `deadlock_retries` counter?
>
> **Answer from code analysis:** The code already separates these — `deadlock_recoveries` (line 1111) tracks deadlock-specific budget (capped at 3), and `retries` is only incremented by `Invoke-SignalActions` via lifecycle `increment_retries` actions. No additional counter is needed.

> [!IMPORTANT]
> **Q2: Should the PLAN-REVIEW shortcut's done-count gate also be removed?**
>
> **Answer from code analysis:** The PLAN-REVIEW shortcut (lines 938–1012) does NOT use a done-count gate (`expected = retries + 1`). Instead, it checks for `pass`/`plan-approve`/`done` signals directly with keyword matching. The old done-count gate is not present here — it was a V1 artifact that is no longer in the code.

---

## Verification Plan

### Automated Tests

```bash
# Run deadlock exploitation tests
pwsh -Command "Invoke-Pester -Path '.agents/tests/roles/manager/Deadlock.Tests.ps1' -Output Detailed"

# Run all manager loop tests (includes static analysis of deadlock fixes)
pwsh -Command "Invoke-Pester -Path '.agents/tests/roles/manager/Start-ManagerLoop.Tests.ps1' -Output Detailed"

# Run lifecycle pipeline tests
pwsh -Command "Invoke-Pester -Path '.agents/tests/lifecycle/Resolve-Pipeline.Tests.ps1' -Output Detailed"
```

### Manual Verification

1. Deploy to a test environment with a room that has a known MCP schema error
2. Observe that the manager:
   - Doesn't inflate `retries` during deadlock recovery
   - Cleans stale PIDs before restart
   - Spawns the correct role from lifecycle state
   - Caps deadlock recoveries at 3 and marks `failed-final`
3. Verify no rooms get permanently stuck in the `fixing` state

