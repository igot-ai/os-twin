BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ResolvePipeline = Join-Path $agentsDir "lifecycle" "Resolve-Pipeline.ps1"
    $script:NewWarRoom = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
}

Describe "V2 Lifecycle Schema Tests" {

    Context "Build-LifecycleV2 via Resolve-Pipeline — single role" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -CandidateRoles @('engineer') -MaxRetries 3
            $script:lc = $output | ConvertFrom-Json
        }

        It "generates version 2 schema" {
            $script:lc.version | Should -Be 2
        }

        It "initial_state is developing" {
            $script:lc.initial_state | Should -Be 'developing'
        }

        It "has developing state with role=engineer and type=work" {
            $script:lc.states.developing.role | Should -Be 'engineer'
            $script:lc.states.developing.type | Should -Be 'work'
        }

        It "developing.done transitions to review (final QA gate)" {
            $script:lc.states.developing.signals.done.target | Should -Be 'review'
        }

        It "developing.error transitions to failed" {
            $script:lc.states.developing.signals.error.target | Should -Be 'failed'
        }

        It "has optimize state with same role as developing" {
            $script:lc.states.optimize.role | Should -Be 'engineer'
            $script:lc.states.optimize.type | Should -Be 'work'
        }

        It "has review state with role=qa and type=review" {
            $script:lc.states.review.role | Should -Be 'qa'
            $script:lc.states.review.type | Should -Be 'review'
        }

        It "review.pass transitions to passed" {
            $script:lc.states.review.signals.pass.target | Should -Be 'passed'
        }

        It "review.fail transitions to developing" {
            $script:lc.states.review.signals.fail.target | Should -Be 'developing'
        }

        It "review.fail includes increment_retries and post_fix actions" {
            $script:lc.states.review.signals.fail.actions | Should -Contain 'increment_retries'
            $script:lc.states.review.signals.fail.actions | Should -Contain 'post_fix'
        }

        It "review.escalate transitions to triage" {
            $script:lc.states.review.signals.escalate.target | Should -Be 'triage'
        }

        It "has triage state with role=manager" {
            $script:lc.states.triage.role | Should -Be 'manager'
            $script:lc.states.triage.type | Should -Be 'triage'
        }

        It "triage has fix, redesign, reject signals" {
            $script:lc.states.triage.signals.fix.target | Should -Be 'developing'
            $script:lc.states.triage.signals.redesign.target | Should -Be 'developing'
            $script:lc.states.triage.signals.reject.target | Should -Be 'failed-final'
        }

        It "has failed decision state with auto_transition" {
            $script:lc.states.failed.type | Should -Be 'decision'
            $script:lc.states.failed.auto_transition | Should -Be $true
        }

        It "failed.retry goes to developing, exhaust goes to failed-final" {
            $script:lc.states.failed.signals.retry.target | Should -Be 'developing'
            $script:lc.states.failed.signals.exhaust.target | Should -Be 'failed-final'
        }

        It "has terminal passed and failed-final states" {
            $script:lc.states.passed.type | Should -Be 'terminal'
            $script:lc.states.'failed-final'.type | Should -Be 'terminal'
        }

        It "respects max_retries parameter" {
            $script:lc.max_retries | Should -Be 3
        }
    }

    Context "Build-LifecycleV2 — multi-role with architect reviewer" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -CandidateRoles @('engineer', 'architect') -MaxRetries 5
            $script:lc = $output | ConvertFrom-Json
        }

        It "generates architect-review state between developing and review" {
            $script:lc.states.'architect-review'.role | Should -Be 'architect'
            $script:lc.states.'architect-review'.type | Should -Be 'review'
        }

        It "developing.done goes to architect-review (not directly to review)" {
            $script:lc.states.developing.signals.done.target | Should -Be 'architect-review'
        }

        It "architect-review.pass goes to review (final QA gate)" {
            $script:lc.states.'architect-review'.signals.pass.target | Should -Be 'review'
        }

        It "architect-review.fail goes to optimize" {
            $script:lc.states.'architect-review'.signals.fail.target | Should -Be 'optimize'
        }

        It "has QA review as final gate" {
            $script:lc.states.review.role | Should -Be 'qa'
            $script:lc.states.review.signals.pass.target | Should -Be 'passed'
        }
    }

    Context "Build-LifecycleV2 — qa in candidate_roles (no duplicate review)" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -CandidateRoles @('engineer', 'qa') -MaxRetries 3
            $script:lc = $output | ConvertFrom-Json
        }

        It "qa-review pass goes to passed directly" {
            $script:lc.states.'qa-review'.signals.pass.target | Should -Be 'passed'
        }

        It "does NOT create a separate review state (qa already covers it)" {
            $script:lc.states.review | Should -BeNullOrEmpty
        }
    }

    Context "Build-LifecycleV2 — PLAN-REVIEW style (architect, manager)" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -CandidateRoles @('architect', 'manager') -MaxRetries 3
            $script:lc = $output | ConvertFrom-Json
        }

        It "primary worker is architect" {
            $script:lc.states.developing.role | Should -Be 'architect'
        }

        It "manager is excluded from review chain (orchestrator)" {
            $script:lc.states | ForEach-Object { $_ } | Where-Object { $_ -match 'manager-review' } | Should -BeNullOrEmpty
        }

        It "still has review state (QA gate)" {
            $script:lc.states.review.role | Should -Be 'qa'
        }
    }

    Context "Build-LifecycleV2 — explicit pipeline string" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -PipelineString "engineer -> security-auditor -> qa" -MaxRetries 3
            $script:lc = $output | ConvertFrom-Json
        }

        It "developing role is the primary (engineer)" {
            $script:lc.states.developing.role | Should -Be 'engineer'
        }

        It "generates security-auditor-review in chain" {
            $script:lc.states.'security-auditor-review'.role | Should -Be 'security-auditor'
        }

        It "chain goes developing → security-auditor-review → qa-review → passed" {
            $script:lc.states.developing.signals.done.target | Should -Be 'security-auditor-review'
            $script:lc.states.'security-auditor-review'.signals.pass.target | Should -Match 'qa-review|review'
        }
    }

    Context "No deadlock possible — every non-terminal state has outbound signals" {

        BeforeEach {
            $script:output = & $script:ResolvePipeline -CandidateRoles @('engineer', 'architect', 'qa') -MaxRetries 3
            $script:lc = $output | ConvertFrom-Json
        }

        It "every non-terminal state has at least one signal" {
            $stateNames = $script:lc.states.PSObject.Properties.Name
            foreach ($name in $stateNames) {
                $state = $script:lc.states.$name
                if ($state.type -eq 'terminal') { continue }
                $sigCount = @($state.signals.PSObject.Properties.Name).Count
                $sigCount | Should -BeGreaterThan 0 `
                    -Because "state '$name' (type=$($state.type)) must have at least one outbound signal"
            }
        }

        It "every signal target is a valid state name" {
            $stateNames = @($script:lc.states.PSObject.Properties.Name)
            foreach ($name in $stateNames) {
                $state = $script:lc.states.$name
                if ($state.type -eq 'terminal') { continue }
                foreach ($sigProp in $state.signals.PSObject.Properties) {
                    $target = $sigProp.Value.target
                    $stateNames | Should -Contain $target `
                        -Because "state '$name' signal '$($sigProp.Name)' targets '$target' which must exist"
                }
            }
        }
    }

    Context "New-WarRoom generates v2 lifecycle" {

        BeforeEach {
            $script:warRoomsDir = Join-Path ([System.IO.Path]::GetTempPath()) "lifecycle-v2-test-$([System.Random]::new().Next())"
            New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
        }

        AfterEach {
            Remove-Item -Path $script:warRoomsDir -Recurse -Force -ErrorAction SilentlyContinue
        }

        It "generates v2 lifecycle with CandidateRoles" {
            & $script:NewWarRoom -RoomId "room-v2" -TaskRef "TASK-V2" `
                -TaskDescription "V2 lifecycle test" -WarRoomsDir $script:warRoomsDir `
                -CandidateRoles @('engineer', 'architect')
            $roomDir = Join-Path $script:warRoomsDir "room-v2"
            $lcPath = Join-Path $roomDir "lifecycle.json"
            $lcPath | Should -Exist
            $lc = Get-Content $lcPath -Raw | ConvertFrom-Json
            $lc.version | Should -Be 2
            $lc.initial_state | Should -Be 'developing'
            $lc.states.developing.role | Should -Be 'engineer'
        }

        It "generates v2 lifecycle even with single role" {
            & $script:NewWarRoom -RoomId "room-v2s" -TaskRef "TASK-V2S" `
                -TaskDescription "Single role v2" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-v2s"
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.version | Should -Be 2
            $lc.states.developing.role | Should -Be 'engineer'
        }
    }
}
