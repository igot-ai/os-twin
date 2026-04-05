# Agent OS — New-WarRoom Pester Tests

BeforeAll {
    $script:NewWarRoom = Join-Path (Resolve-Path "$PSScriptRoot/../../war-rooms").Path "New-WarRoom.ps1"
}

Describe "New-WarRoom" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
    }

    Context "Basic creation" {
        It "creates the room directory structure" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Implement feature" `
                                 -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-001"
            Test-Path $roomDir | Should -BeTrue
            Test-Path (Join-Path $roomDir "pids") | Should -BeTrue
            Test-Path (Join-Path $roomDir "artifacts") | Should -BeTrue
            Test-Path (Join-Path $roomDir "channel.jsonl") | Should -BeTrue
        }

        It "creates the status file with 'pending'" {
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $status = (Get-Content (Join-Path $script:warRoomsDir "room-002" "status") -Raw).Trim()
            $status | Should -Be "pending"
        }

        It "creates the retries file with '0'" {
            & $script:NewWarRoom -RoomId "room-003" -TaskRef "TASK-003" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $retries = (Get-Content (Join-Path $script:warRoomsDir "room-003" "retries") -Raw).Trim()
            $retries | Should -Be "0"
        }

        It "creates the task-ref file" {
            & $script:NewWarRoom -RoomId "room-004" -TaskRef "EPIC-001" `
                                 -TaskDescription "Epic work" -WarRoomsDir $script:warRoomsDir

            $ref = (Get-Content (Join-Path $script:warRoomsDir "room-004" "task-ref") -Raw).Trim()
            $ref | Should -Be "EPIC-001"
        }

        It "creates the brief.md file" {
            & $script:NewWarRoom -RoomId "room-005" -TaskRef "TASK-005" `
                                 -TaskDescription "Brief content here" `
                                 -WarRoomsDir $script:warRoomsDir

            $brief = Get-Content (Join-Path $script:warRoomsDir "room-005" "brief.md") -Raw
            $brief | Should -Match "TASK-005"
            $brief | Should -Match "Brief content here"
        }
    }

    Context "Config.json goal contract" {
        It "creates config.json with required structure" {
            & $script:NewWarRoom -RoomId "room-010" -TaskRef "EPIC-001" `
                                 -TaskDescription "Auth system" `
                                 -WarRoomsDir $script:warRoomsDir

            $configFile = Join-Path $script:warRoomsDir "room-010" "config.json"
            Test-Path $configFile | Should -BeTrue
            $config = Get-Content $configFile -Raw | ConvertFrom-Json

            $config.room_id | Should -Be "room-010"
            $config.task_ref | Should -Be "EPIC-001"
            $config.created_at.ToString("o") | Should -Match "\d{4}-\d{2}-\d{2}T"
        }

        It "stores assignment metadata" {
            & $script:NewWarRoom -RoomId "room-011" -TaskRef "EPIC-002" `
                                 -TaskDescription "Dashboard v2`nBuild a new dashboard" `
                                 -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-011" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.title | Should -Be "Dashboard v2"
            $config.assignment.description | Should -Match "Build a new dashboard"
            $config.assignment.assigned_role | Should -Be "engineer"
            $config.assignment.type | Should -Be "epic"
        }

        It "detects task type from TASK- prefix" {
            & $script:NewWarRoom -RoomId "room-012" -TaskRef "TASK-001" `
                                 -TaskDescription "Small fix" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-012" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.type | Should -Be "task"
        }

        It "detects epic type from EPIC- prefix" {
            & $script:NewWarRoom -RoomId "room-013" -TaskRef "EPIC-003" `
                                 -TaskDescription "Big feature" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-013" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.type | Should -Be "epic"
        }

        It "stores definition_of_done goals" {
            $dod = @("JWT working", "Tests at 80%", "No hardcoded secrets")
            & $script:NewWarRoom -RoomId "room-014" -TaskRef "EPIC-004" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir `
                                 -DefinitionOfDone $dod

            $config = Get-Content (Join-Path $script:warRoomsDir "room-014" "config.json") -Raw | ConvertFrom-Json
            $config.goals.definition_of_done.Count | Should -Be 3
            $config.goals.definition_of_done[0] | Should -Be "JWT working"
            $config.goals.definition_of_done[2] | Should -Be "No hardcoded secrets"
        }

        It "stores acceptance_criteria" {
            $ac = @("POST /login returns 200", "GET /protected returns 401 without token")
            & $script:NewWarRoom -RoomId "room-015" -TaskRef "TASK-010" `
                                 -TaskDescription "API" -WarRoomsDir $script:warRoomsDir `
                                 -AcceptanceCriteria $ac

            $config = Get-Content (Join-Path $script:warRoomsDir "room-015" "config.json") -Raw | ConvertFrom-Json
            $config.goals.acceptance_criteria.Count | Should -Be 2
        }

        It "includes default quality_requirements" {
            & $script:NewWarRoom -RoomId "room-016" -TaskRef "TASK-011" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-016" "config.json") -Raw | ConvertFrom-Json
            $config.goals.quality_requirements.test_coverage_min | Should -Be 80
            $config.goals.quality_requirements.lint_clean | Should -Be $true
        }

        It "stores constraints" {
            & $script:NewWarRoom -RoomId "room-017" -TaskRef "TASK-012" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir `
                                 -MaxRetries 5 -TimeoutSeconds 1200

            $config = Get-Content (Join-Path $script:warRoomsDir "room-017" "config.json") -Raw | ConvertFrom-Json
            $config.constraints.max_retries | Should -Be 5
            $config.constraints.timeout_seconds | Should -Be 1200
        }

        It "stores status with pending state" {
            & $script:NewWarRoom -RoomId "room-018" -TaskRef "TASK-013" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-018" "config.json") -Raw | ConvertFrom-Json
            $config.status.current | Should -Be "pending"
            $config.status.retries | Should -Be 0
        }

        It "stores plan_id when provided" {
            & $script:NewWarRoom -RoomId "room-019" -TaskRef "EPIC-005" `
                                 -TaskDescription "Feature" -WarRoomsDir $script:warRoomsDir `
                                 -PlanId "001-auth-system"

            $config = Get-Content (Join-Path $script:warRoomsDir "room-019" "config.json") -Raw | ConvertFrom-Json
            $config.plan_id | Should -Be "001-auth-system"
        }
    }

    Context "Error handling" {
        It "prevents overwriting existing room" {
            & $script:NewWarRoom -RoomId "room-dup" -TaskRef "TASK-001" `
                                 -TaskDescription "First" -WarRoomsDir $script:warRoomsDir

            $output = & $script:NewWarRoom -RoomId "room-dup" -TaskRef "TASK-002" `
                                           -TaskDescription "Second" -WarRoomsDir $script:warRoomsDir 2>&1
            $output | Should -Match "already exists"
        }
    }

    Context "Empty goals" {
        It "creates config.json with empty goals arrays when no goals provided" {
            & $script:NewWarRoom -RoomId "room-020" -TaskRef "TASK-020" `
                                 -TaskDescription "No goals" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-020" "config.json") -Raw | ConvertFrom-Json
            $config.goals.definition_of_done.Count | Should -Be 0
            $config.goals.acceptance_criteria.Count | Should -Be 0
        }
    }

    Context "AssignedRole support" {
        It "writes AssignedRole into config.json" {
            & $script:NewWarRoom -RoomId "room-role-01" -TaskRef "TASK-100" `
                                 -TaskDescription "FE work" -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer:fe"

            $config = Get-Content (Join-Path $script:warRoomsDir "room-role-01" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.assigned_role | Should -Be "engineer:fe"
        }

        It "defaults AssignedRole to engineer" {
            & $script:NewWarRoom -RoomId "room-role-02" -TaskRef "TASK-101" `
                                 -TaskDescription "Generic work" -WarRoomsDir $script:warRoomsDir

            $config = Get-Content (Join-Path $script:warRoomsDir "room-role-02" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.assigned_role | Should -Be "engineer"
        }

        It "supports backend engineer instance" {
            & $script:NewWarRoom -RoomId "room-role-03" -TaskRef "TASK-102" `
                                 -TaskDescription "BE work" -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer:be"

            $config = Get-Content (Join-Path $script:warRoomsDir "room-role-03" "config.json") -Raw | ConvertFrom-Json
            $config.assignment.assigned_role | Should -Be "engineer:be"
        }
    }

    Context "Contexts directory" {
        It "creates contexts/ directory in new room" {
            & $script:NewWarRoom -RoomId "room-ctx-01" -TaskRef "TASK-200" `
                                 -TaskDescription "Test contexts" -WarRoomsDir $script:warRoomsDir

            Test-Path (Join-Path $script:warRoomsDir "room-ctx-01" "contexts") | Should -BeTrue
        }
    }

    Context "Plan-specific roles.json resolution" {
        BeforeEach {
            # Create a mock ~/.ostwin/.agents/plans directory with plan roles config
            $script:plansDir = Join-Path $TestDrive "ostwin-plans-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:plansDir -Force | Out-Null
            $script:testPlanId = "test-plan-$(Get-Random)"

            $planRolesConfig = @{
                engineer = @{
                    default_model   = "gemini-plan-custom-model"
                    timeout_seconds = 1800
                    skill_refs      = @("write-tests", "code-review")
                }
                qa = @{
                    default_model = "qa-plan-model"
                }
            }
            $planRolesFile = Join-Path $script:plansDir "$($script:testPlanId).roles.json"
            $planRolesConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $planRolesFile -Encoding utf8

            # Point HOME to TestDrive so the script finds ~/.ostwin/.agents/plans/
            $script:origHome = $env:HOME
            $script:fakeHome = Join-Path $TestDrive "fakehome-$(Get-Random)"
            New-Item -ItemType Directory -Path (Join-Path $script:fakeHome ".ostwin" ".agents" "plans") -Force | Out-Null
            Copy-Item $planRolesFile (Join-Path $script:fakeHome ".ostwin" ".agents" "plans")
            $env:HOME = $script:fakeHome
        }

        AfterEach {
            $env:HOME = $script:origHome
        }

        It "uses model from plan roles.json when PlanId is provided" {
            & $script:NewWarRoom -RoomId "room-plan-01" -TaskRef "EPIC-010" `
                                 -TaskDescription "Plan test" -WarRoomsDir $script:warRoomsDir `
                                 -PlanId $script:testPlanId

            $roleFile = Get-ChildItem (Join-Path $script:warRoomsDir "room-plan-01") -Filter "engineer_*.json" | Select-Object -First 1
            $roleFile | Should -Not -BeNullOrEmpty
            $roleConfig = Get-Content $roleFile.FullName -Raw | ConvertFrom-Json
            $roleConfig.model | Should -Be "gemini-plan-custom-model"
        }

        It "uses timeout from plan roles.json" {
            & $script:NewWarRoom -RoomId "room-plan-02" -TaskRef "EPIC-011" `
                                 -TaskDescription "Timeout test" -WarRoomsDir $script:warRoomsDir `
                                 -PlanId $script:testPlanId

            $roleFile = Get-ChildItem (Join-Path $script:warRoomsDir "room-plan-02") -Filter "engineer_*.json" | Select-Object -First 1
            $roleConfig = Get-Content $roleFile.FullName -Raw | ConvertFrom-Json
            $roleConfig.timeout_seconds | Should -Be 1800
        }

        It "includes skill_refs from plan roles.json" {
            & $script:NewWarRoom -RoomId "room-plan-03" -TaskRef "EPIC-012" `
                                 -TaskDescription "Skills test" -WarRoomsDir $script:warRoomsDir `
                                 -PlanId $script:testPlanId

            $roleFile = Get-ChildItem (Join-Path $script:warRoomsDir "room-plan-03") -Filter "engineer_*.json" | Select-Object -First 1
            $roleConfig = Get-Content $roleFile.FullName -Raw | ConvertFrom-Json
            $roleConfig.skill_refs | Should -Contain "write-tests"
            $roleConfig.skill_refs | Should -Contain "code-review"
        }

        It "falls back to default model when PlanId has no roles.json" {
            & $script:NewWarRoom -RoomId "room-plan-04" -TaskRef "EPIC-013" `
                                 -TaskDescription "Fallback test" -WarRoomsDir $script:warRoomsDir `
                                 -PlanId "nonexistent-plan-id"

            $roleFile = Get-ChildItem (Join-Path $script:warRoomsDir "room-plan-04") -Filter "engineer_*.json" | Select-Object -First 1
            $roleConfig = Get-Content $roleFile.FullName -Raw | ConvertFrom-Json
            # Should fall back to global config or default
            $roleConfig.model | Should -Not -Be "gemini-plan-custom-model"
        }
    }
}
