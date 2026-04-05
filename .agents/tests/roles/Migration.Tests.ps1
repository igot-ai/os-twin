# EPIC-001 Skills Migration Tests

Describe "Registry Schema Migration" {
    BeforeAll {
        $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
        $script:rolesDir = Join-Path $script:agentsDir "roles"
        $script:registryFile = Join-Path $script:rolesDir "registry.json"
    }

    It "registry.json should exist" {
        Test-Path $script:registryFile | Should -Be $true
    }

    It "should contain tags and trust_level for all available skills" {
        $registry = Get-Content $script:registryFile -Raw | ConvertFrom-Json
        $registry.skills.available | ForEach-Object {
            $_.tags | Should -Not -BeNullOrEmpty
            $_.trust_level | Should -Match '^(core|experimental|certified)$'
        }
    }

    It "should contain legacy 'skills' string field for all available skills" {
        $registry = Get-Content $script:registryFile -Raw | ConvertFrom-Json
        $registry.skills.available | ForEach-Object {
            $_.skills | Should -Not -BeNullOrEmpty
            $_.skills | Should -BeOfType [string]
        }
    }
}

Describe "Role Definition Migration" {
    BeforeAll {
        $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
        $script:rolesDir = Join-Path $script:agentsDir "roles"
    }

    It "All roles should contain skill_refs property" {
        $roles = @("engineer", "qa", "architect")
        foreach ($roleName in $roles) {
            $roleFile = Join-Path $script:rolesDir $roleName "role.json"
            Write-Host "Checking '$roleFile'"
            $roleData = Get-Content $roleFile -Raw | ConvertFrom-Json
            # Check if property exists using PSObject
            $hasProp = $null -ne ($roleData.PSObject.Properties | Where-Object { $_.Name -eq "skill_refs" })
            if (-not $hasProp) {
                Write-Error "Role $roleName is missing skill_refs"
            }
            $hasProp | Should -Be $true
        }
    }

    It "Architect role should have specific skills" {
        $roleFile = Join-Path $script:rolesDir "architect" "role.json"
        $roleData = Get-Content $roleFile -Raw | ConvertFrom-Json
        $roleData.skill_refs | Should -Contain "create-architecture"
        $roleData.skill_refs | Should -Contain "create-lifecycle"
        $roleData.skill_refs | Should -Contain "create-role"
    }

    It "Core implementation and orchestration roles should declare baseline skill_refs" {
        $expectedByRole = [ordered]@{
            "engineer" = @("implement-epic", "fix-from-qa", "refactor-code", "write-tests")
            "backend-engineer" = @("implement-epic", "fix-from-qa", "refactor-code", "write-tests")
            "frontend-engineer" = @("implement-epic", "fix-from-qa", "refactor-code", "write-tests")
            "qa" = @("review-epic", "review-task", "security-review")
            "reporter" = @("generate-report", "data-visualization")
            "manager" = @("assign-epic", "coordinate-release", "discover-skills", "triage-failure")
        }

        foreach ($roleName in $expectedByRole.Keys) {
            $roleFile = Join-Path $script:rolesDir $roleName "role.json"
            $roleData = Get-Content $roleFile -Raw | ConvertFrom-Json
            foreach ($skillName in $expectedByRole[$roleName]) {
                $roleData.skill_refs | Should -Contain $skillName
            }
        }
    }

    It "Aggregate role catalog should mirror baseline skill_refs for shipped core roles" {
        $catalogFile = Join-Path $script:rolesDir "config.json"
        $catalog = Get-Content $catalogFile -Raw | ConvertFrom-Json
        $expectedByRole = [ordered]@{
            "engineer" = @("implement-epic", "fix-from-qa", "refactor-code", "write-tests")
            "qa" = @("review-epic", "review-task", "security-review")
            "manager" = @("assign-epic", "coordinate-release", "discover-skills", "triage-failure")
            "reporter" = @("generate-report", "data-visualization")
        }

        foreach ($roleName in $expectedByRole.Keys) {
            $catalogRole = $catalog | Where-Object { $_.name -eq $roleName } | Select-Object -First 1
            $catalogRole | Should -Not -BeNullOrEmpty
            foreach ($skillName in $expectedByRole[$roleName]) {
                $catalogRole.skill_refs | Should -Contain $skillName
            }
        }
    }
}

Describe "SKILL.md Frontmatter Migration" {
    BeforeAll {
        $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
        $script:skillsDir = Join-Path $script:agentsDir "skills"
        $script:registryFile = Join-Path $script:agentsDir "roles" "registry.json"
    }

    It "All skills in registry should have structured frontmatter at specified paths" {
        $registry = Get-Content $script:registryFile -Raw | ConvertFrom-Json
        foreach ($skill in $registry.skills.available) {
            $skillName = $skill.name
            $skillPath = $skill.path
            $skillMd = Join-Path $script:agentsDir $skillPath
            Write-Host "Checking '$skillMd'"
            if (-not (Test-Path $skillMd)) {
                Write-Error "File not found: $skillMd (from registry path: $skillPath)"
                $false | Should -Be $true
            }
            $content = Get-Content $skillMd -Raw
            $content | Should -Match '(?s)^---\n.*tags: \[.*\].*trust_level: .*\n---\n'
        }
    }
}

Describe "Manager Configuration" {
    BeforeAll {
        $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/..").Path "..")).Path
        $script:configFile = Join-Path $script:agentsDir "config.json"
    }

    It "config.json should have preflight_skill_check: warn" {
        $config = Get-Content $script:configFile -Raw | ConvertFrom-Json
        $config.manager.preflight_skill_check | Should -Be "warn"
    }

    It "manager config should declare orchestration skill_refs" {
        $config = Get-Content $script:configFile -Raw | ConvertFrom-Json
        $config.manager.skill_refs | Should -Contain "assign-epic"
        $config.manager.skill_refs | Should -Contain "coordinate-release"
        $config.manager.skill_refs | Should -Contain "discover-skills"
        $config.manager.skill_refs | Should -Contain "triage-failure"
    }
}
