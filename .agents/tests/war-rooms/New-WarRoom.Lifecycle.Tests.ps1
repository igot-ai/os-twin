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

    Context "Single candidate — developing goes through review to passed" {
        It "candidate_roles=['engineer'] → developing role is engineer" {
            & $script:NewWarRoom -RoomId "room-sc-01" -TaskRef "EPIC-001" `
                                 -TaskDescription "Engineer only" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.role | Should -Be "engineer"
            $lc.states.developing.signals.done.target | Should -Be "review"
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

    Context "Multi-candidate — review chain from candidate_roles[1..N]" {
        It "candidate_roles=['engineer','qa'] → qa-review is final gate" {
            & $script:NewWarRoom -RoomId "room-mc-01" -TaskRef "EPIC-010" `
                                 -TaskDescription "With QA" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.signals.done.target | Should -Be "qa-review"
            $lc.states.'qa-review'.role | Should -Be "qa"
            $lc.states.'qa-review'.signals.pass.target | Should -Be "passed"
            $lc.states.'qa-review'.signals.fail.target | Should -Be "optimize"
        }

        It "candidate_roles=['architect','manager'] → architect develops, manager excluded from review" {
            & $script:NewWarRoom -RoomId "room-mc-02" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Plan negotiation" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "architect" `
                                 -CandidateRoles @("architect", "manager")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.role | Should -Be "architect"
            # manager excluded from review chain (orchestrator); QA review is final gate
            $lc.states.review.role | Should -Be "qa"
        }

        It "three candidates chain correctly: developing → architect-review → qa-review → passed" {
            & $script:NewWarRoom -RoomId "room-mc-04" -TaskRef "EPIC-012" `
                                 -TaskDescription "Full pipeline" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "architect", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-04" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.signals.done.target | Should -Be "architect-review"
            $lc.states.'architect-review'.role | Should -Be "architect"
            $lc.states.'architect-review'.signals.pass.target | Should -Match "qa-review|review"
            $lc.states.'qa-review'.role | Should -Be "qa"
            $lc.states.'qa-review'.signals.pass.target | Should -Be "passed"
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
            # Pipeline produces security-review (which candidate-only would NOT)
            $lc.states.'security-review-review' | Should -Not -BeNullOrEmpty
        }
    }

    Context "Unknown role gets generic state name" {
        It "unknown role 'data-scientist' gets 'data-scientist-review' state" {
            & $script:NewWarRoom -RoomId "room-ur-01" -TaskRef "EPIC-040" `
                                 -TaskDescription "Custom role" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "data-scientist")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-ur-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.'data-scientist-review'.role | Should -Be "data-scientist"
            $lc.states.'data-scientist-review'.signals.pass | Should -Not -BeNullOrEmpty
        }
    }
}
