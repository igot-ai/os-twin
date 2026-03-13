# Plan: Port Remaining Bash Scripts to PowerShell

> Priority: 1 (foundation — unblocks Plan 8)
> Parallel: ✅ No dependencies

## Goal

Port the 10 remaining bash scripts to PowerShell with Pester tests, completing the full PowerShell migration.

## Epics

### EPIC-001 — Port CLI & System Scripts

#### Definition of Done
- [ ] `config.sh` → `Get-Config.ps1` + tests
- [ ] `health.sh` → `Test-Health.ps1` + tests
- [ ] `stop.sh` → `Stop-Manager.ps1` + tests
- [ ] `logs.sh` → `Get-Logs.ps1` + tests

#### Acceptance Criteria
- [ ] `ostwin config --get manager.poll_interval` works via PowerShell
- [ ] `ostwin health` runs health checks via PowerShell
- [ ] `ostwin stop` gracefully stops manager via PowerShell
- [ ] `ostwin logs room-001` shows filtered channel messages

#### Tasks
- [ ] TASK-001 — Port config.sh to Get-Config.ps1 with get/set operations
- [ ] TASK-002 — Port health.sh to Test-Health.ps1 with dependency checks
- [ ] TASK-003 — Port stop.sh to Stop-Manager.ps1 with graceful shutdown
- [ ] TASK-004 — Port logs.sh to Get-Logs.ps1 with --follow and --type filters

### EPIC-002 — Port Init, Dashboard, Release Scripts

#### Definition of Done
- [ ] `init.sh` → `Initialize-Project.ps1` + tests
- [ ] `dashboard.sh` → `Start-Dashboard.ps1` + tests
- [ ] `release/draft.sh` → `New-ReleaseDraft.ps1` + tests
- [ ] `release/signoff.sh` → `Request-Signoff.ps1` + tests

#### Acceptance Criteria
- [ ] `ostwin init ~/new-project` scaffolds via PowerShell
- [ ] `ostwin dashboard` starts FastAPI via PowerShell launcher
- [ ] Release draft generates RELEASE.md from completed war-rooms
- [ ] All new scripts have Pester tests with >80% path coverage

#### Tasks
- [ ] TASK-005 — Port init.sh to Initialize-Project.ps1
- [ ] TASK-006 — Port dashboard.sh to Start-Dashboard.ps1
- [ ] TASK-007 — Port release/draft.sh to New-ReleaseDraft.ps1
- [ ] TASK-008 — Port release/signoff.sh to Request-Signoff.ps1

---

## Configuration

```json
{
    "plan_id": "001-bash-to-powershell",
    "priority": 1,
    "goals": {
        "definition_of_done": [
            "config.sh ported to Get-Config.ps1 with Pester tests",
            "health.sh ported to Test-Health.ps1 with Pester tests",
            "stop.sh ported to Stop-Manager.ps1 with Pester tests",
            "logs.sh ported to Get-Logs.ps1 with Pester tests",
            "init.sh ported to Initialize-Project.ps1 with Pester tests",
            "dashboard.sh ported to Start-Dashboard.ps1 with Pester tests",
            "release/draft.sh ported to New-ReleaseDraft.ps1 with Pester tests",
            "release/signoff.sh ported to Request-Signoff.ps1 with Pester tests"
        ],
        "acceptance_criteria": [
            "ostwin CLI dispatches all commands to PowerShell scripts",
            "All new scripts have Pester tests",
            "Old bash scripts can be deleted after port"
        ]
    }
}
```
