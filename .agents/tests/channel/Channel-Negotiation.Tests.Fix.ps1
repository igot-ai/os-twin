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
        
        $script:planFile = Join-Path $TestDrive "test-plan-negotiation-ok.md"
        $lines = @(
            "# Plan: Negotiation Test",
            "",
            "## Epics",
            "",
            "## EPIC-001 - First task",
            "",
            "- This is a well-specified task.",
            "",
            "#### Definition of Done",
            "- [ ] Task done",
            "",
            "#### Acceptance Criteria",
            "- [ ] Test passes"
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
            # We use Unified mode to test the new flow
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Unified -Review
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
            Write-Host "JOB OUTPUT:"
            Receive-Job $job | Write-Host
            throw "room-000 was not created!"
        }
        Test-Path $channel000 | Should -BeTrue

        # Read the plan-review message
        $msgs = @(& $script:ReadMessages -RoomDir $room000 -FilterType "plan-review" -AsObject)
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
    
    It "aborts if plan is rejected" {
        $env:WARROOMS_DIR = $script:warRoomsDir
        
        $job = Start-Job -ScriptBlock {
            param($StartPlan, $PlanFile, $ProjectDir, $WarRoomsDir)
            $env:WARROOMS_DIR = $WarRoomsDir
            & $StartPlan -PlanFile $PlanFile -ProjectDir $ProjectDir -Unified -Review
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
            Write-Host "JOB OUTPUT:"
            Receive-Job $job | Write-Host
            throw "room-000 was not created!"
        }
        Test-Path $channel000 | Should -BeTrue

        # Post plan-reject
        & $script:PostMessage -RoomDir $room000 -From "team" -To "manager" -Type "plan-reject" -Ref "PLAN-REVIEW" -Body "Needs changes" | Out-Null
        
        # Wait for job to complete (it should exit with code 1)
        $waited = 0
        while ($job.State -eq 'Running' -and $waited -lt $maxWaits) {
            Start-Sleep -Milliseconds 500
            $waited++
        }
        
        $job.State | Should -Be 'Completed'
        
        # room-001 should not exist
        $room001 = Join-Path $script:warRoomsDir "room-001"
        Test-Path $room001 | Should -BeFalse
        
        Remove-Job $job
    }
}

