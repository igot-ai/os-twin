Describe "Resolve-RoleSkills" {
    BeforeAll {
        $script:resolveScript = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Resolve-RoleSkills.ps1"
        $script:baseDir = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_skills"
        $script:testRolePath = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_role"

        # Override HOME so the script finds role.json at ~/.ostwin/roles/<name>/role.json
        $script:origHome = $env:HOME
        $script:fakeHome = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_fakehome"

        # Helper: write role.json to the HOME-based path the script expects
        function script:Set-TestRoleJson {
            param([string]$RoleName, [hashtable]$Data)
            $roleDir = Join-Path $script:fakeHome ".ostwin" "roles" $RoleName
            New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
            $Data | ConvertTo-Json | Out-File -FilePath (Join-Path $roleDir "role.json") -Encoding utf8
        }
    }

    BeforeEach {
        # Clean test directories before each test
        if (Test-Path $script:baseDir) { Remove-Item $script:baseDir -Recurse -Force }
        if (Test-Path $script:fakeHome) { Remove-Item $script:fakeHome -Recurse -Force }
        if (Test-Path $script:testRolePath) { Remove-Item $script:testRolePath -Recurse -Force }

        # Create base skills directory structure
        New-Item -ItemType Directory -Path $script:baseDir -Force | Out-Null
        New-Item -ItemType Directory -Path $script:testRolePath -Force | Out-Null

        $env:HOME = $script:fakeHome
    }

    AfterAll {
        $env:HOME = $script:origHome
        if (Test-Path $script:baseDir) { Remove-Item $script:baseDir -Recurse -Force }
        if (Test-Path $script:testRolePath) { Remove-Item $script:testRolePath -Recurse -Force }
        if (Test-Path $script:fakeHome) { Remove-Item $script:fakeHome -Recurse -Force }
    }

    Context "Flat path resolution" {
        It "resolves skill from flat skills/<ref>/SKILL.md" {
            # Setup: skill at flat path
            mkdir -p (Join-Path $script:baseDir "lang")
            "Lang Skill content" > (Join-Path $script:baseDir "lang" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("lang")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $skills.Count | Should -Be 1
            ($skills | Where-Object { $_.Name -eq "lang" }).Tier | Should -Be "Explicit"
        }

        It "resolves multiple skills from skill_refs" {
            mkdir -p (Join-Path $script:baseDir "skill-a")
            "Skill A" > (Join-Path $script:baseDir "skill-a" "SKILL.md")
            mkdir -p (Join-Path $script:baseDir "skill-b")
            "Skill B" > (Join-Path $script:baseDir "skill-b" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("skill-a", "skill-b")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir
            $skills.Count | Should -Be 2
        }
    }

    Context "Hierarchical path resolution (Bug 2 fix)" {
        It "resolves skill from skills/roles/<roleName>/<ref>/ when flat path does not exist" {
            # Skill only exists under roles/game-engineer/build-ui, NOT at flat skills/build-ui
            mkdir -p (Join-Path $script:baseDir "roles" "game-engineer" "build-ui")
            "Build UI Skill content" > (Join-Path $script:baseDir "roles" "game-engineer" "build-ui" "SKILL.md")

            Set-TestRoleJson -RoleName "game-engineer" -Data @{
                name = "game-engineer"
                skill_refs = @("build-ui")
            }

            $skills = & $script:resolveScript -RoleName "game-engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            ($skills | Where-Object { $_.Name -eq "build-ui" }) | Should -Not -BeNullOrEmpty
        }

        It "resolves skill from skills/global/<ref>/ when flat path does not exist" {
            # Skill only exists under global/shared-memory
            mkdir -p (Join-Path $script:baseDir "global" "shared-memory")
            "Shared Memory Skill" > (Join-Path $script:baseDir "global" "shared-memory" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("shared-memory")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            ($skills | Where-Object { $_.Name -eq "shared-memory" }) | Should -Not -BeNullOrEmpty
        }

        It "resolves skill from a different role's directory via hierarchical search" {
            # Engineer references a skill that lives under skills/roles/qa/
            mkdir -p (Join-Path $script:baseDir "roles" "qa" "code-review")
            "Code Review Skill" > (Join-Path $script:baseDir "roles" "qa" "code-review" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("code-review")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            ($skills | Where-Object { $_.Name -eq "code-review" }) | Should -Not -BeNullOrEmpty
        }

        It "prefers own role's skill directory over other roles" {
            # Skill exists in both roles/engineer/ and roles/qa/
            mkdir -p (Join-Path $script:baseDir "roles" "engineer" "review-skill")
            "Engineer version" > (Join-Path $script:baseDir "roles" "engineer" "review-skill" "SKILL.md")
            mkdir -p (Join-Path $script:baseDir "roles" "qa" "review-skill")
            "QA version" > (Join-Path $script:baseDir "roles" "qa" "review-skill" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("review-skill")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $resolved = $skills | Where-Object { $_.Name -eq "review-skill" }
            $resolved | Should -Not -BeNullOrEmpty
            $resolved.Path | Should -Match "roles[\\/]engineer[\\/]review-skill"
        }

        It "resolves flat path before hierarchical paths" {
            # Skill exists at BOTH flat and role paths — flat should win
            mkdir -p (Join-Path $script:baseDir "dual-skill")
            "Flat version" > (Join-Path $script:baseDir "dual-skill" "SKILL.md")
            mkdir -p (Join-Path $script:baseDir "roles" "engineer" "dual-skill")
            "Role version" > (Join-Path $script:baseDir "roles" "engineer" "dual-skill" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("dual-skill")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $resolved = $skills | Where-Object { $_.Name -eq "dual-skill" }
            $resolved | Should -Not -BeNullOrEmpty
            # Flat path is searched first (before hierarchical)
            $resolved.Path | Should -Not -Match "roles[\\/]engineer"
        }
    }

    Context "Role-private auto-loading" {
        It "auto-loads skills under skills/roles/<RoleName>/ even without skill_refs" {
            # Two private skills for game-engineer; role.json has no skill_refs
            mkdir -p (Join-Path $script:baseDir "roles" "game-engineer" "build-ui")
            "Build UI" > (Join-Path $script:baseDir "roles" "game-engineer" "build-ui" "SKILL.md")
            mkdir -p (Join-Path $script:baseDir "roles" "game-engineer" "build-anim")
            "Build Anim" > (Join-Path $script:baseDir "roles" "game-engineer" "build-anim" "SKILL.md")

            Set-TestRoleJson -RoleName "game-engineer" -Data @{
                name = "game-engineer"
            }

            $skills = & $script:resolveScript -RoleName "game-engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $names = @($skills | ForEach-Object { $_.Name })
            $names | Should -Contain "build-ui"
            $names | Should -Contain "build-anim"
            ($skills | Where-Object { $_.Name -eq "build-ui" }).Tier | Should -Be "RoleAuto"
        }

        It "does not auto-load skills from other roles' private buckets" {
            # qa has a private skill; engineer should NOT pick it up
            mkdir -p (Join-Path $script:baseDir "roles" "qa" "code-review")
            "QA Review" > (Join-Path $script:baseDir "roles" "qa" "code-review" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir
            $skills.Count | Should -Be 0
        }

        It "explicit skill_ref tier wins over auto-loaded tier for the same skill" {
            mkdir -p (Join-Path $script:baseDir "roles" "engineer" "shared-tool")
            "Shared Tool" > (Join-Path $script:baseDir "roles" "engineer" "shared-tool" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("shared-tool")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $skills.Count | Should -Be 1
            ($skills | Where-Object { $_.Name -eq "shared-tool" }).Tier | Should -Be "Explicit"
        }

        It "auto-loads role-private skills from ~/.ostwin/.agents/skills/roles/<RoleName>/" {
            # Seed a private skill in the fake-HOME ostwin tree, NOT in the project tree
            $homeSkillsDir = Join-Path $script:fakeHome ".ostwin" ".agents" "skills" "roles" "game-engineer" "unity-templates"
            New-Item -ItemType Directory -Path $homeSkillsDir -Force | Out-Null
            "Unity Templates" > (Join-Path $homeSkillsDir "SKILL.md")

            Set-TestRoleJson -RoleName "game-engineer" -Data @{
                name = "game-engineer"
            }

            $skills = & $script:resolveScript -RoleName "game-engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $resolved = $skills | Where-Object { $_.Name -eq "unity-templates" }
            $resolved | Should -Not -BeNullOrEmpty
            $resolved.Tier | Should -Be "RoleAuto"
            $resolved.Path | Should -Match "\.ostwin[\\/]\.agents[\\/]skills[\\/]roles[\\/]game-engineer[\\/]unity-templates"
        }

        It "merges auto-loaded skills from project and home trees" {
            # One private skill in the project tree
            mkdir -p (Join-Path $script:baseDir "roles" "engineer" "project-only")
            "Project Only" > (Join-Path $script:baseDir "roles" "engineer" "project-only" "SKILL.md")

            # A different private skill in the home tree
            $homeSkillsDir = Join-Path $script:fakeHome ".ostwin" ".agents" "skills" "roles" "engineer" "home-only"
            New-Item -ItemType Directory -Path $homeSkillsDir -Force | Out-Null
            "Home Only" > (Join-Path $homeSkillsDir "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $names = @($skills | ForEach-Object { $_.Name })
            $names | Should -Contain "project-only"
            $names | Should -Contain "home-only"
        }

        It "skips auto-loaded skills that are explicitly disabled" {
            $skillDir = Join-Path $script:baseDir "roles" "engineer" "disabled-skill"
            New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
            @"
---
name: disabled-skill
enabled: false
---
Disabled body
"@ | Out-File -FilePath (Join-Path $skillDir "SKILL.md") -Encoding utf8

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir
            ($skills | Where-Object { $_.Name -eq "disabled-skill" }) | Should -BeNullOrEmpty
        }
    }

    Context "Deduplication" {
        It "deduplicates when skill appears in both skill_refs and capabilities" {
            mkdir -p (Join-Path $script:baseDir "lang")
            "Lang Skill" > (Join-Path $script:baseDir "lang" "SKILL.md")

            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("lang")
                capabilities = @("lang")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir
            $skills.Count | Should -Be 1
        }
    }

    Context "Error handling" {
        It "throws error for missing explicit skill" {
            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("non-existent-skill")
            }

            { & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir } | Should -Throw "Skill Not Found*"
        }

        It "returns empty array when role.json does not exist" {
            # No role.json at HOME path, no registry
            $skills = & $script:resolveScript -RoleName "missing-role" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir
            $skills.Count | Should -Be 0
        }

        It "returns empty when skills base dir does not exist" {
            Set-TestRoleJson -RoleName "engineer" -Data @{
                name = "engineer"
                skill_refs = @("lang")
            }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir "/nonexistent/path"
            $skills.Count | Should -Be 0
        }
    }
}
