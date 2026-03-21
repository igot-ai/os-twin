# Agent OS — New-WarRoom Lifecycle Pester Tests
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

        It "sets initial_state to engineering" {
            & $script:NewWarRoom -RoomId "room-lc-02" -TaskRef "EPIC-002" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-lc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.initial_state | Should -Be "engineering"
        }
    }

    Context "Single candidate — no extra review states" {
        It "candidate_roles=['engineer'] → engineering goes directly to passed" {
            & $script:NewWarRoom -RoomId "room-sc-01" -TaskRef "EPIC-001" `
                                 -TaskDescription "Engineer only" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.role | Should -Be "engineer"
            $lc.states.engineering.transitions.done | Should -Be "passed"
        }

        It "candidate_roles=['engineer'] → NO qa-review state exists" {
            & $script:NewWarRoom -RoomId "room-sc-02" -TaskRef "EPIC-002" `
                                 -TaskDescription "No QA" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.'qa-review' | Should -BeNullOrEmpty
        }

        It "candidate_roles=['reporter'] → reporter does engineering" {
            & $script:NewWarRoom -RoomId "room-sc-03" -TaskRef "EPIC-003" `
                                 -TaskDescription "Reporter only" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "reporter" `
                                 -CandidateRoles @("reporter")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-03" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.role | Should -Be "reporter"
            $lc.states.engineering.transitions.done | Should -Be "passed"
        }

        It "fixing transitions to passed when no review stages" {
            & $script:NewWarRoom -RoomId "room-sc-04" -TaskRef "EPIC-004" `
                                 -TaskDescription "Single role fixing" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-sc-04" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.fixing.role | Should -Be "engineer"
            $lc.states.fixing.transitions.done | Should -Be "passed"
        }
    }

    Context "Multi-candidate — review stages from candidate_roles[1..N]" {
        It "candidate_roles=['engineer','qa'] → adds qa-review between engineering and passed" {
            & $script:NewWarRoom -RoomId "room-mc-01" -TaskRef "EPIC-010" `
                                 -TaskDescription "With QA" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.transitions.done | Should -Be "qa-review"
            $lc.states.'qa-review'.role | Should -Be "qa"
            $lc.states.'qa-review'.transitions.pass | Should -Be "passed"
            $lc.states.'qa-review'.transitions.fail | Should -Be "manager-triage"
        }

        It "candidate_roles=['manager','architect'] → adds architect-review" {
            & $script:NewWarRoom -RoomId "room-mc-02" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Plan negotiation" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "manager" `
                                 -CandidateRoles @("manager", "architect")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-02" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.role | Should -Be "manager"
            $lc.states.'architect-review'.role | Should -Be "architect"
            $lc.states.'architect-review'.transitions.pass | Should -Be "passed"
        }

        It "fixing routes to first review stage (not passed)" {
            & $script:NewWarRoom -RoomId "room-mc-03" -TaskRef "EPIC-011" `
                                 -TaskDescription "Fixing loop" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-03" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.fixing.transitions.done | Should -Be "qa-review"
        }

        It "three candidates chain correctly: engineering → review1 → review2 → passed" {
            & $script:NewWarRoom -RoomId "room-mc-04" -TaskRef "EPIC-012" `
                                 -TaskDescription "Full pipeline" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -AssignedRole "engineer" `
                                 -CandidateRoles @("engineer", "architect", "qa")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-mc-04" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.transitions.done | Should -Be "architect-review"
            $lc.states.'architect-review'.role | Should -Be "architect"
            $lc.states.'architect-review'.transitions.pass | Should -Be "qa-review"
            $lc.states.'qa-review'.role | Should -Be "qa"
            $lc.states.'qa-review'.transitions.pass | Should -Be "passed"
        }
    }

    Context "Builtin states always present" {
        It "manager-triage and plan-revision exist for single candidate" {
            & $script:NewWarRoom -RoomId "room-bi-01" -TaskRef "EPIC-020" `
                                 -TaskDescription "Builtins" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -CandidateRoles @("engineer")

            $lc = Get-Content (Join-Path $script:warRoomsDir "room-bi-01" "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.'manager-triage'.type | Should -Be "builtin"
            $lc.states.'manager-triage'.role | Should -Be "manager"
            $lc.states.'plan-revision'.type | Should -Be "builtin"
            $lc.states.'plan-revision'.role | Should -Be "manager"
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
            $lc.states.'security-review' | Should -Not -BeNullOrEmpty
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
            $lc.states.'data-scientist-review'.transitions.pass | Should -Be "passed"
        }
    }
}
