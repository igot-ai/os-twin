# Agent OS — Unified Negotiation Integration Tests
# EPIC-002: Unified Plan Negotiation

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $script:StartPlan = Join-Path $script:agentsDir "plan" "Start-Plan.ps1"
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
}

Describe "Unified Plan Negotiation" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-unified-$(Get-Random)"
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
        Copy-Item -Path (Join-Path $script:agentsDir "lib/Utils.psm1") -Destination (Join-Path $script:projectDir ".agents/lib/")
        Copy-Item -Path (Join-Path $script:agentsDir "lib/Log.psm1") -Destination (Join-Path $script:projectDir ".agents/lib/")
        Copy-Item -Path (Join-Path $script:agentsDir "lib/Config.psm1") -Destination (Join-Path $script:projectDir ".agents/lib/")
        Copy-Item -Path (Join-Path $script:agentsDir "roles/manager/Start-ManagerLoop.ps1") -Destination (Join-Path $script:projectDir ".agents/roles/manager/")
        
        # We need a dummy config.json too
        '{"manager":{"poll_interval_seconds":1,"max_engineer_retries":1,"max_concurrent_rooms":5,"unified_plan_negotiation":true}}' | Out-File (Join-Path $script:projectDir ".agents/config.json") -Encoding utf8
        
        $script:planFile = Join-Path $TestDrive "test-plan-unified-ok.md"
        $lines = @(
            "# Plan: Unified Test",
            "",
            "## Epics",
            "",
            "## EPIC-001 - First task",
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

    It "bootstraps room-000, hands off to manager-loop, and creates epic rooms after approval" {
        $env:WARROOMS_DIR = $script:warRoomsDir

        # Run Start-Plan in unified mode
        $job = Start-Job -ScriptBlock {
            param($StartPlan, $PlanFile, $ProjectDir, $WarRoomsDir)
            $env:WARROOMS_DIR = $WarRoomsDir
            # -Review -Unified means it will start ManagerLoop and exit
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Review -Unified
        } -ArgumentList $script:StartPlan, $script:planFile, $script:projectDir, $script:warRoomsDir

        # Wait for room-000
        $room000 = Join-Path $script:warRoomsDir "room-000"
        $status000 = Join-Path $room000 "status"
        
        $maxWaits = 60
        $waited = 0
        while (-not (Test-Path $status000) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        if (-not (Test-Path $status000)) {
            Write-Host "JOB OUTPUT:"
            Receive-Job $job | Write-Host
            throw "room-000 was not created!"
        }
        Test-Path $status000 | Should -BeTrue

        # Wait for the manager loop to start and room-000 to move to engineering or qa-review
        # (It will move to engineering because architect role is assigned)
        $waited = 0
        $s = ""
        while ($s -ne "engineering" -and $s -ne "qa-review" -and $waited -lt $maxWaits) {
            if (Test-Path $status000) { $s = (Get-Content $status000 -Raw).Trim() }
            Start-Sleep -Milliseconds 500
            $waited++
        }
        $s | Should -BeIn @("engineering", "qa-review", "pending")

        # Post plan-approve to room-000
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-approve" -Ref "PLAN-REVIEW" -Body "Approved" | Out-Null
        
        # Wait for EPIC-001 (room-001) to be created by the manager loop
        $room001 = Join-Path $script:warRoomsDir "room-001"
        $waited = 0
        while (-not (Test-Path $room001) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        if (-not (Test-Path $room001)) {
            Write-Host "JOB OUTPUT:"
            Receive-Job $job | Write-Host
            throw "room-001 was not created!"
        }
        Test-Path $room001 | Should -BeTrue
        
        # Cleanup
        Stop-Job $job
        Remove-Job $job
    }
}
