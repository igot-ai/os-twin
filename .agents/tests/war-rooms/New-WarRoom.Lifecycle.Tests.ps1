# Agent OS — New-WarRoom Lifecycle Pester Tests (V2 Schema)
# Verifies that lifecycle.json is purely derived from candidate_roles (DAG.json design)

BeforeAll {
    $script:NewWarRoom = Join-Path (Resolve-Path "$PSScriptRoot/../../war-rooms").Path "New-WarRoom.ps1"
}

Describe "New-WarRoom lifecycle.json" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
    }

    Context "Always created" {
        It "creates lifecycle.json even without Pipeline or Capabilities" {
            & $script:NewWarRoom -RoomId "room-lc-01" -TaskRef "EPIC-001" `
                                 -TaskDescription "Basic epic" `
                                 -WarRoomsDir $script:warRoomsDir

            Test-Path (Join-Path $script:warRoomsDir "room-lc-01" "lifecycle.json") | Should -BeTrue
        }

        It "sets initial_state to developing (v2)" {
            & $script:NewWarRoom -RoomId "room-lc-02" -TaskRef "EPIC-002" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-lc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.initial_state | Should -Be "developing"
            $lc.version | Should -Be 2
        }
    }

    Context "Single candidate — developing goes to passed (no evaluator)" {
        It "candidate_roles=['engineer'] → developing role is engineer, done goes to passed" {
            & $script:NewWarRoom -RoomId "room-sc-01" -TaskRef "EPIC-001" `
                                 -TaskDescription "Engineer only" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.role | Should -Be "engineer"
            # Single worker with no evaluator → done goes directly to passed
            $lc.states.developing.signals.done.target | Should -Be "passed"
        }

        It "candidate_roles=['reporter'] → reporter does developing" {
            & $script:NewWarRoom -RoomId "room-sc-03" -TaskRef "EPIC-003" `
                                 -TaskDescription "Reporter only" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "reporter" `
                                 -CandidateRoles @("reporter")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-03" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.role | Should -Be "reporter"
        }

        It "optimize state exists with same role as developing" {
            & $script:NewWarRoom -RoomId "room-sc-04" -TaskRef "EPIC-004" `
                                 -TaskDescription "Optimize state" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-04" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.optimize.role | Should -Be "engineer"
            $lc.states.optimize.type | Should -Be "work"
        }
    }

    Context "Multi-candidate — review chain from evaluator roles" {
        It "candidate_roles=['engineer','qa'] → review is final gate (qa=evaluator)" {
            & $script:NewWarRoom -RoomId "room-mc-01" -TaskRef "EPIC-010" `
                                 -TaskDescription "With QA" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            # qa has instance_type=evaluator → first evaluator gets state name "review"
            $lc.states.developing.signals.done.target | Should -Be "review"
            $lc.states.review.role | Should -Be "qa"
            $lc.states.review.type | Should -Be "review"
            $lc.states.review.signals.pass.target | Should -Be "passed"
            $lc.states.review.signals.fail.target | Should -Be "optimize"
        }

        It "candidate_roles=['architect','manager'] → architect is evaluator, manager excluded" {
            & $script:NewWarRoom -RoomId "room-mc-02" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Plan negotiation" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "architect" `
                                 -CandidateRoles @("architect", "manager")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            # architect has instance_type=evaluator; manager is orchestrator (filtered)
            # Only evaluator remains → initial_state = "review" (no workers)
            $lc.initial_state | Should -Be "review"
            $lc.states.review.role | Should -Be "architect"
            $lc.states.review.type | Should -Be "review"
        }

        It "three candidates chain correctly: developing → review(architect) → review-qa → passed" {
            & $script:NewWarRoom -RoomId "room-mc-04" -TaskRef "EPIC-012" `
                                 -TaskDescription "Full pipeline" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "architect", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-04" "lifecycle.json") -Raw | ConvertFrom-Json
            # engineer=worker → developing; architect=evaluator → review; qa=evaluator → review-qa
            $lc.states.developing.signals.done.target | Should -Be "review"
            $lc.states.review.role | Should -Be "architect"
            $lc.states.review.signals.pass.target | Should -Be "review-qa"
            $lc.states.'review-qa'.role | Should -Be "qa"
            $lc.states.'review-qa'.signals.pass.target | Should -Be "passed"
        }
    }

    Context "V2 structural states always present" {
        It "triage and failed states exist for single candidate" {
            & $script:NewWarRoom -RoomId "room-bi-01" -TaskRef "EPIC-020" `
                                 -TaskDescription "Builtins" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-bi-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.triage.type | Should -Be "triage"
            $lc.states.triage.role | Should -Be "manager"
            $lc.states.failed.type | Should -Be "decision"
            $lc.states.passed.type | Should -Be "terminal"
            $lc.states.'failed-final'.type | Should -Be "terminal"
        }
    }

    Context "Pipeline precedence" {
        It "explicit Pipeline overrides candidate-derived lifecycle" {
            & $script:NewWarRoom -RoomId "room-pp-01" -TaskRef "EPIC-030" `
                                 -TaskDescription "Pipeline room" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer") `
                                 -Pipeline "engineer -> security-review -> qa"

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-pp-01" "lifecycle.json") -Raw | ConvertFrom-Json
            # Pipeline: engineer(worker) → security-review(worker, no role.json) → qa(evaluator)
            # security-review has no role.json → defaults to worker → "developing-security-review"
            $lc.states.'developing-security-review' | Should -Not -BeNullOrEmpty
            $lc.states.'developing-security-review'.type | Should -Be "work"
            # qa is evaluator → "review"
            $lc.states.review.role | Should -Be "qa"
        }
    }

    Context "Unknown role gets developing state (defaults to worker)" {
        It "unknown role 'data-scientist' gets 'developing-data-scientist' state" {
            & $script:NewWarRoom -RoomId "room-ur-01" -TaskRef "EPIC-040" `
                                 -TaskDescription "Custom role" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "data-scientist")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-ur-01" "lifecycle.json") -Raw | ConvertFrom-Json
            # data-scientist has no role.json → defaults to worker → "developing-data-scientist"
            $lc.states.'developing-data-scientist'.role | Should -Be "data-scientist"
            $lc.states.'developing-data-scientist'.type | Should -Be "work"
            $lc.states.'developing-data-scientist'.signals.done | Should -Not -BeNullOrEmpty
        }
    }
}
