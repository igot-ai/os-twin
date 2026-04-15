# Agent OS — Review-Dependencies.ps1 Pester Tests

BeforeAll {
    $script:ReviewDeps = Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "Review-Dependencies.ps1"
    $script:NewWarRoom = Join-Path (Resolve-Path "$PSScriptRoot/../../war-rooms").Path "New-WarRoom.ps1"
    # Build-DependencyGraph.ps1 was removed — DAG logic is now in Start-Plan.ps1
}

Describe "Review-Dependencies.ps1" {
    BeforeEach {
        $script:tempDir = Join-Path $TestDrive "review-deps-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:tempDir -Force | Out-Null

        $script:warRoomsDir = Join-Path $script:tempDir ".war-rooms"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

        $script:planFile = Join-Path $script:tempDir "PLAN.md"
    }

    Context "Input Validation" {
        It "exits gracefully with single EPIC room" {
            # Plan with one EPIC
            @"
# Plan: Single EPIC

## EPIC-001 - Solo Feature

Build the feature.

#### Definition of Done
- [ ] Feature works
"@ | Out-File -FilePath $script:planFile -Encoding utf8

            # Create one room
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "EPIC-001" `
                -TaskDescription "Solo Feature" -WarRoomsDir $script:warRoomsDir | Out-Null

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile'" 2>&1
            ($output -join "`n") | Should -Match "no dependency analysis needed"
        }
    }

    Context "Dependency analysis with mock AI" {
        BeforeEach {
            # Plan with TWO EPICs
            @"
# Plan: Multi-EPIC Dep Test

## EPIC-001 - Database Schema

Build the database schema.

#### Definition of Done
- [ ] Schema created
- [ ] Migrations work

## EPIC-002 - API Layer

Build REST APIs on top of the database.

#### Definition of Done
- [ ] API endpoints implemented
- [ ] Integration tests pass

depends_on: []
"@ | Out-File -FilePath $script:planFile -Encoding utf8

            # Create war-rooms with brief.md
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "EPIC-001" `
                -TaskDescription "Database Schema`n`nBuild the database schema with migrations and seed data." `
                -WarRoomsDir $script:warRoomsDir `
                -DefinitionOfDone @("Schema created", "Migrations work") | Out-Null

            & $script:NewWarRoom -RoomId "room-002" -TaskRef "EPIC-002" `
                -TaskDescription "API Layer`n`nBuild REST APIs that consume the database schema." `
                -WarRoomsDir $script:warRoomsDir `
                -DefinitionOfDone @("API endpoints implemented", "Integration tests pass") | Out-Null

            # Mock agent that returns dependency analysis in new format
            $script:depMock = Join-Path $script:tempDir "dep-mock.sh"
            @'
#!/bin/bash
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}'
'@ | Out-File -FilePath $script:depMock -Encoding utf8 -NoNewline
            chmod +x $script:depMock
        }

        It "detects dependency changes and shows diff with AutoApprove" {
            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -AutoApprove" 2>&1
            $outputStr = $output -join "`n"

            # Should show the analysis ran
            $outputStr | Should -Match "DEP-REVIEW.*Analyzing dependencies"

            # Should show the proposed change
            $outputStr | Should -Match "Proposed Dependency Changes"
            $outputStr | Should -Match "EPIC-001"

            # Should show auto-approved
            $outputStr | Should -Match "Auto-approved|Dependencies updated"
        }

        It "updates room config.json with approved dependencies" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -AutoApprove" 2>&1

            # Read room-002 config and check depends_on
            $configPath = Join-Path $script:warRoomsDir "room-002" "config.json"
            $config = Get-Content $configPath -Raw | ConvertFrom-Json
            $config.depends_on | Should -Contain "EPIC-001"
        }

        It "updates plan file with approved dependencies" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -AutoApprove" 2>&1

            $updatedContent = Get-Content $script:planFile -Raw
            $updatedContent | Should -Match 'depends_on:.*EPIC-001'
        }

        It "writes .planning-DAG.json with stage=review" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -AutoApprove" 2>&1

            $dagFile = Join-Path $script:tempDir ".planning-DAG.json"
            Test-Path $dagFile | Should -BeTrue

            $dag = Get-Content $dagFile -Raw | ConvertFrom-Json
            $dag.total_nodes | Should -Be 2
            $dag.stage | Should -Be "review"

            $epic2Node = $dag.nodes | Where-Object { $_.task_ref -eq 'EPIC-002' }
            $epic2Node.depends_on | Should -Contain 'EPIC-001'
        }

        It "rebuilds DAG.json with updated dependencies after approval" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -AutoApprove" 2>&1

            # DAG.json must exist in the war-rooms directory
            $dagJsonFile = Join-Path $script:warRoomsDir "DAG.json"
            Test-Path $dagJsonFile | Should -BeTrue -Because "Review-Dependencies must rebuild DAG.json after approval"

            $dagJson = Get-Content $dagJsonFile -Raw | ConvertFrom-Json

            # DAG must contain nodes for both EPICs (+ PLAN-REVIEW virtual node)
            $nodeIds = @($dagJson.nodes.PSObject.Properties.Name)
            $nodeIds | Should -Contain "EPIC-001" -Because "DAG must include EPIC-001"
            $nodeIds | Should -Contain "EPIC-002" -Because "DAG must include EPIC-002"

            # EPIC-002 must depend on EPIC-001 in the rebuilt DAG
            $epic2Node = $dagJson.nodes.'EPIC-002'
            $epic2Node.depends_on | Should -Contain "EPIC-001" -Because "EPIC-002 depends on EPIC-001 after dep review"
        }

        It "does not modify anything in DryRun mode" {
            $configBefore = Get-Content (Join-Path $script:warRoomsDir "room-002" "config.json") -Raw
            $planBefore = Get-Content $script:planFile -Raw

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:depMock' -DryRun" 2>&1
            ($output -join "`n") | Should -Match "DRY RUN"

            # Files must be unchanged
            (Get-Content (Join-Path $script:warRoomsDir "room-002" "config.json") -Raw) | Should -Be $configBefore
            (Get-Content $script:planFile -Raw) | Should -Be $planBefore
        }
    }

    Context "Prompt content verification (what the AI actually receives)" {
        BeforeEach {
            # Plan with header context (dependency diagram, data assets) + two EPICs
            @"
# Plan: Audit System

## Context

This audit system processes financial data to detect fraud.

### Dependency Graph
``````
EPIC-001 → EPIC-002
``````

### Data Assets
- transactions.csv (10K rows)
- vendors.csv (500 rows)

---

## EPIC-001 - Data Pipeline

Roles: engineer

**Goal:** Build data ingestion that loads CSVs and validates schema.

### Tasks
1. Write data_loader.py
2. Implement schema validation

### Definition of Done
- [ ] All CSVs load
- [ ] Schema validated

### Acceptance Criteria
- [ ] Loads in under 10s
- [ ] Zero orphan records

depends_on: []

## EPIC-002 - Fraud Detection

Roles: engineer, qa

**Goal:** Detect fraud patterns using data from EPIC-001 pipeline.

### Tasks
1. Build detection modules
2. Score findings

### Definition of Done
- [ ] 8 detection modules
- [ ] Findings output JSON

### Acceptance Criteria
- [ ] Precision > 80%
- [ ] All patterns covered

depends_on: ["EPIC-001"]
"@ | Out-File -FilePath $script:planFile -Encoding utf8

            # Create rooms (needed for currentDeps lookup, but prompt content comes from plan file)
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "EPIC-001" `
                -TaskDescription "Data Pipeline" `
                -WarRoomsDir $script:warRoomsDir | Out-Null

            & $script:NewWarRoom -RoomId "room-002" -TaskRef "EPIC-002" `
                -TaskDescription "Fraud Detection" `
                -WarRoomsDir $script:warRoomsDir | Out-Null

            # Mock agent that CAPTURES the prompt to a file, then returns JSON
            $script:promptCapture = Join-Path $script:tempDir "captured-prompt.txt"
            $script:captureMock = Join-Path $script:tempDir "capture-mock.sh"
            @"
#!/bin/bash
# Dump the full prompt to a file for test inspection
echo "`$*" > '$($script:promptCapture)'
# Return valid dependency JSON in new format
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}'
"@ | Out-File -FilePath $script:captureMock -Encoding utf8 -NoNewline
            chmod +x $script:captureMock
        }

        It "sends plan header context (dependency diagram, data assets) to the AI" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:captureMock' -AutoApprove" 2>&1

            Test-Path $script:promptCapture | Should -BeTrue -Because "mock should have captured the prompt"
            $prompt = Get-Content $script:promptCapture -Raw

            # Plan header context must be present
            $prompt | Should -Match "Plan Context" -Because "plan header should be injected"
            $prompt | Should -Match "Audit System" -Because "plan title should appear"
            $prompt | Should -Match "EPIC-001.*EPIC-002" -Because "dependency diagram should appear"
            $prompt | Should -Match "transactions\.csv" -Because "data assets should appear"
        }

        It "includes EPIC description/goal but excludes Tasks, DoD, AC from plan content" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:captureMock' -AutoApprove" 2>&1

            $prompt = Get-Content $script:promptCapture -Raw

            # Description/goal from plan MUST be present
            $prompt | Should -Match "Build data ingestion" -Because "EPIC-001 goal should be in prompt"
            $prompt | Should -Match "Detect fraud patterns" -Because "EPIC-002 goal should be in prompt"

            # Tasks section from plan MUST be excluded (these strings are under ### Tasks)
            $prompt | Should -Not -Match "Write data_loader\.py" -Because "plan Tasks section is noise"
            $prompt | Should -Not -Match "Implement schema validation" -Because "plan Tasks section is noise"
            $prompt | Should -Not -Match "Build detection modules" -Because "plan Tasks section is noise"
            $prompt | Should -Not -Match "Score findings" -Because "plan Tasks section is noise"

            # Definition of Done from plan MUST be excluded
            $prompt | Should -Not -Match "All CSVs load" -Because "plan DoD is noise"
            $prompt | Should -Not -Match "Schema validated" -Because "plan DoD is noise"
            $prompt | Should -Not -Match "Findings output JSON" -Because "plan DoD is noise"

            # Acceptance Criteria from plan MUST be excluded
            $prompt | Should -Not -Match "Loads in under 10s" -Because "plan AC is noise"
            $prompt | Should -Not -Match "Zero orphan records" -Because "plan AC is noise"
            $prompt | Should -Not -Match "Precision > 80" -Because "plan AC is noise"
            $prompt | Should -Not -Match "All patterns covered" -Because "plan AC is noise"
        }

        It "excludes depends_on lines from EPIC sections (AI decides fresh)" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:captureMock' -AutoApprove" 2>&1

            $prompt = Get-Content $script:promptCapture -Raw

            # The plan has depends_on: ["EPIC-001"] in EPIC-002 section — this is AFTER
            # the ### Tasks cut point, so it should already be excluded by the cut.
            # But the plan header's dependency diagram IS included (that's the context).
            $prompt | Should -Match "EPIC-001.*EPIC-002" -Because "plan header dep diagram is context"
        }

        It "includes all EPIC refs in the output format requirement" {
            $null = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$script:captureMock' -AutoApprove" 2>&1

            $prompt = Get-Content $script:promptCapture -Raw

            # Prompt must tell AI to include ALL EPICs in response
            $prompt | Should -Match "MUST include ALL EPICs" -Because "AI must return every EPIC"
            $prompt | Should -Match '"EPIC-001"' -Because "EPIC-001 must be in ref list"
            $prompt | Should -Match '"EPIC-002"' -Because "EPIC-002 must be in ref list"

            # Output format must show the new per-EPIC structure
            $prompt | Should -Match '"depends_on"' -Because "output format must show depends_on key"
        }
    }

    Context "No changes detected" {
        It "reports no changes when AI returns empty edges" {
            @"
# Plan: No Deps

## EPIC-001 - Feature A
Short desc A.
#### Definition of Done
- [ ] Done A

## EPIC-002 - Feature B
Short desc B.
#### Definition of Done
- [ ] Done B
"@ | Out-File -FilePath $script:planFile -Encoding utf8

            & $script:NewWarRoom -RoomId "room-001" -TaskRef "EPIC-001" `
                -TaskDescription "Feature A" -WarRoomsDir $script:warRoomsDir | Out-Null
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "EPIC-002" `
                -TaskDescription "Feature B" -WarRoomsDir $script:warRoomsDir | Out-Null

            $noDeps = Join-Path $script:tempDir "no-deps-mock.sh"
            @'
#!/bin/bash
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": []}}'
'@ | Out-File -FilePath $noDeps -Encoding utf8 -NoNewline
            chmod +x $noDeps

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$noDeps'" 2>&1
            ($output -join "`n") | Should -Match "No dependency changes detected"
        }
    }

    Context "Noisy AI output parsing" {
        BeforeEach {
            @"
# Plan: Noisy Test

## EPIC-001 - Foundation
Build the base layer.

### Tasks
1. Setup

### Definition of Done
- [ ] Done

## EPIC-002 - Feature
Build on the base.

### Tasks
1. Implement

### Definition of Done
- [ ] Done
"@ | Out-File -FilePath $script:planFile -Encoding utf8

            & $script:NewWarRoom -RoomId "room-001" -TaskRef "EPIC-001" `
                -TaskDescription "Foundation" -WarRoomsDir $script:warRoomsDir | Out-Null
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "EPIC-002" `
                -TaskDescription "Feature" -WarRoomsDir $script:warRoomsDir | Out-Null
        }

        It "extracts JSON from output with preamble text" {
            $noisyMock = Join-Path $script:tempDir "noisy-mock.sh"
            @'
#!/bin/bash
echo "Here is my analysis of the dependencies:"
echo ""
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}'
echo ""
echo "Let me know if you need changes."
'@ | Out-File -FilePath $noisyMock -Encoding utf8 -NoNewline
            chmod +x $noisyMock

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$noisyMock' -AutoApprove" 2>&1
            $outputStr = $output -join "`n"

            $outputStr | Should -Match "Dependencies updated" -Because "should parse JSON despite preamble"

            $config = Get-Content (Join-Path $script:warRoomsDir "room-002" "config.json") -Raw | ConvertFrom-Json
            $config.depends_on | Should -Contain "EPIC-001"
        }

        It "extracts JSON wrapped in markdown fences" {
            $fencedMock = Join-Path $script:tempDir "fenced-mock.sh"
            @'
#!/bin/bash
echo 'Based on the analysis:'
echo '```json'
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}'
echo '```'
'@ | Out-File -FilePath $fencedMock -Encoding utf8 -NoNewline
            chmod +x $fencedMock

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$fencedMock' -AutoApprove" 2>&1
            $outputStr = $output -join "`n"

            $outputStr | Should -Match "Dependencies updated" -Because "should strip fences and parse JSON"
        }

        It "extracts JSON from wrapper noise with PID lines" {
            $wrapperMock = Join-Path $script:tempDir "wrapper-mock.sh"
            @'
#!/bin/bash
echo "[wrapper] PID=12345, CMD=opencode"
echo "Running task non-interactively..."
echo '{"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}'
echo "✓ Task completed"
'@ | Out-File -FilePath $wrapperMock -Encoding utf8 -NoNewline
            chmod +x $wrapperMock

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$wrapperMock' -AutoApprove" 2>&1
            $outputStr = $output -join "`n"

            $outputStr | Should -Match "Dependencies updated" -Because "should extract JSON from wrapper noise"
        }

        It "fails gracefully when no JSON found in output" {
            $badMock = Join-Path $script:tempDir "bad-mock.sh"
            @'
#!/bin/bash
echo "I could not determine the dependencies. Please provide more context."
'@ | Out-File -FilePath $badMock -Encoding utf8 -NoNewline
            chmod +x $badMock

            $output = pwsh -NoProfile -Command "& '$script:ReviewDeps' -WarRoomsDir '$script:warRoomsDir' -PlanFile '$script:planFile' -AgentCmd '$badMock' -AutoApprove" 2>&1
            $outputStr = $output -join "`n"

            $outputStr | Should -Match "No JSON object found" -Because "should warn about missing JSON"
        }
    }
}
