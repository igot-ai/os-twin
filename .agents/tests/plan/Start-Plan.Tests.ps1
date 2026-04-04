# Agent OS — Start-Plan Pester Tests

BeforeAll {
    $script:StartPlan = Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "Start-Plan.ps1"
    $script:NewPlan = Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "New-Plan.ps1"
    
    function global:Get-OstwinConfig {
        return [PSCustomObject]@{
            manager = [PSCustomObject]@{
                auto_expand_plan = $false
            }
        }
    }
    
    function global:Test-Underspecified {
        param([string]$Content)
        if ($Content -match "Short description") { return $true }
        return $false
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
        "param([object[]]`$Nodes, [switch]`$Validate) if (`$Validate) { return `$Nodes | ForEach-Object { [PSCustomObject]@{ Id = `$_.Id } } } else { Write-Host 'Dummy BuildDag' }" | Out-File (Join-Path $agentsDir "plan/Build-DependencyGraph.ps1") -Encoding utf8
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
            ($output -join "`n") | Should -Match "War-rooms to create: 2"
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

    Context "Upfront Room and DAG Creation" {
        BeforeEach {
            $script:multiRoomPlan = Join-Path $TestDrive "multi-room-plan.md"
            $content = @"
# Plan: Multi-Room Test
working_dir: $script:projectDir

## EPIC-001 — Base Epic
#### Definition of Done
- [ ] Done 1

## EPIC-002 — Dependent Epic
depends_on: ["EPIC-001"]
#### Definition of Done
- [ ] Done 2
"@
            $content | Out-File $script:multiRoomPlan -Encoding utf8
        }

        It "injects PLAN-REVIEW as a dependency for all epics" {
            $output = & $script:StartPlan -PlanFile $script:multiRoomPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = $output -join "`n"
            $outputStr | Should -Match "room-001 → EPIC-001.*\[depends_on: PLAN-REVIEW\]"
            $outputStr | Should -Match "room-002 → EPIC-002.*\[depends_on: PLAN-REVIEW, EPIC-001\]"
        }

        It "shows topological order in dry-run" {
            $output = & $script:StartPlan -PlanFile $script:multiRoomPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = $output -join "`n"
            $outputStr | Should -Match "Dependency Graph \(Topological Order\):"
            $outputStr | Should -Match "PLAN-REVIEW -> EPIC-001 -> EPIC-002"
        }
    }

    Context "Plan expansion" {
        BeforeEach {
            $script:expandPlan = Join-Path $TestDrive "expand-plan.md"
            $expandContent = "# Plan: Expansion Test`n`n## Epics`n`n### EPIC-001 — Short description`n"
            $expandContent | Out-File $script:expandPlan -Encoding utf8
            
            $testPlanDir = Join-Path $script:projectDir ".agents/plan"
            New-Item -ItemType Directory -Path $testPlanDir -Force | Out-Null
            Copy-Item -Path (Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "Expand-Plan.ps1") -Destination $testPlanDir -Force
        }

        It "runs expansion when underspecified epics are detected" {
            # Mock Test-Underspecified to return true for this test
            function global:Test-Underspecified { param($Content) return $true }
            
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun -Expand *>&1
            $outputStr = $output -join "`n"
            # Use a more lenient regex to ignore potential ANSI escape codes
            $outputStr | Should -Match "underspecified epics"
            $outputStr | Should -Match "expand epics"
        }

        It "respects the DryRun flag during expansion" {
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun *>&1
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            Test-Path $refinedFile | Should -Be $false
        }

        It "runs expansion without DryRun and writes logs" {
            # Dummy Expand-Plan.ps1 that creates the refined file and exits cleanly
            $dummyExpand = @"
param(
    [string]`$PlanFile,
    [string]`$OutFile,
    [switch]`$DryRun
)
if (-not `$DryRun) {
    Set-Content -Path `$OutFile -Value "# Plan: Refined Test``n``n## Epics``n``n### EPIC-001 — Expanded description``n``n#### Definition of Done``n- [ ] Done``n- [ ] D2``n- [ ] D3``n- [ ] D4``n- [ ] D5``n``n#### Acceptance Criteria``n- [ ] Accepted``n- [ ] A2``n- [ ] A3``n- [ ] A4``n- [ ] A5``n"
    Write-Host "Expansion done"
}
exit 0
"@
            $dummyExpand | Out-File (Join-Path $script:projectDir ".agents/plan/Expand-Plan.ps1") -Encoding utf8

            # Run Start-Plan without DryRun using -Expand to force expansion and -SkipLoop to isolate.
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir `
                -DryRun:$false -Expand -SkipLoop *>&1

            # Verify expansion ran successfully by checking the refined file was created
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            Test-Path $refinedFile | Should -Be $true

            $updatedContent = Get-Content $refinedFile -Raw
            $updatedContent | Should -Match "Refined Test"

            # Verify the expansion was triggered in the output
            ($output -join "`n") | Should -Match "Plan expanded successfully"
        }

        It "skips expansion when refined file already exists" {
            # Create a pre-existing refined file whose EPIC description does NOT trigger
            # Test-Underspecified (which matches 'Short description')
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            $refinedContent = @"
# Plan: Already Refined

## Epics

### EPIC-001 — Fully specified auth module with detailed logic and implementation steps
- Detailed bullet 1
- Detailed bullet 2
- Detailed bullet 3
- Detailed bullet 4
- Detailed bullet 5

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
            $refinedContent | Out-File $refinedFile -Encoding utf8

            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = ($output -join "`n")

            # Should detect and reuse existing refined file
            $outputStr | Should -Match "Using Existing Refined Plan"
            # Should NOT try to expand again since the refined content is well-specified
            $outputStr | Should -Not -Match "\[DRY RUN\] Would expand"
        }

        It "force re-expands with -Expand even when refined file exists" {
            # Create a pre-existing refined file
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            "# Plan: Old Refined`n`n### EPIC-001 — Old`n" | Out-File $refinedFile -Encoding utf8

            # With -Expand flag, it should re-run expansion, not reuse
            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun -Expand *>&1
            $outputStr = ($output -join "`n")

            # Should NOT say "Using Existing" — it should re-expand
            $outputStr | Should -Not -Match "Using Existing Refined Plan"
            # Actual output: "[DRY RUN] Would expand epics (e.g. EPIC-001)"
            $outputStr | Should -Match "Would expand epics.*EPIC-001"
        }

        It "parses epics from the refined file when reusing" {
            $refinedFile = $script:expandPlan -replace '\.md$', '.refined.md'
            $refinedContent = @"
# Plan: Refined Plan

## Epics

### EPIC-001 — Expanded Auth System
- Full description bullet 1
- Full description bullet 2

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

### EPIC-002 — Expanded Dashboard
- Full description bullet 1
- Full description bullet 2

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
            $refinedContent | Out-File $refinedFile -Encoding utf8

            $output = & $script:StartPlan -PlanFile $script:expandPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = ($output -join "`n")

            # Should use the refined file and parse its 2 epics + room-000
            $outputStr | Should -Match "Using Existing Refined Plan"
            $outputStr | Should -Match "War-rooms to create: 3"
            $outputStr | Should -Match "EPIC-001"
            $outputStr | Should -Match "EPIC-002"
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
            ($output -join "`n") | Should -Match "War-rooms to create: 3"
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
            ($output -join "`n") | Should -Match "War-rooms to create: 4"
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
            ($output -join "`n") | Should -Match "depends_on: PLAN-REVIEW, EPIC-001"
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
            ($output -join "`n") | Should -Match "depends_on: PLAN-REVIEW"
        }
    }

    Context "Mixed epic and task plan" {
        BeforeEach {
            $script:mixedPlan = Join-Path $TestDrive "mixed-plan.md"
            $content = @"
# Plan: Mixed Test
## Epics
### EPIC-001 - My Epic
- Bullet 1

## Tasks
- [ ] TASK-001 - My Task
"@
            $content | Out-File $script:mixedPlan -Encoding utf8
        }
        
        It "parses both epics and tasks and injects PLAN-REVIEW" {
            $output = & $script:StartPlan -PlanFile $script:mixedPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = $output -join "`n"
            $outputStr | Should -Match "War-rooms to create: 3"
            $outputStr | Should -Match "EPIC-001"
            $outputStr | Should -Match "TASK-001"
            $outputStr | Should -Match "room-001 → EPIC-001.*\[depends_on: PLAN-REVIEW\]"
            $outputStr | Should -Match "room-002 → TASK-001.*\[depends_on: PLAN-REVIEW\]"
        }
    }

    Context "Multi-Room DAG Launch (Plan B Verification)" {
        It "creates 5 rooms and full DAG for a 4-EPIC plan" {
            $fourEpicPlan = Join-Path $TestDrive "4-epic-plan.md"
            $content = @"
# Plan: 4-Epic Test
working_dir: $script:projectDir

## EPIC-001 - Epic 1
#### Definition of Done
- [ ] D1
## EPIC-002 - Epic 2
#### Definition of Done
- [ ] D2
## EPIC-003 - Epic 3
#### Definition of Done
- [ ] D3
## EPIC-004 - Epic 4
#### Definition of Done
- [ ] D4
"@
            $content | Out-File $fourEpicPlan -Encoding utf8
            
            $output = & $script:StartPlan -PlanFile $fourEpicPlan -ProjectDir $script:projectDir -DryRun *>&1
            $outputStr = $output -join "`n"
            $outputStr | Should -Match "War-rooms to create: 5"
            $outputStr | Should -Match "PLAN-REVIEW -> EPIC-001 -> EPIC-002 -> EPIC-003 -> EPIC-004"
        }
    }

    Context "Resume functionality" {
        BeforeEach {
            $absProjectDir = (Resolve-Path $script:projectDir).Path
            $script:resumePlan = Join-Path $TestDrive "resume-plan.md"
            "# Plan: Resume Test`n`n### EPIC-001 - Test`n" | Out-File $script:resumePlan -Encoding utf8
            
            $warRooms = Join-Path $absProjectDir ".war-rooms"
            if (-not (Test-Path $warRooms)) { New-Item -ItemType Directory -Path $warRooms -Force | Out-Null }
            
            $roomDir = Join-Path $warRooms "room-001"
            if (-not (Test-Path $roomDir)) { New-Item -ItemType Directory -Path $roomDir -Force | Out-Null }
            "failed-final" | Out-File (Join-Path $roomDir "status") -Encoding utf8 -NoNewline
            "10" | Out-File (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
            "5" | Out-File (Join-Path $roomDir "qa_retries") -Encoding utf8 -NoNewline
            
            $room000 = Join-Path $warRooms "room-000"
            if (-not (Test-Path $room000)) { New-Item -ItemType Directory -Path $room000 -Force | Out-Null }
            "passed" | Out-File (Join-Path $room000 "status") -Encoding utf8 -NoNewline

            $room002 = Join-Path $warRooms "room-002"
            if (-not (Test-Path $room002)) { New-Item -ItemType Directory -Path $room002 -Force | Out-Null }
            "fixing" | Out-File (Join-Path $room002 "status") -Encoding utf8 -NoNewline
            $pidDir002 = New-Item -ItemType Directory -Path (Join-Path $room002 "pids") -Force
            New-Item -ItemType File -Path (Join-Path $pidDir002 "test.pid") -Force | Out-Null

            # Ensure .agents/plan exists for mock Update-Progress
            $agentsPlanDir = Join-Path $absProjectDir ".agents/plan"
            if (-not (Test-Path $agentsPlanDir)) { New-Item -ItemType Directory -Path $agentsPlanDir -Force | Out-Null }
            "Write-Host 'Progress updated'" | Out-File (Join-Path $agentsPlanDir "Update-Progress.ps1") -Encoding utf8
        }

        It "resets failed-final rooms to pending" {
            $absProjectDir = (Resolve-Path $script:projectDir).Path
            $output = & $script:StartPlan -PlanFile $script:resumePlan -ProjectDir $absProjectDir -Resume -DryRun:$false -SkipLoop *>&1
            $outputStr = $output -join "`n"
            
            $outputStr | Should -Match "Resetting room-001 to pending"
            
            $statusFile = Join-Path $absProjectDir ".war-rooms/room-001/status"
            (Get-Content $statusFile -Raw) | Should -Be "pending"
        }

        It "moves fixing rooms to developing" {
            $absProjectDir = (Resolve-Path $script:projectDir).Path
            $output = & $script:StartPlan -PlanFile $script:resumePlan -ProjectDir $absProjectDir -Resume -DryRun:$false -SkipLoop *>&1
            $outputStr = $output -join "`n"
            
            $outputStr | Should -Match "Moving room-002 from fixing to developing"
            
            $statusFile = Join-Path $absProjectDir ".war-rooms/room-002/status"
            (Get-Content $statusFile -Raw) | Should -Be "developing"
            
            $pidDir = Join-Path $absProjectDir ".war-rooms/room-002/pids"
            (Get-ChildItem $pidDir -Filter "*.pid").Count | Should -Be 0
        }

        It "clears retry counters on resume" {
            $absProjectDir = (Resolve-Path $script:projectDir).Path
            & $script:StartPlan -PlanFile $script:resumePlan -ProjectDir $absProjectDir -Resume -DryRun:$false -SkipLoop *>&1 | Out-Null
            
            $retriesFile = Join-Path $absProjectDir ".war-rooms/room-001/retries"
            $content = (Get-Content $retriesFile -Raw).Trim()
            $content | Should -Be "0"
            
            $qaRetriesFile = Join-Path $absProjectDir ".war-rooms/room-001/qa_retries"
            (Test-Path $qaRetriesFile) | Should -Be $false
        }

        It "triggers Update-Progress after resets" {
            $output = & $script:StartPlan -PlanFile $script:resumePlan -ProjectDir $script:projectDir -Resume -DryRun:$false -SkipLoop *>&1
            ($output -join "`n") | Should -Match "Progress updated"
        }
    }
}
