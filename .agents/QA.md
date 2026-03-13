# Agent OS — QA Report (Epic 1: Core Infrastructure + Epic 2/4: Roles)

> **Date**: 2026-03-13  
> **Scope**: All 15 Pester test files — Lib, Channel, War-Room, Role modules  
> **Pester Version**: 5.7.1  
> **PowerShell Version**: 7.5.4 (macOS)

---

## Test Results — Epic 1: Core Infrastructure

| File | Tests | Passed | Failed | Status |
|------|-------|--------|--------|--------|
| `lib/Log.Tests.ps1` | 15 | 15 | 0 | ✅ |
| `lib/Utils.Tests.ps1` | 25 | 25 | 0 | ✅ |
| `lib/Config.Tests.ps1` | 15 | 15 | 0 | ✅ |
| `channel/Post-Message.Tests.ps1` | 10 | 10 | 0 | ✅ |
| `channel/Read-Messages.Tests.ps1` | 22 | 22 | 0 | ✅ |
| `channel/Wait-ForMessage.Tests.ps1` | 6 | 6 | 0 | ✅ |
| `war-rooms/New-WarRoom.Tests.ps1` | 17 | 17 | 0 | ✅ |
| `war-rooms/Get-WarRoomStatus.Tests.ps1` | 11 | 11 | 0 | ✅ |
| `war-rooms/Remove-WarRoom.Tests.ps1` | 10 | 10 | 0 | ✅ |
| **Subtotal** | **131** | **131** | **0** | **✅** |

## Test Results — Epic 2/4: Role Engine

| File | Tests | Passed | Failed | Status |
|------|-------|--------|--------|--------|
| `roles/_base/Get-RoleDefinition.Tests.ps1` | 19 | 19 | 0 | ✅ |
| `roles/_base/Build-SystemPrompt.Tests.ps1` | 17 | 17 | 0 | ✅ |
| `roles/_base/Invoke-Agent.Tests.ps1` | 13 | 13 | 0 | ✅ |
| `roles/engineer/Start-Engineer.Tests.ps1` | 9 | 9 | 0 | ✅ |
| `roles/manager/Start-ManagerLoop.Tests.ps1` | 14 | 14 | 0 | ✅ |
| `roles/qa/Start-QA.Tests.ps1` | 11 | 11 | 0 | ✅ |
| **Subtotal** | **83** | **83** | **0** | **✅** |

---

## Grand Total: 214 tests, 214 passed, 0 failed ✅

---

## Bugs Found & Fixed

### BUG-001: Pester v5 Scoping — `$script:` variables at file level

**Severity**: High (caused 12 test failures in Config.Tests.ps1 + 17 in Read-Messages.Tests.ps1)

**Root Cause**: In Pester v5, script-level code outside `Describe`/`BeforeAll` runs during the **discovery phase**, not during test execution. Variables set at file level with `$script:` are not available in the run phase.

**Files affected**:
- `lib/Config.Tests.ps1` — `$script:ValidConfig` hashtable defined at file level
- `channel/Read-Messages.Tests.ps1` — `Add-TestMessages` helper function defined at file level

**Fix**: Moved all shared test data and helper functions inside `BeforeAll {}` blocks.

---

### BUG-002: ConvertFrom-Json DateTime auto-conversion

**Severity**: Medium (caused 3 test failures across Log, Post-Message, New-WarRoom tests)

**Root Cause**: PowerShell 7's `ConvertFrom-Json` automatically deserializes ISO 8601 strings (e.g. `"2026-03-13T02:14:52Z"`) into `System.DateTime` objects. When `Should -Match` converts a DateTime to string, it uses the locale-dependent `DateTime.ToString()` format (e.g. `03/13/2026 02:16:30`), which no longer matches ISO 8601 regex patterns like `\d{4}-\d{2}-\d{2}T`.

**Files affected**:
- `lib/Log.Tests.ps1` line 141
- `channel/Post-Message.Tests.ps1` line 38  
- `war-rooms/New-WarRoom.Tests.ps1` line 73

**Fix**: Used `.ToString("o")` to convert DateTime back to ISO 8601 round-trip format before regex matching.

---

### BUG-003: Single-item pipeline unwrapping

**Severity**: Medium (caused 1 test failure in Post-Message.Tests.ps1)

**Root Cause**: In PowerShell, `Get-Content | Where-Object` returns a plain `System.String` (not `String[]`) when exactly 1 line matches. Indexing `$lines[0]` on a String returns the **first character** (`{`), not the first array element, causing `ConvertFrom-Json` to fail with "Unexpected end when reading JSON".

**File affected**: `channel/Post-Message.Tests.ps1` line 28

**Fix**: Wrapped in `@()` to force array context: `$lines = @(Get-Content $channelFile | Where-Object { $_.Trim() })`

---

### BUG-004: Get-TruncatedText rejects empty string

**Severity**: Low (caused 1 test failure in Utils.Tests.ps1)

**Root Cause**: `[Parameter(Mandatory)]` without `[AllowEmptyString()]` rejects empty string arguments. The bash `truncate_bytes` function accepted empty text.

**File affected**: `lib/Utils.psm1` — `Get-TruncatedText` function

**Fix**: Added `[AllowEmptyString()]` attribute to the `$Text` parameter.

---

### BUG-005: Test-PidAlive null method call on empty file

**Severity**: Low (caused 1 test failure in Utils.Tests.ps1)

**Root Cause**: `Get-Content $PidFile -Raw` returns `$null` for an empty file. Calling `.Trim()` on `$null` throws "You cannot call a method on a null-valued expression."

**File affected**: `lib/Utils.psm1` — `Test-PidAlive` function

**Fix**: Added `[string]::IsNullOrWhiteSpace()` check before `.Trim()`.

---

### BUG-006: Regex `\a` is bell character, not literal 'a'

**Severity**: Low (caused 1 test failure in Utils.Tests.ps1)

**Root Cause**: The regex `^\a\]lon` uses `\a` which is a regex escape for the ASCII bell character (0x07), not the literal letter 'a'.

**File affected**: `lib/Utils.Tests.ps1` line 178

**Fix**: Replaced `-Match "^\a\]lon"` with `-BeLike "a]lon*"`.

---

### BUG-007: Write-Error capture pattern in Pester v5

**Severity**: Low (caused 2 test failures across New-WarRoom + Remove-WarRoom tests)

**Root Cause**: The pattern `{ & script.ps1 } 2>&1 | Should -Match` doesn't reliably capture `Write-Error` output from external `.ps1` scripts in Pester v5. The `2>&1` merge needs to be on the invocation (`$output = & script.ps1 2>&1`), not on the scriptblock.

**Files affected**:
- `war-rooms/New-WarRoom.Tests.ps1` line 169-171
- `war-rooms/Remove-WarRoom.Tests.ps1` line 37-38

**Fix**: Changed to `$output = & script.ps1 2>&1; $output | Should -Match`.

---

### BUG-008: Multi-line output regex matching

**Severity**: Low (caused 1 test failure in Remove-WarRoom.Tests.ps1)

**Root Cause**: `Remove-WarRoom.ps1` produces multiple `Write-Output` calls. `Should -Match` on an array tests **each element individually**, so `TEARDOWN.*room-del.*removed` only matches if a single output line contains both words. The removal confirmation is split across two lines.

**File affected**: `war-rooms/Remove-WarRoom.Tests.ps1` line 31

**Fix**: Joined output with `($output -join "`n") | Should -Match`.

---

## PLAN.md Compliance Check

| PLAN.md Requirement | Status | Evidence |
|---|---|---|
| Every `.sh` has matching `.ps1` + `.Tests.ps1` | ✅ | All 9 bash scripts → 9 PS scripts → 9 test files |
| `lib/` modules: Log, Utils, Config | ✅ | All 3 modules + 3 test files pass |
| `channel/` scripts: post, read, wait-for | ✅ | All 3 scripts + 3 test files pass |
| `war-rooms/` scripts: create, status, teardown | ✅ | All 3 scripts + 3 test files pass |
| `config.json` goal contract in New-WarRoom | ✅ | 10 tests validate config.json structure, goals, constraints |
| `goal-verification.json` in status display | ✅ | Test verifies `2/3` goal completion display |
| ValidateSet for status values | ✅ | 6 states: pending, engineering, qa-review, fixing, passed, failed-final |
| ValidateSet for message types | ✅ | 9 types: task, done, review, pass, fail, fix, error, signoff, release |
| Audit trail in Set-WarRoomStatus | ✅ | Tests verify `old -> new` status in audit.log |
| Config validation (Test-OstwinConfig) | ✅ | Tests check required fields, ranges, multiple errors |
| Archive mode in Remove-WarRoom | ✅ | Archives channel, config, audit, goals before removal |
| Pester v5 compatibility | ✅ | All tests pass with Pester 5.7.1 |
| Cross-platform (macOS) | ✅ | Tests pass on Darwin 25.4.0 / PowerShell 7.5.4 |

---

## Sign-off

> **QA Verdict**: ✅ **PASS** — All 131 tests pass. 8 bugs found and fixed. Epic 1 is complete and compatible with PLAN.md.
