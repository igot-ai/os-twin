# Agent OS — Start-Plan Pester Tests

BeforeAll {
    $script:StartPlan = Join-Path $PSScriptRoot "Start-Plan.ps1"
    $script:NewPlan = Join-Path $PSScriptRoot "New-Plan.ps1"
}

Describe "Start-Plan" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:projectDir ".agents") -Force | Out-Null
    }

    Context "Plan parsing" {
        BeforeEach {
            $script:planFile = Join-Path $TestDrive "test-plan.md"
            @"
# Plan: Auth System

> Created: 2026-01-01T00:00:00Z
> Status: draft

---

## Goal

Implement JWT authentication

## Epics

### EPIC-001 — JWT Authentication

#### Definition of Done
- [ ] JWT token generation working
- [ ] Token validation middleware
- [ ] Refresh token support

#### Acceptance Criteria
- [ ] POST /login returns valid JWT
- [ ] Protected routes reject invalid tokens

#### Tasks
- [ ] TASK-001 — Design auth flow
- [ ] TASK-002 — Implement JWT generation
- [ ] TASK-003 — Write auth middleware
- [ ] TASK-004 — Add tests

---

## Configuration

```json
{
    "plan_id": "plan-auth-001",
    "priority": 1,
    "goals": {
        "definition_of_done": ["JWT working", "Tests passing"],
        "acceptance_criteria": ["Login returns 200"]
    }
}
```
"@ | Out-File $script:planFile -Encoding utf8
        }

        It "parses the plan in dry-run mode without errors" {
            $output = & $script:StartPlan -PlanFile $script:planFile `
                                          -ProjectDir $script:projectDir -DryRun 2>&1
            # Should not throw
            $LASTEXITCODE | Should -Not -Be 1
        }

        It "detects EPIC-001" {
            $output = & $script:StartPlan -PlanFile $script:planFile `
                                          -ProjectDir $script:projectDir -DryRun
            ($output -join "`n") | Should -Match "EPIC-001"
        }

        It "shows the number of war-rooms to create" {
            $output = & $script:StartPlan -PlanFile $script:planFile `
                                          -ProjectDir $script:projectDir -DryRun
            ($output -join "`n") | Should -Match "War-rooms to create: 1"
        }

        It "does not create rooms in dry-run mode" {
            & $script:StartPlan -PlanFile $script:planFile `
                                -ProjectDir $script:projectDir -DryRun

            $warRooms = Join-Path $script:projectDir ".war-rooms"
            if (Test-Path $warRooms) {
                $rooms = Get-ChildItem $warRooms -Directory -Filter "room-*" -ErrorAction SilentlyContinue
                $rooms.Count | Should -Be 0
            }
        }
    }

    Context "Multi-epic plan" {
        BeforeEach {
            $script:multiPlan = Join-Path $TestDrive "multi-plan.md"
            @"
# Plan: Full System

## Epics

### EPIC-001 — Authentication

#### Definition of Done
- [ ] Login working

#### Acceptance Criteria
- [ ] POST /login returns 200

### EPIC-002 — Dashboard

#### Definition of Done
- [ ] Dashboard renders

#### Acceptance Criteria
- [ ] GET /dashboard returns HTML
"@ | Out-File $script:multiPlan -Encoding utf8
        }

        It "detects multiple epics" {
            $output = & $script:StartPlan -PlanFile $script:multiPlan `
                                          -ProjectDir $script:projectDir -DryRun
            ($output -join "`n") | Should -Match "War-rooms to create: 2"
            ($output -join "`n") | Should -Match "EPIC-001"
            ($output -join "`n") | Should -Match "EPIC-002"
        }
    }

    Context "Task-only plan" {
        BeforeEach {
            $script:taskPlan = Join-Path $TestDrive "task-plan.md"
            @"
# Plan: Small fixes

## Tasks
- [ ] TASK-001 — Fix login button
- [ ] TASK-002 — Update footer text
- [ ] TASK-003 — Add favicon
"@ | Out-File $script:taskPlan -Encoding utf8
        }

        It "parses standalone tasks" {
            $output = & $script:StartPlan -PlanFile $script:taskPlan `
                                          -ProjectDir $script:projectDir -DryRun
            ($output -join "`n") | Should -Match "War-rooms to create: 3"
        }
    }

    Context "Error handling" {
        It "fails when plan file doesn't exist" {
            { & $script:StartPlan -PlanFile "/nonexistent/plan.md" `
                                  -ProjectDir $script:projectDir -DryRun } 2>&1 |
                Should -Match "not found"
        }

        It "fails when plan has no epics or tasks" {
            $emptyPlan = Join-Path $TestDrive "empty-plan.md"
            "# Empty plan`nNo epics here." | Out-File $emptyPlan -Encoding utf8

            { & $script:StartPlan -PlanFile $emptyPlan `
                                  -ProjectDir $script:projectDir -DryRun } 2>&1 |
                Should -Match "No epics or tasks"
        }
    }

    Context "Plan ID extraction" {
        It "extracts plan_id from embedded JSON config" {
            $planWithId = Join-Path $TestDrive "plan-with-id.md"
            @"
# Plan: Test

### EPIC-001 — Test

#### Definition of Done
- [ ] Done

```json
{
    "plan_id": "my-custom-plan-123"
}
```
"@ | Out-File $planWithId -Encoding utf8

            $output = & $script:StartPlan -PlanFile $planWithId `
                                          -ProjectDir $script:projectDir -DryRun
            ($output -join "`n") | Should -Match "my-custom-plan-123"
        }
    }
}
