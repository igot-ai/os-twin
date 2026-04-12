# Materialize-PlanRoles.ps1 — Contract Tests
#
# Verifies that the materialization script produces the exact artifacts
# that core runtime surfaces expect, without modifying any core files.

BeforeAll {
    $script:projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." ".." "..")).Path
    $script:materializeScript = Join-Path $script:projectRoot ".agents" "scripts" "Materialize-PlanRoles.ps1"
    $script:contributesDir = Join-Path $script:projectRoot "contributes" "roles"
    $script:planFile = Join-Path $script:projectRoot ".agents" "plans" "test-dynamic-roles.md"

    # Create isolated temp HOME to avoid polluting real ~/.ostwin
    $script:tempHome = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-test-$(Get-Random)"
    New-Item -ItemType Directory -Path $script:tempHome -Force | Out-Null

    $script:tempOstwinHome = Join-Path $script:tempHome ".ostwin"
    $script:tempXdgConfig = Join-Path $script:tempHome ".config"
}

AfterAll {
    if ($script:tempHome -and (Test-Path $script:tempHome)) {
        Remove-Item -Path $script:tempHome -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Describe "Materialize-PlanRoles.ps1 — Artifact Production" {

    BeforeEach {
        # Clean temp dirs before each test
        if (Test-Path $script:tempOstwinHome) { Remove-Item $script:tempOstwinHome -Recurse -Force }
        if (Test-Path $script:tempXdgConfig) { Remove-Item $script:tempXdgConfig -Recurse -Force }

        # Override env vars to point to temp HOME
        $env:OSTWIN_HOME = $script:tempOstwinHome
        $env:HOME = $script:tempHome
        $env:XDG_CONFIG_HOME = $script:tempXdgConfig
    }

    AfterEach {
        # Restore env
        Remove-Item Env:OSTWIN_HOME -ErrorAction SilentlyContinue
    }

    It "Parses roles from plan file and materializes contributed roles only" {
        & $script:materializeScript -PlanFile $script:planFile -ProjectDir $script:projectRoot

        # qa-test-planner is a contributed role — should be materialized
        $qatpRoleJson = Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json"
        Test-Path $qatpRoleJson | Should -BeTrue

        # engineer is a builtin — should NOT be materialized
        $engRoleJson = Join-Path $script:tempOstwinHome ".agents" "roles" "engineer" "role.json"
        Test-Path $engRoleJson | Should -BeFalse
    }

    It "Produces role.json at ~/.ostwin/.agents/roles/<role>/ (Invoke-Agent surface)" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"

        $dest = Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json"
        Test-Path $dest | Should -BeTrue

        $data = Get-Content $dest -Raw | ConvertFrom-Json
        $data.model | Should -Not -BeNullOrEmpty
    }

    It "Produces role.json at ~/.ostwin/roles/<role>/ (Resolve-RoleSkills surface)" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"

        $dest = Join-Path $script:tempOstwinHome "roles" "qa-test-planner" "role.json"
        Test-Path $dest | Should -BeTrue
    }

    It "Produces ROLE.md at ~/.ostwin/.agents/roles/<role>/ (Build-SystemPrompt surface)" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"

        $dest = Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "ROLE.md"
        Test-Path $dest | Should -BeTrue

        $content = Get-Content $dest -Raw
        $content | Should -Match "qa-test-planner"
        $content.Length | Should -BeGreaterThan 200
    }

    It "Produces <role>.md at ~/.config/opencode/agents/ (OpenCode agent surface)" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"

        $dest = Join-Path $script:tempXdgConfig "opencode" "agents" "qa-test-planner.md"
        Test-Path $dest | Should -BeTrue
    }

    It "Produces plan.roles.json with model/timeout from role.json" {
        & $script:materializeScript -Roles @("qa-test-planner", "test-engineer") -ProjectDir $script:projectRoot -PlanId "test-dynamic-roles"

        $dest = Join-Path $script:tempOstwinHome ".agents" "plans" "test-dynamic-roles.roles.json"
        Test-Path $dest | Should -BeTrue

        $data = Get-Content $dest -Raw | ConvertFrom-Json
        $data."qa-test-planner" | Should -Not -BeNullOrEmpty
        $data."test-engineer" | Should -Not -BeNullOrEmpty
        $data."test-engineer".default_model | Should -Not -BeNullOrEmpty
    }

    It "Merges into existing plan.roles.json without overwriting builtin entries" {
        # Pre-seed plan.roles.json with a builtin role config
        $planDir = Join-Path $script:tempOstwinHome ".agents" "plans"
        New-Item -ItemType Directory -Path $planDir -Force | Out-Null
        $planRolesFile = Join-Path $planDir "test-merge.roles.json"
        @{ engineer = @{ default_model = "gpt-4o"; timeout_seconds = 900 } } |
            ConvertTo-Json -Depth 5 | Out-File $planRolesFile -Encoding utf8

        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test-merge"

        $data = Get-Content $planRolesFile -Raw | ConvertFrom-Json
        # Builtin entry preserved
        $data.engineer.default_model | Should -Be "gpt-4o"
        # Contributed entry added
        $data."qa-test-planner" | Should -Not -BeNullOrEmpty
    }

    It "Is idempotent — running twice produces same result" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"
        $first = Get-Content (Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json") -Raw

        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"
        $second = Get-Content (Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json") -Raw

        $first | Should -Be $second
    }

    It "Materializes all 11 contributed dynamic roles from the test plan" {
        & $script:materializeScript -PlanFile $script:planFile -ProjectDir $script:projectRoot

        $expectedRoles = @(
            "requirement-analyst", "architecture-advisor",
            "code-generator", "code-reviewer",
            "qa-test-planner", "test-engineer",
            "bug-hunter", "refactoring-agent",
            "security-scanner",
            "devops-agent", "documentation-agent"
        )

        foreach ($role in $expectedRoles) {
            $homeAgents = Join-Path $script:tempOstwinHome ".agents" "roles" $role "role.json"
            Test-Path $homeAgents | Should -BeTrue -Because "role.json for $role should exist at ~/.ostwin/.agents/roles/"

            $homeRoles = Join-Path $script:tempOstwinHome "roles" $role "role.json"
            Test-Path $homeRoles | Should -BeTrue -Because "role.json for $role should exist at ~/.ostwin/roles/"

            $agentMd = Join-Path $script:tempXdgConfig "opencode" "agents" "$role.md"
            Test-Path $agentMd | Should -BeTrue -Because "ROLE.md for $role should exist at ~/.config/opencode/agents/"
        }
    }

    It "DryRun does not write any files" {
        & $script:materializeScript -Roles @("qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test" -DryRun

        $dest = Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json"
        Test-Path $dest | Should -BeFalse
    }

    It "Materializes room overrides when WarRoomsDir is provided" {
        # Create a fake room with lifecycle referencing qa-test-planner
        $fakeWarRooms = Join-Path $script:tempHome "war-rooms"
        $fakeRoom = Join-Path $fakeWarRooms "room-001"
        New-Item -ItemType Directory -Path $fakeRoom -Force | Out-Null

        $lifecycle = @{
            version = 2
            initial_state = "developing"
            states = @{
                developing = @{ role = "test-engineer"; type = "work" }
                "qa-test-planner-review" = @{ role = "qa-test-planner"; type = "review" }
            }
        }
        $lifecycle | ConvertTo-Json -Depth 5 | Out-File (Join-Path $fakeRoom "lifecycle.json") -Encoding utf8

        & $script:materializeScript -Roles @("qa-test-planner", "test-engineer") -ProjectDir $script:projectRoot -PlanId "test" -WarRoomsDir $fakeWarRooms

        # Room overrides should exist
        $overrideRoleJson = Join-Path $fakeRoom "overrides" "qa-test-planner" "role.json"
        Test-Path $overrideRoleJson | Should -BeTrue

        $overrideRoleMd = Join-Path $fakeRoom "overrides" "qa-test-planner" "ROLE.md"
        Test-Path $overrideRoleMd | Should -BeTrue

        $teOverride = Join-Path $fakeRoom "overrides" "test-engineer" "role.json"
        Test-Path $teOverride | Should -BeTrue
    }
}

Describe "Materialize-PlanRoles.ps1 — Builtin Role Safety" {

    BeforeEach {
        if (Test-Path $script:tempOstwinHome) { Remove-Item $script:tempOstwinHome -Recurse -Force }
        $env:OSTWIN_HOME = $script:tempOstwinHome
        $env:HOME = $script:tempHome
        $env:XDG_CONFIG_HOME = $script:tempXdgConfig
    }

    AfterEach {
        Remove-Item Env:OSTWIN_HOME -ErrorAction SilentlyContinue
    }

    It "Does not materialize builtin roles (engineer, qa, architect, manager)" {
        & $script:materializeScript -Roles @("engineer", "qa", "architect", "manager", "qa-test-planner") -ProjectDir $script:projectRoot -PlanId "test"

        foreach ($builtin in @("engineer", "qa", "architect", "manager")) {
            $dest = Join-Path $script:tempOstwinHome ".agents" "roles" $builtin "role.json"
            Test-Path $dest | Should -BeFalse -Because "$builtin is a builtin role and should not be materialized"
        }

        # But contributed role should be materialized
        $dest = Join-Path $script:tempOstwinHome ".agents" "roles" "qa-test-planner" "role.json"
        Test-Path $dest | Should -BeTrue
    }
}
