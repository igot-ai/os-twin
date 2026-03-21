# Agent OS — New-GoalReport Pester Tests

BeforeAll {
    $script:NewGoalReport = Join-Path (Resolve-Path "$PSScriptRoot/../../war-rooms").Path "New-GoalReport.ps1"
    $script:NewWarRoom = Join-Path (Resolve-Path "$PSScriptRoot/../../war-rooms").Path "New-WarRoom.ps1"
}

Describe "New-GoalReport" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "wr-report-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
    }

    BeforeAll {
        function New-TestRoom {
            param(
                [string]$RoomId,
                [string[]]$DoD = @(),
                [string[]]$AC = @(),
                [string]$EngOutput = ""
            )
            & $script:NewWarRoom -RoomId $RoomId -TaskRef "TASK-RPT" `
                                 -TaskDescription "Report test" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -DefinitionOfDone $DoD `
                                 -AcceptanceCriteria $AC | Out-Null
            $roomDir = Join-Path $script:warRoomsDir $RoomId
            if ($EngOutput) {
                $EngOutput | Out-File (Join-Path $roomDir "artifacts" "engineer-output.txt") -Encoding utf8
            }
            return [string]$roomDir
        }
    }

    Context "Report generation" {
        It "creates goal-verification.json" {
            $roomDir = New-TestRoom -RoomId "room-r01" `
                -DoD @("Feature complete") `
                -EngOutput "Feature complete and deployed."

            & $script:NewGoalReport -RoomDir $roomDir

            $reportFile = Join-Path $roomDir "goal-verification.json"
            Test-Path $reportFile | Should -BeTrue
        }

        It "returns the report file path" {
            $roomDir = New-TestRoom -RoomId "room-r02" `
                -DoD @("Test") -EngOutput "Test done."

            $result = & $script:NewGoalReport -RoomDir $roomDir
            $result | Should -Match "goal-verification\.json"
        }
    }

    Context "Report structure" {
        BeforeEach {
            $roomDir = New-TestRoom -RoomId "room-r10" `
                -DoD @("Auth working", "Tests passing") `
                -AC @("Login works") `
                -EngOutput "Auth working perfectly. Tests passing. Login works now."

            & $script:NewGoalReport -RoomDir $roomDir

            $script:report = Get-Content (Join-Path $roomDir "goal-verification.json") -Raw | ConvertFrom-Json
        }

        It "includes version" {
            $script:report.version | Should -Be 1
        }

        It "includes generated_at timestamp" {
            $script:report.generated_at.ToString("o") | Should -Match "\d{4}-\d{2}-\d{2}T"
        }

        It "includes room_id" {
            $script:report.room_id | Should -Be "room-r10"
        }

        It "includes task_ref" {
            $script:report.task_ref | Should -Be "TASK-RPT"
        }

        It "includes overall_status" {
            $script:report.overall_status | Should -BeIn @("passed", "partial", "failed")
        }

        It "includes overall_score" {
            $script:report.overall_score | Should -BeGreaterOrEqual 0
            $script:report.overall_score | Should -BeLessOrEqual 1.0
        }

        It "includes summary counts" {
            $script:report.summary.total_goals | Should -Be 3
            $script:report.summary.goals_met | Should -BeGreaterOrEqual 0
        }

        It "includes per-goal details" {
            $script:report.goals.Count | Should -Be 3
            $script:report.goals[0].PSObject.Properties.Name | Should -Contain "category"
            $script:report.goals[0].PSObject.Properties.Name | Should -Contain "goal"
            $script:report.goals[0].PSObject.Properties.Name | Should -Contain "status"
            $script:report.goals[0].PSObject.Properties.Name | Should -Contain "evidence"
            $script:report.goals[0].PSObject.Properties.Name | Should -Contain "score"
        }

        It "categorizes DoD and AC goals correctly" {
            $categories = $script:report.goals | ForEach-Object { $_.category }
            ($categories | Where-Object { $_ -eq "definition_of_done" }).Count | Should -Be 2
            ($categories | Where-Object { $_ -eq "acceptance_criteria" }).Count | Should -Be 1
        }
    }

    Context "Passed report" {
        It "shows passed when all goals met" {
            $roomDir = New-TestRoom -RoomId "room-r20" `
                -DoD @("feature complete") `
                -EngOutput "The feature complete and tested."

            & $script:NewGoalReport -RoomDir $roomDir

            $report = Get-Content (Join-Path $roomDir "goal-verification.json") -Raw | ConvertFrom-Json
            $report.overall_status | Should -Be "passed"
            $report.summary.goals_met | Should -Be 1
            $report.summary.goals_not_met | Should -Be 0
        }
    }

    Context "Failed report" {
        It "shows non-passed when goals not met" {
            $roomDir = New-TestRoom -RoomId "room-r30" `
                -DoD @("Kubernetes deployment working") `
                -EngOutput "Fixed a CSS issue."

            & $script:NewGoalReport -RoomDir $roomDir

            $report = Get-Content (Join-Path $roomDir "goal-verification.json") -Raw | ConvertFrom-Json
            $report.overall_status | Should -Not -Be "passed"
        }
    }

    Context "No goals" {
        It "auto-passes with no goals defined" {
            $roomDir = New-TestRoom -RoomId "room-r40" -EngOutput "Work done."

            & $script:NewGoalReport -RoomDir $roomDir

            $report = Get-Content (Join-Path $roomDir "goal-verification.json") -Raw | ConvertFrom-Json
            $report.overall_status | Should -Be "passed"
            $report.summary.total_goals | Should -Be 0
        }
    }
}
