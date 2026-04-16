# Agent OS — Unified Negotiation Rejection Integration Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
    $script:StartPlan = Join-Path $script:agentsDir "plan" "Start-Plan.ps1"
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
}

Describe "Unified Plan Negotiation Rejection" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-unified-reject-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
        $script:warRoomsDir = Join-Path $script:projectDir ".war-rooms"
        
        # Create necessary subdirectories
        $subDirs = @("plan", "war-rooms", "channel", "lib", "roles/manager")
        foreach ($sd in $subDirs) {
            New-Item -ItemType Directory -Path (Join-Path $script:projectDir ".agents/$sd") -Force | Out-Null
        }
        
        # Copy real scripts that we need in the project dir to avoid falling back to installDir
        Copy-Item -Path (Join-Path $script:agentsDir "war-rooms/New-WarRoom.ps1") -Destination (Join-Path $script:projectDir ".agents/war-rooms/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Post-Message.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Wait-ForMessage.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Read-Messages.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "plan/Build-DependencyGraph.ps1") -Destination (Join-Path $script:projectDir ".agents/plan/")
        Copy-Item -Path (Join-Path $script:agentsDir "plan/Test-DependenciesReady.ps1") -Destination (Join-Path $script:projectDir ".agents/plan/")
        Copy-Item -Path (Join-Path $script:agentsDir "plan/Update-Progress.ps1") -Destination (Join-Path $script:projectDir ".agents/plan/")
        # Copy all lib modules (Utils.psm1 imports Lock.psm1, Start-Plan.ps1 imports PlanParser.psm1)
        Get-ChildItem -Path (Join-Path $script:agentsDir "lib") -Filter "*.psm1" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $script:projectDir ".agents/lib/")
        }
        Copy-Item -Path (Join-Path $script:agentsDir "roles/manager/Start-ManagerLoop.ps1") -Destination (Join-Path $script:projectDir ".agents/roles/manager/")
        
        # We need a dummy config.json too
        '{"manager":{"poll_interval_seconds":1,"max_engineer_retries":1,"max_concurrent_rooms":5,"unified_plan_negotiation":true}}' | Out-File (Join-Path $script:projectDir ".agents/config.json") -Encoding utf8
        
        $script:planFile = Join-Path $TestDrive "test-plan-unified-reject.md"
        $lines = @(
            "# Plan: Unified Reject Test",
            "",
            "## Epics",
            "",
            "## EPIC-001 - Task to be rejected",
            "",
            "* Bullet 1",
            "* Bullet 2",
            "* Bullet 3",
            "* Bullet 4",
            "* Bullet 5",
            "",
            "#### Definition of Done",
            "- [ ] D1", "- [ ] D2", "- [ ] D3", "- [ ] D4", "- [ ] D5", "- [ ] D6", "- [ ] D7", "- [ ] D8", "- [ ] D9", "- [ ] D10",
            "",
            "#### Acceptance Criteria",
            "- [ ] A1", "- [ ] A2", "- [ ] A3", "- [ ] A4", "- [ ] A5", "- [ ] A6", "- [ ] A7", "- [ ] A8", "- [ ] A9", "- [ ] A10"
        )
        $lines | Out-File $script:planFile -Encoding utf8
    }

    It "handles plan-reject by resetting room-000 to pending" -Skip:$true -ForEach @{reason = "Flaky: externally-set review status races with manager loop's internal state"} {
        $env:WARROOMS_DIR = $script:warRoomsDir

        # Run Start-Plan in unified mode
        $job = Start-Job -ScriptBlock {
            param($StartPlan, $PlanFile, $ProjectDir, $WarRoomsDir)
            $env:WARROOMS_DIR = $WarRoomsDir
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Review -Unified
        } -ArgumentList $script:StartPlan, $script:planFile, $script:projectDir, $script:warRoomsDir

        # Wait for room-000
        $room000 = Join-Path $script:warRoomsDir "room-000"
        $status000 = Join-Path $room000 "status"
        
        $maxWaits = 90
        $waited = 0
        while (-not (Test-Path $status000) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        if (-not (Test-Path $status000)) { throw "room-000 not created" }

        # Wait for manager to pick it up (developing or review)
        $waited = 0
        $s = ""
        while ($s -ne "developing" -and $s -ne "review" -and $waited -lt $maxWaits) {
            $s = (Get-Content $status000 -Raw).Trim()
            Start-Sleep -Milliseconds 500
            $waited++
        }

        # Change status to review so manager checks for plan-reject/plan-approve
        "review" | Out-File -FilePath $status000 -Encoding utf8 -NoNewline

        # Give the manager loop time to detect the new status before posting the message
        Start-Sleep -Seconds 2

        # Post plan-reject
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-reject" -Ref "PLAN-REVIEW" -Body "Rejected for more detail" | Out-Null
        
        # Wait for status to become manager-triage (handoff)
        $waited = 0
        $s = (Get-Content $status000 -Raw).Trim()
        while ($s -ne "manager-triage" -and $waited -lt $maxWaits) {
            $s = (Get-Content $status000 -Raw).Trim()
            Start-Sleep -Milliseconds 500
            $waited++
        }
        $s | Should -Be "manager-triage"

        # Wait for manager-triage to process it and set back to pending (after expansion)
        $waited = 0
        while ($s -ne "pending" -and $waited -lt $maxWaits) {
            $s = (Get-Content $status000 -Raw).Trim()
            Start-Sleep -Milliseconds 500
            $waited++
        }
        $s | Should -Be "pending"
        
        # Cleanup
        Stop-Job $job
        Remove-Job $job
    }
}
