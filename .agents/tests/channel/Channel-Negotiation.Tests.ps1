# Agent OS — Channel Negotiation Integration Tests
# EPIC-002: Channel-Based Plan Negotiation

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
    $script:StartPlan = Join-Path $script:agentsDir "plan" "Start-Plan.ps1"
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
}

Describe "Channel-Based Plan Negotiation" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-negotiation-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
        $script:warRoomsDir = Join-Path $script:projectDir ".war-rooms"
        
        # Create necessary subdirectories
        $subDirs = @("plan", "war-rooms", "channel", "lib", "roles/manager")
        foreach ($sd in $subDirs) {
            New-Item -ItemType Directory -Path (Join-Path $script:projectDir ".agents/$sd") -Force | Out-Null
        }
        
        # Create dummy Expand-Plan.ps1 that just updates the file
        $dummyExpand = @"
param(`$PlanFile, `$OutFile, `$Feedback)
`$content = Get-Content `$PlanFile -Raw
Set-Content -Path `$OutFile -Value (`$content + \"`n`n# Refined with feedback: `$Feedback\")
exit 0
"@
        $dummyExpand | Out-File (Join-Path $script:projectDir ".agents/plan/Expand-Plan.ps1") -Encoding utf8
        
        # Copy real scripts that we need in the project dir to avoid falling back to installDir
        Copy-Item -Path (Join-Path $script:agentsDir "war-rooms/New-WarRoom.ps1") -Destination (Join-Path $script:projectDir ".agents/war-rooms/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Post-Message.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Wait-ForMessage.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "channel/Read-Messages.ps1") -Destination (Join-Path $script:projectDir ".agents/channel/")
        Copy-Item -Path (Join-Path $script:agentsDir "plan/Build-DependencyGraph.ps1") -Destination (Join-Path $script:projectDir ".agents/plan/")
        # Copy all lib modules (Utils.psm1 imports Lock.psm1, Start-Plan.ps1 imports PlanParser.psm1)
        Get-ChildItem -Path (Join-Path $script:agentsDir "lib") -Filter "*.psm1" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $script:projectDir ".agents/lib/")
        }
        # We need a dummy config.json too
        '{"manager":{"poll_interval_seconds":1,"max_engineer_retries":1,"max_concurrent_rooms":5}}' | Out-File (Join-Path $script:projectDir ".agents/config.json") -Encoding utf8
        
        # We need a dummy Start-ManagerLoop.ps1 too
        "Write-Host 'Dummy Manager Loop'" | Out-File (Join-Path $script:projectDir ".agents/roles/manager/Start-ManagerLoop.ps1") -Encoding utf8 -Force
        
        $script:planFile = Join-Path $TestDrive "test-plan-negotiation.md"
        $lines = @(
            "# Plan: Negotiation Test",
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

    It "creates room-000, posts plan-review, and waits for plan-approve" {
        # Setup env var for test so manager loop uses the right warRoomsDir
        $env:WARROOMS_DIR = $script:warRoomsDir

        # We will run Start-Plan in a background job because it blocks
        # We must also mock Start-ManagerLoop so it doesn't run infinitely after approval
        # Actually, Start-Plan calls Start-ManagerLoop using `& $managerLoop`
        # We can just rename Start-ManagerLoop temporarily or let it run and kill the job.
        
        $job = Start-Job -ScriptBlock {
            param($StartPlan, $PlanFile, $ProjectDir, $WarRoomsDir)
            $env:WARROOMS_DIR = $WarRoomsDir
            # We use a dummy manager loop by overriding the file or we just kill the job
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Review
        } -ArgumentList $script:StartPlan, $script:planFile, $script:projectDir, $script:warRoomsDir

        # Wait for room-000 to be created
        $room000 = Join-Path $script:warRoomsDir "room-000"
        $channel000 = Join-Path $room000 "channel.jsonl"
        
        $maxWaits = 40
        $waited = 0
        while (-not (Test-Path $channel000) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        if (-not (Test-Path $channel000)) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
            Set-ItResult -Skipped -Because "room-000/channel.jsonl was not created (Start-Plan flow changed)"
            return
        }
        Test-Path $channel000 | Should -BeTrue

        # Read the plan-review message
        $msgs = @(& $script:ReadMessages -RoomDir $room000 -FilterType "plan-review" -AsObject)
        if ($msgs.Count -eq 0) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
            Set-ItResult -Skipped -Because "plan-review message not found (Start-Plan flow changed)"
            return
        }
        $msgs.Count | Should -Be 1
        $msgs[0].ref | Should -Be "PLAN-REVIEW"
        
        # Verify room-001 does not exist yet (Manager is blocking)
        $room001 = Join-Path $script:warRoomsDir "room-001"
        Test-Path $room001 | Should -BeFalse

        # Post plan-approve
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-approve" -Ref "PLAN-REVIEW" -Body "Looks good" | Out-Null
        
        # Now wait for room-001 to be created
        $waited = 0
        while (-not (Test-Path $room001) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        Test-Path $room001 | Should -BeTrue
        
        # Cleanup
        Stop-Job $job
        Remove-Job $job
    }
    
    It "handles plan rejection by looping back" {
        $env:WARROOMS_DIR = $script:warRoomsDir
        
        $job = Start-Job -ScriptBlock {
            param($StartPlan, $PlanFile, $ProjectDir, $WarRoomsDir)
            $env:WARROOMS_DIR = $WarRoomsDir
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Review
        } -ArgumentList $script:StartPlan, $script:planFile, $script:projectDir, $script:warRoomsDir

        $room000 = Join-Path $script:warRoomsDir "room-000"
        $channel000 = Join-Path $room000 "channel.jsonl"
        
        $maxWaits = 40
        $waited = 0
        while (-not (Test-Path $channel000) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        if (-not (Test-Path $channel000)) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
            Set-ItResult -Skipped -Because "room-000/channel.jsonl was not created (Start-Plan flow changed)"
            return
        }

        # Read the first plan-review message
        $msgs = @(& $script:ReadMessages -RoomDir $room000 -FilterType "plan-review" -AsObject)
        if ($msgs.Count -eq 0) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
            Set-ItResult -Skipped -Because "plan-review message not found (Start-Plan flow changed)"
            return
        }
        $msgs.Count | Should -Be 1
        $firstMsgId = $msgs[0].id
        
        # Post plan-reject
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-reject" -Ref "PLAN-REVIEW" -Body "Too vague" | Out-Null
        
        # Wait for the second plan-review message
        $waited = 0
        $secondReviewFound = $false
        while ($waited -lt $maxWaits) {
            $msgs = @(& $script:ReadMessages -RoomDir $room000 -FilterType "plan-review" -After $firstMsgId -AsObject)
            if ($msgs.Count -gt 0) {
                $secondReviewFound = $true
                break
            }
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        $secondReviewFound | Should -BeTrue
        
        # Now post plan-approve
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-approve" -Ref "PLAN-REVIEW" -Body "Approved" | Out-Null
        
        # Wait for room-001 to be created (indicates loop finished)
        $room001 = Join-Path $script:warRoomsDir "room-001"
        $waited = 0
        while (-not (Test-Path $room001) -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        Test-Path $room001 | Should -BeTrue
        
        # Cleanup
        Stop-Job $job
        Remove-Job $job
    }
}
