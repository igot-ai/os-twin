# Agent OS — Resolve-Pipeline.ps1 Unit Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../lifecycle").Path "..")).Path
    $script:ResolvePipeline = Join-Path $script:agentsDir "lifecycle" "Resolve-Pipeline.ps1"
}

Describe "Resolve-Pipeline.ps1 — Dynamic Lifecycle Generation" {
    It "Builds lifecycle with three candidates (position-based)" {
        # Position-based: [0]=worker, [1..N]=evaluators
        # RoleOverrides kept for backward compat — InstanceType is ignored,
        # only Name and position matter.
        $roles = @(
            [PSCustomObject]@{ Name = 'game-architect'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'game-engineer'; InstanceType = 'worker' },
            [PSCustomObject]@{ Name = 'game-qa'; InstanceType = 'evaluator' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        # State check — position-based: [0]=worker, [1..N]=evaluators
        $lc.initial_state | Should -Be "developing"
        $lc.states.developing.role | Should -Be "game-architect"
        $lc.states.developing.type | Should -Be "work"
        $lc.states.developing.signals.done.target | Should -Be "game-engineer-review"

        # Position [1] is evaluator with {role}-review naming
        $lc.states."game-engineer-review".role | Should -Be "game-engineer"
        $lc.states."game-engineer-review".type | Should -Be "review"
        $lc.states."game-engineer-review".signals.pass.target | Should -Be "game-qa-review"

        # Position [2] is evaluator — final gate
        $lc.states."game-qa-review".role | Should -Be "game-qa"
        $lc.states."game-qa-review".type | Should -Be "review"
        $lc.states."game-qa-review".signals.pass.target | Should -Be "passed"
        $lc.states."game-qa-review".signals.done.target | Should -Be "passed"

        # Error signal on evaluator states (crash-loop guard)
        $lc.states."game-qa-review".signals.error | Should -Not -BeNullOrEmpty
        $lc.states."game-qa-review".signals.error.target | Should -Be "failed"
        $lc.states."game-qa-review".signals.error.actions | Should -Contain "increment_retries"

        # Evaluator fail → optimize (worker's optimize state)
        $lc.states."game-qa-review".signals.fail.target | Should -Be "optimize"

        # Optimize state carries the worker role
        $lc.states.optimize.role | Should -Be "game-architect"
    }

    It "Builds lifecycle with single candidate — QA review injected" {
        $roles = @(
            [PSCustomObject]@{ Name = 'game-ui-analyst'; InstanceType = 'worker' }
        )

        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -RoleOverrides $roles -MaxRetries 3

        $lc.initial_state | Should -Be "developing"
        $lc.states.developing.role | Should -Be "game-ui-analyst"
        # Single candidate → QA review injected as final gate
        $lc.states.developing.signals.done.target | Should -Be "review"

        $lc.states.optimize.role | Should -Be "game-ui-analyst"
        $lc.states.optimize.signals.done.target | Should -Be "review"

        # Injected QA review state
        $lc.states.review.role | Should -Be "qa"
        $lc.states.review.type | Should -Be "review"
        $lc.states.review.signals.pass.target | Should -Be "passed"
    }

    It "Single candidate via -Roles string array also works" {
        . $script:ResolvePipeline -PipelineString "just_to_source_functions" -ErrorAction SilentlyContinue

        $lc = Build-LifecycleV2 -Roles @('game-qa') -MaxRetries 3

        # Position [0] is always the worker regardless of role name
        $lc.initial_state | Should -Be "developing"
        $lc.states.developing.role | Should -Be "game-qa"

        # Single candidate → QA review injected
        $lc.states.review.role | Should -Be "qa"
        $lc.states.review.signals.fail.target | Should -Be "optimize"
        $lc.states.review.signals.pass.target | Should -Be "passed"
        $lc.states.review.signals.done.target | Should -Be "passed"

        # Error signal present on injected review
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

        # Position-based: design-reviewer-review and final-qa-review
        foreach ($stateName in @('design-reviewer-review', 'final-qa-review')) {
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
        # Evaluator error signal (qa-review, position-based naming)
        $lc.states.'qa-review'.signals.error.target | Should -Be 'failed'
    }
}
