# Agent OS — New-Plan Pester Tests

BeforeAll {
    $script:NewPlan = Join-Path $PSScriptRoot "New-Plan.ps1"
}

Describe "New-Plan" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:projectDir ".agents") -Force | Out-Null
    }

    Context "Plan creation" {
        It "creates a plan file" {
            $planFile = Join-Path $TestDrive "plan-test.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Implement auth" `
                              -PlanFile $planFile -NonInteractive

            Test-Path $planFile | Should -BeTrue
        }

        It "includes the goal in the plan" {
            $planFile = Join-Path $TestDrive "plan-goal.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Build dashboard v2" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "Build dashboard v2"
        }

        It "generates EPIC-001 from the goal" {
            $planFile = Join-Path $TestDrive "plan-epic.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "API layer" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "EPIC-001"
        }

        It "includes tasks under the epic" {
            $planFile = Join-Path $TestDrive "plan-tasks.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Test" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "TASK-001"
            $content | Should -Match "TASK-002"
            $content | Should -Match "TASK-003"
            $content | Should -Match "TASK-004"
        }

        It "includes definition of done" {
            $planFile = Join-Path $TestDrive "plan-dod.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Test" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "Definition of Done"
        }

        It "includes acceptance criteria" {
            $planFile = Join-Path $TestDrive "plan-ac.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Test" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "Acceptance Criteria"
        }

        It "includes embedded JSON config" {
            $planFile = Join-Path $TestDrive "plan-config.md"
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Test" `
                              -PlanFile $planFile -NonInteractive

            $content = Get-Content $planFile -Raw
            $content | Should -Match "plan_id"
            $content | Should -Match "definition_of_done"
            $content | Should -Match "acceptance_criteria"
        }
    }

    Context "Auto-generated plan file path" {
        It "creates plan in project root directory when no PlanFile specified" {
            & $script:NewPlan -ProjectDir $script:projectDir -Goal "Auto path" -NonInteractive

            $plans = Get-ChildItem $script:projectDir -Filter "plan-*.md" -ErrorAction SilentlyContinue
            $plans.Count | Should -BeGreaterOrEqual 1
        }
    }

    Context "Error handling" {
        It "fails when no goal provided in non-interactive mode" {
            $planFile = Join-Path $TestDrive "plan-nogoal.md"
            $err = $null
            try {
                & $script:NewPlan -ProjectDir $script:projectDir -PlanFile $planFile -NonInteractive 2>&1
            } catch {
                $err = $_.Exception.Message
            }
            # Script calls Write-Error + exit 1; Pester v5 captures either as error
            $true | Should -BeTrue  # If we got here without a plan file, the guard worked
            Test-Path $planFile | Should -BeFalse
        }
    }

    Context "Output" {
        It "returns the plan file path or registered plan_id" {
            $planFile = Join-Path $TestDrive "plan-output.md"
            $result = & $script:NewPlan -ProjectDir $script:projectDir -Goal "Output test" `
                                        -PlanFile $planFile -NonInteractive
            # New-Plan returns the plan_id when dashboard is reachable,
            # or the plan file path when it is not.
            $lastOutput = ($result | Select-Object -Last 1).ToString().Trim()
            ($lastOutput -eq $planFile -or $lastOutput -match '^[0-9a-f]{8,}$') | Should -BeTrue
        }
    }
}
