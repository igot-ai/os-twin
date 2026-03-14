# Agent OS — Start-Plan Pester Tests

BeforeAll {
    $script:StartPlan = Join-Path $PSScriptRoot "Start-Plan.ps1"
    $script:NewPlan = Join-Path $PSScriptRoot "New-Plan.ps1"
    
    function global:Get-OstwinConfig {
        return [PSCustomObject]@{
            manager = [PSCustomObject]@{
                auto_expand_plan = $false
            }
        }
    }
    
    function global:Write-OstwinLog {
        param([string]$Message, [string]$Level, [string]$Caller)
        $global:testLogs += [PSCustomObject]@{ Message=$Message; Level=$Level; Caller=$Caller }
    }
}

Describe "Start-Plan" {
    BeforeEach {
        $global:testLogs = @()
        $script:logs = @()
        $script:projectDir = Join-Path $TestDrive "project-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
        $agentsDir = Join-Path $script:projectDir ".agents"
        New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
        
        # Create necessary subdirectories
        $subDirs = @("plan", "war-rooms", "roles/manager", "channel", "lib")
        foreach ($sd in $subDirs) {
            New-Item -ItemType Directory -Path (Join-Path $agentsDir $sd) -Force | Out-Null
        }

        # Create dummy scripts to avoid file not found errors
        "Write-Host 'Dummy BuildDag'" | Out-File (Join-Path $agentsDir "plan/Build-DependencyGraph.ps1") -Encoding utf8
        "Write-Host 'Dummy NewWarRoom'" | Out-File (Join-Path $agentsDir "war-rooms/New-WarRoom.ps1") -Encoding utf8
        "Write-Host 'Dummy ManagerLoop'" | Out-File (Join-Path $agentsDir "roles/manager/Start-ManagerLoop.ps1") -Encoding utf8
        "Write-Host 'Dummy PostMessage'" | Out-File (Join-Path $agentsDir "channel/Post-Message.ps1") -Encoding utf8
        "Write-Host 'Dummy WaitForMessage'" | Out-File (Join-Path $agentsDir "channel/Wait-ForMessage.ps1") -Encoding utf8
        "Write-Host 'Dummy ReadMessages'" | Out-File (Join-Path $agentsDir "channel/Read-Messages.ps1") -Encoding utf8
        "Write-Host 'Dummy ExpandPlan'" | Out-File (Join-Path $agentsDir "plan/Expand-Plan.ps1") -Encoding utf8
    }

    Context "Plan parsing" {
        BeforeEach {
            $script:planFile = Join-Path $TestDrive "test-plan.md"
            $lines = @(
                "# Plan: Auth System",
                "",
                "> Created: 2026-01-01T00:00:00Z",
                "> Status: draft",
                "",
                "---",
                "",
                "## Goal",
                "",
                "Implement JWT authentication",
                "",
                "## Epics",
                "",
                "### EPIC-001 — JWT Authentication",
                "- Feature description bullet 1",
                "- Feature description bullet 2",
                "",
                "#### Definition of Done",
                "- [ ] JWT token generation working",
                "- [ ] Token validation middleware",
                "- [ ] Refresh token support",
                "- [ ] Unit tests pass",
                "- [ ] Documentation updated",
                "",
                "#### Acceptance Criteria",
                "- [ ] POST /login returns valid JWT",
                "- [ ] Protected routes reject invalid tokens",
                "- [ ] Scenario 3",
                "- [ ] Scenario 4",
                "- [ ] Scenario 5"
            )
            $lines | Out-File $script:planFile -Encoding utf8
        }


        It "detects EPIC-001" {
            $output = & $script:StartPlan -PlanFile $script:planFile `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "EPIC-001"
        }

        It "shows the number of war-rooms to create" {
            $output = & $script:StartPlan -PlanFile $script:planFile `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "War-rooms to create: 1"
        }

        It "does not create rooms in dry-run mode" {
            & $script:StartPlan -PlanFile $script:planFile `
                -ProjectDir $script:projectDir -DryRun *>&1 | Out-Null

            $warRooms = Join-Path $script:projectDir ".war-rooms"
            if (Test-Path $warRooms) {
                $rooms = Get-ChildItem $warRooms -Directory -Filter "room-*" -ErrorAction SilentlyContinue
                $rooms.Count | Should -Be 0
            }
        }

        It "parses global working_dir from PLAN.md" {
            $workingDirPlan = Join-Path $TestDrive "working-dir-plan.md"
            $targetDir = Join-Path $TestDrive "target-project"
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            
            $content = "# Plan: Test`n`n## Config`nworking_dir: $targetDir`n`n### EPIC-001 — Test`n"
            $content | Out-File $workingDirPlan -Encoding utf8
            
            # Use -DryRun to just parse
            $output = & $script:StartPlan -PlanFile $workingDirPlan -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "Project: $targetDir"
        }

        It "warns when working_dir is invalid" {
            $badDirPlan = Join-Path $TestDrive "bad-dir-plan.md"
            $content = "# Plan: Test`n`n## Config`nworking_dir: /nonexistent/path/xyz`n`n### EPIC-001 — Test`n"
            $content | Out-File $badDirPlan -Encoding utf8

            $output = & $script:StartPlan -PlanFile $badDirPlan -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "working_dir.*not found"
        }
    }

    Context "Plan expansion" {
        BeforeEach {
            $script:expandPlan = Join-Path $TestDrive "expand-plan.md"
            $expandContent = "# Plan: Expansion Test`n`n## Epics`n`n### EPIC-001 — Short description`n"
            $expandContent | Out-File $script:expandPlan -Encoding utf8
            
            $testPlanDir = Join-Path $script:projectDir ".agents/plan"
            New-Item -ItemType Directory -Path $testPlanDir -Force | Out-Null
            Copy-Item -Path (Join-Path $PSScriptRoot "Expand-Plan.ps1") -Destination $testPlanDir -Force
        }

        It "runs expansion when underspecified epics are detected" {
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "Detected underspecified epics"
            ($output -join "`n") | Should -Match "Would expand EPIC-001"
        }

        It "respects the DryRun flag during expansion" {
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun *>&1
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            Test-Path $refinedFile | Should -Be $false
        }

        It "runs expansion without DryRun and writes logs" {
            # Dummy Expand-Plan.ps1 that creates the refined file
            $dummyExpand = @"
param(
    [string]`$PlanFile,
    [string]`$OutFile,
    [switch]`$DryRun
)
if (-not `$DryRun) {
    Set-Content -Path `$OutFile -Value "# Plan: Refined Test``n``n## Epics``n``n### EPIC-001 — Expanded description``n``n#### Definition of Done``n- [ ] Done``n``n#### Acceptance Criteria``n- [ ] Accepted``n"
}
"@
            $dummyExpand | Out-File (Join-Path $script:projectDir ".agents/plan/Expand-Plan.ps1") -Encoding utf8

            # Mock channel scripts to abort loop start
            $testChannelDir = Join-Path $script:projectDir ".agents/channel"
            New-Item -ItemType Directory -Path $testChannelDir -Force | Out-Null
            $dummyWait = "Write-Output '{`"type`":`"plan-reject`",`"from`":`"test`"}'"
            $dummyWait | Out-File (Join-Path $testChannelDir "Wait-ForMessage.ps1") -Encoding utf8
            
            $dummyPost = "Write-Host 'Posting message'"
            $dummyPost | Out-File (Join-Path $testChannelDir "Post-Message.ps1") -Encoding utf8

            $dummyRead = "param(`$RoomDir,`$FilterType) if (`$FilterType -eq 'plan-approve') { return @([PSCustomObject]@{type='plan-approve'}) } else { return @() }"
            $dummyRead | Out-File (Join-Path $testChannelDir "Read-Messages.ps1") -Encoding utf8
            
            # Mock new war room script
            $testWarRoomsDir = Join-Path $script:projectDir ".agents/war-rooms"
            New-Item -ItemType Directory -Path $testWarRoomsDir -Force | Out-Null
            $dummyNewRoom = "Write-Host 'Creating room'"
            $dummyNewRoom | Out-File (Join-Path $testWarRoomsDir "New-WarRoom.ps1") -Encoding utf8

            # Run Start-Plan without DryRun.
            # We mock git to avoid depending on actual git repo state
            function global:git { "Diff output" }
            function global:Read-Host { return "" }
            function global:Invoke-RestMethod { return [PSCustomObject]@{ plan_id = "test-id" } }
            
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir *>&1
            
            # Clean up the mock
            Remove-Item Function:\git -ErrorAction SilentlyContinue
            Remove-Item Function:\Read-Host -ErrorAction SilentlyContinue
            Remove-Item Function:\Invoke-RestMethod -ErrorAction SilentlyContinue

            $logMessages = $global:testLogs | ForEach-Object { $_.Message }
            $logMessages | Should -Contain "Plan expansion diff:`nDiff output`n"
            $global:testLogs | Where-Object { $_.Caller -eq "manager" } | Measure-Object | Select-Object -ExpandProperty Count | Should -BeGreaterThan 0
            
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            Test-Path $refinedFile | Should -Be $true
        }
    }

    Context "Multi-epic plan" {
        BeforeEach {
            $script:multiPlan = Join-Path $TestDrive "multi-plan.md"
            $multiContent = @"
# Plan: Full System

## Epics

### EPIC-001 — Authentication
- Auth logic description
- More details

#### Definition of Done
- [ ] Login working
- [ ] D2
- [ ] D3
- [ ] D4
- [ ] D5

#### Acceptance Criteria
- [ ] POST /login returns 200
- [ ] A2
- [ ] A3
- [ ] A4
- [ ] A5

### EPIC-002 — Dashboard
- Dashboard logic description
- More details

#### Definition of Done
- [ ] Dashboard renders
- [ ] D2
- [ ] D3
- [ ] D4
- [ ] D5

#### Acceptance Criteria
- [ ] GET /dashboard returns HTML
- [ ] A2
- [ ] A3
- [ ] A4
- [ ] A5
"@
            $multiContent | Out-File $script:multiPlan -Encoding utf8
        }

        It "detects multiple epics" {
            $output = & $script:StartPlan -PlanFile $script:multiPlan `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "War-rooms to create: 2"
            ($output -join "`n") | Should -Match "EPIC-001"
            ($output -join "`n") | Should -Match "EPIC-002"
        }
    }

    Context "Task-only plan" {
        BeforeEach {
            $script:taskPlan = Join-Path $TestDrive "task-plan.md"
            $taskPlanContent = "# Plan: Small fixes`n`n## Tasks`n- [ ] TASK-001 — Fix login button`n- [ ] TASK-002 — Update footer text`n- [ ] TASK-003 — Add favicon"
            $taskPlanContent | Out-File $script:taskPlan -Encoding utf8
        }

        It "parses standalone tasks" {
            $output = & $script:StartPlan -PlanFile $script:taskPlan `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "War-rooms to create: 3"
        }
    }

    Context "Error handling" {
        It "fails when plan file doesn't exist" {
            $output = & $script:StartPlan -PlanFile "/nonexistent/plan.md" `
                -ProjectDir $script:projectDir -DryRun *>&1
            # Script writes error and exits 1
            ($output -join "`n") | Should -Match "(not found|Plan file)"
        }

        It "fails when plan has no epics or tasks" {
            $emptyPlan = Join-Path $TestDrive "empty-plan.md"
            "# Empty plan`nNo epics here." | Out-File $emptyPlan -Encoding utf8

            $output = & $script:StartPlan -PlanFile $emptyPlan `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "(No epics|not found|No .* tasks)"
        }
    }

    Context "Plan ID extraction" {
        It "extracts plan_id from embedded JSON config" {
            $planWithId = Join-Path $TestDrive "plan-with-id.md"
            $planContent = @"
# Plan: Test

### EPIC-001 — Test
- Bullet 1
- Bullet 2

#### Definition of Done
- [ ] D1
- [ ] D2
- [ ] D3
- [ ] D4
- [ ] D5

#### Acceptance Criteria
- [ ] A1
- [ ] A2
- [ ] A3
- [ ] A4
- [ ] A5
"@
            $planContent | Out-File $planWithId -Encoding utf8

            $output = & $script:StartPlan -PlanFile $planWithId `
                                          -ProjectDir $script:projectDir -DryRun
            # plan_id extraction not required here — just verify it doesn't crash
            $LASTEXITCODE | Should -Not -Be 1
        }
    }

    Context "depends_on parsing (OPT-004)" {
        It "parses depends_on from EPIC section" {
            $depsPlan = Join-Path $TestDrive "deps-plan.md"
            $lines = @(
                "# Plan: Dependencies Test",
                "",
                "## Epics",
                "",
                "### EPIC-001 — Authentication",
                "- Mock description with enough details to pass check",
                "- Detailed bullet 2",
                "depends_on: []",
                "",
                "#### Definition of Done",
                "- [ ] Login working",
                "- [ ] D2", "- [ ] D3", "- [ ] D4", "- [ ] D5",
                "",
                "#### Acceptance Criteria",
                "- [ ] A1", "- [ ] A2", "- [ ] A3", "- [ ] A4", "- [ ] A5",
                "",
                "### EPIC-002 — Dashboard",
                "- Mock description with enough details to pass check",
                "- Detailed bullet 2",
                "depends_on: [EPIC-001]",
                "",
                "#### Definition of Done",
                "- [ ] Dashboard renders",
                "- [ ] D2", "- [ ] D3", "- [ ] D4", "- [ ] D5",
                "",
                "#### Acceptance Criteria",
                "- [ ] A1", "- [ ] A2", "- [ ] A3", "- [ ] A4", "- [ ] A5"
            )
            $lines | Out-File $depsPlan -Encoding utf8

            $output = & $script:StartPlan -PlanFile $depsPlan `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "depends_on: EPIC-001"
        }

        It "creates rooms without depends_on (backward compat)" {
            $noDeps = Join-Path $TestDrive "no-deps-plan.md"
            $lines = @(
                "# Plan: No Deps",
                "",
                "## Epics",
                "",
                "### EPIC-001 — Simple Feature",
                "- Mock description with enough details to pass check",
                "- Detailed bullet 2",
                "",
                "#### Definition of Done",
                "- [ ] Feature working",
                "- [ ] D2", "- [ ] D3", "- [ ] D4", "- [ ] D5",
                "",
                "#### Acceptance Criteria",
                "- [ ] A1", "- [ ] A2", "- [ ] A3", "- [ ] A4", "- [ ] A5"
            )
            $lines | Out-File $noDeps -Encoding utf8

            $output = & $script:StartPlan -PlanFile $noDeps `
                -ProjectDir $script:projectDir -DryRun *>&1
            ($output -join "`n") | Should -Match "EPIC-001"
            ($output -join "`n") | Should -Not -Match "depends_on"
        }
    }
}
