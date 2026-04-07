# Agent OS — Resolve-Pipeline.ps1 Unit Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../lifecycle").Path "..")).Path
    $script:ResolvePipeline = Join-Path $script:agentsDir "lifecycle" "Resolve-Pipeline.ps1"
}

Describe "Resolve-Pipeline.ps1 — Dynamic Lifecycle Generation" {
    It "Builds lifecycle with multiple workers and one evaluator" {
        $roles = @(
            [PSCustomObject]@{ Name = 'game-architect'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'game-engineer'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'game-qa'; InstanceType = 'evaluator' }
        )

        $params = @{
            CandidateRoles = @('game-architect', 'game-engineer', 'game-qa')
            AgentsDir = $script:agentsDir
        }

        # Instead of calling the actual Resolve-Pipeline which depends on Resolve-Role.ps1 and directory structures, 
        # we can source it and call Build-LifecycleV2
        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        # State check
        $lc.initial_state | Should -Be "developing"
        $lc.states.developing.role | Should -Be "game-architect"
        $lc.states.developing.type | Should -Be "work"
        $lc.states.developing.signals.done.target | Should -Be "developing-game-engineer"

        # Non-first workers get "developing-{roleName}" — never a raw role name
        $lc.states."developing-game-engineer".role | Should -Be "game-engineer"
        $lc.states."developing-game-engineer".type | Should -Be "work"
        $lc.states."developing-game-engineer".signals.done.target | Should -Be "review"

        $lc.states.review.role | Should -Be "game-qa"
        $lc.states.review.type | Should -Be "review"
        $lc.states.review.signals.pass.target | Should -Be "passed"
        $lc.states.review.signals.done.target | Should -Be "passed"
        
        # Error signal on review state (crash-loop guard)
        $lc.states.review.signals.error | Should -Not -BeNullOrEmpty
        $lc.states.review.signals.error.target | Should -Be "failed"
        $lc.states.review.signals.error.actions | Should -Contain "increment_retries"

        # Optimize states routing
        $lc.states.review.signals.fail.target | Should -Be "optimize-game-engineer"
        $lc.states."optimize-game-engineer".role | Should -Be "game-engineer"
        $lc.states.optimize.role | Should -Be "game-architect"
    }

    It "Builds lifecycle with single worker" {
        $roles = @(
            [PSCustomObject]@{ Name = 'game-ui-analyst'; InstanceType = 'worker' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        $lc.initial_state | Should -Be "developing"
        $lc.states.developing.role | Should -Be "game-ui-analyst"
        $lc.states.developing.signals.done.target | Should -Be "passed"

        $lc.states.optimize.role | Should -Be "game-ui-analyst"
        $lc.states.optimize.signals.done.target | Should -Be "passed"

        $lc.states.Keys -contains "game-ui-analyst-review" | Should -BeFalse
    }

    It "Builds lifecycle with single evaluator (no workers)" {
        $roles = @(
            [PSCustomObject]@{ Name = 'game-qa'; InstanceType = 'evaluator' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        $lc.initial_state | Should -Be "review"
        $lc.states.review.role | Should -Be "game-qa"
        
        # When an evaluator fails off the bat, since there are no prior workers, it should target failed
        $lc.states.review.signals.fail.target | Should -Be "failed"
        $lc.states.review.signals.pass.target | Should -Be "passed"
        $lc.states.review.signals.done.target | Should -Be "passed"
        
        # Error signal present even on standalone evaluator
        $lc.states.review.signals.error | Should -Not -BeNullOrEmpty
        $lc.states.review.signals.error.target | Should -Be "failed"
    }

    It "JSON output is valid and contains version 2" {
        $roles = @(
            [PSCustomObject]@{ Name = 'game-architect'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'game-qa'; InstanceType = 'evaluator' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3
        $json = $lc | ConvertTo-Json -Depth 10

        # Must be valid JSON
        $parsed = $json | ConvertFrom-Json
        $parsed.version | Should -Be 2
        $parsed.initial_state | Should -Be "developing"
        $parsed.states.passed.type | Should -Be "terminal"
        $parsed.states.'failed-final'.type | Should -Be "terminal"
    }

    It "All evaluator states include error signal targeting failed" {
        $roles = @(
            [PSCustomObject]@{ Name = 'designer'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'design-reviewer'; InstanceType = 'evaluator' },
            [PSCustomObject]@{ Name = 'final-qa'; InstanceType = 'evaluator' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        # Both evaluator states must have error signal
        foreach ($stateName in @('review', 'review-final-qa')) {
            $state = $lc.states[$stateName]
            $state | Should -Not -BeNullOrEmpty -Because "state '$stateName' should exist"
            $state.type | Should -Be 'review'
            $state.signals.error | Should -Not -BeNullOrEmpty -Because "evaluator state '$stateName' must handle agent crashes"
            $state.signals.error.target | Should -Be 'failed'
            $state.signals.error.actions | Should -Contain 'increment_retries'
        }
    }

    It "Worker and evaluator error signals both target failed state" {
        $roles = @(
            [PSCustomObject]@{ Name = 'eng'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'qa'; InstanceType = 'evaluator' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        # Worker error signal
        $lc.states.developing.signals.error.target | Should -Be 'failed'
        # Evaluator error signal
        $lc.states.review.signals.error.target | Should -Be 'failed'
    }
}
