Describe "Resolve-RoleSkills" {
    BeforeAll {
        $script:resolveScript = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Resolve-RoleSkills.ps1"
        $script:baseDir = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_skills"
        $script:testRolePath = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_role"

        # Override HOME so registry lookups use a controlled path
        $script:origHome = $env:HOME
        $script:fakeHome = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "test_fakehome"

        # Helper: create a room dir with a brief.md
        function script:New-TestRoom {
            param([string]$BriefContent = "Implement data parsing pipeline")
            $roomDir = Join-Path $TestDrive "room-$(Get-Random)"
            New-Item -ItemType Directory -Path $roomDir -Force | Out-Null
            if ($BriefContent) {
                $BriefContent | Out-File -FilePath (Join-Path $roomDir "brief.md") -Encoding utf8
            }
            return $roomDir
        }

        # Helper: create a local skill under the skills base dir
        function script:New-TestSkill {
            param(
                [string]$Name,
                [string]$Location = "flat",     # flat | global | roles/<roleName>
                [string]$Content = "# $Name skill content",
                [string]$Frontmatter = ""
            )
            $dir = switch ($Location) {
                "flat"   { Join-Path $script:baseDir $Name }
                "global" { Join-Path $script:baseDir "global" $Name }
                default  { Join-Path $script:baseDir $Location $Name }
            }
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            $fullContent = if ($Frontmatter) { "$Frontmatter`n$Content" } else { $Content }
            $fullContent | Out-File -FilePath (Join-Path $dir "SKILL.md") -Encoding utf8
            return $dir
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
        # Ensure OSTWIN_API_KEY is unset unless tests set it explicitly
        $script:origApiKey = $env:OSTWIN_API_KEY
        $env:OSTWIN_API_KEY = ''
    }

    AfterEach {
        $env:OSTWIN_API_KEY = $script:origApiKey
    }

    AfterAll {
        $env:HOME = $script:origHome
        if (Test-Path $script:baseDir) { Remove-Item $script:baseDir -Recurse -Force }
        if (Test-Path $script:testRolePath) { Remove-Item $script:testRolePath -Recurse -Force }
        if (Test-Path $script:fakeHome) { Remove-Item $script:fakeHome -Recurse -Force }
    }

    # =======================================================================
    # API SEARCH AS SOLE SOURCE — no-mock tests
    # =======================================================================
    Context "API search is the sole source of skill refs (no-mock)" {
        It "returns empty when no RoomDir is provided" {
            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath -SkillsBaseDir $script:baseDir

            $skills.Count | Should -Be 0
        }

        It "returns empty when RoomDir has no brief.md" {
            $roomDir = Join-Path $TestDrive "empty-room-$(Get-Random)"
            New-Item -ItemType Directory -Path $roomDir -Force | Out-Null

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir

            $skills.Count | Should -Be 0
        }

        It "returns empty when brief.md content is whitespace-only" {
            $roomDir = New-TestRoom -BriefContent "   "

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir

            $skills.Count | Should -Be 0
        }

        It "returns empty when API is unreachable" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "lang" -Location "flat"

            # Point to a non-existent server so Invoke-RestMethod fails
            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://127.0.0.1:19999"

            # Even with a local skill present, it should NOT be loaded without API discovery
            $skills.Count | Should -Be 0
        }

        It "returns empty when skills base dir does not exist" {
            $roomDir = New-TestRoom

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir "/nonexistent/path" -RoomDir $roomDir

            $skills.Count | Should -Be 0
        }
    }

    # =======================================================================
    # API-DRIVEN RESOLUTION — mocked Invoke-RestMethod
    # =======================================================================
    Context "API-driven skill resolution" {
        BeforeAll {
            Mock Invoke-RestMethod {
                return @(
                    [PSCustomObject]@{ name = "validate-output"; relative_path = "skills/validate-output" },
                    [PSCustomObject]@{ name = "lang"; relative_path = "skills/lang" }
                )
            }
        }

        It "resolves skills returned by API search to local paths" {
            $roomDir = New-TestRoom -BriefContent "Build CSV parser with validation"
            New-TestSkill -Name "validate-output" -Location "flat"
            New-TestSkill -Name "lang" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 2
            ($skills | Where-Object { $_.Name -eq "validate-output" }) | Should -Not -BeNullOrEmpty
            ($skills | Where-Object { $_.Name -eq "lang" }) | Should -Not -BeNullOrEmpty
        }
    }

    Context "API results capped at 5" {
        BeforeAll {
            Mock Invoke-RestMethod {
                return @(
                    [PSCustomObject]@{ name = "skill-1" }, [PSCustomObject]@{ name = "skill-2" },
                    [PSCustomObject]@{ name = "skill-3" }, [PSCustomObject]@{ name = "skill-4" },
                    [PSCustomObject]@{ name = "skill-5" }, [PSCustomObject]@{ name = "skill-6" },
                    [PSCustomObject]@{ name = "skill-7" }
                )
            }
        }

        It "caps results to first 5 from API" {
            $roomDir = New-TestRoom
            1..7 | ForEach-Object { New-TestSkill -Name "skill-$_" -Location "flat" }

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 5
        }
    }

    Context "API returns empty results" {
        BeforeAll {
            Mock Invoke-RestMethod { return @() }
        }

        It "returns empty even when local skills exist" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "lang" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }
    }

    # =======================================================================
    # NO FALLBACK LOADING
    # =======================================================================
    Context "No fallback loading from role.json, config.json, or auto-discovery" {
        BeforeAll {
            Mock Invoke-RestMethod { return @() }
        }

        It "does NOT load skills from role.json skill_refs" {
            $roomDir = New-TestRoom

            $roleDir = Join-Path $script:fakeHome ".ostwin" "roles" "engineer"
            New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
            @{ name = "engineer"; skill_refs = @("lang", "write-tests") } |
                ConvertTo-Json | Out-File -FilePath (Join-Path $roleDir "role.json") -Encoding utf8

            New-TestSkill -Name "lang" -Location "flat"
            New-TestSkill -Name "write-tests" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }

        It "does NOT load skills from role.json capabilities" {
            $roomDir = New-TestRoom

            $roleDir = Join-Path $script:fakeHome ".ostwin" "roles" "engineer"
            New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
            @{ name = "engineer"; capabilities = @("code-review", "refactor") } |
                ConvertTo-Json | Out-File -FilePath (Join-Path $roleDir "role.json") -Encoding utf8

            New-TestSkill -Name "code-review" -Location "flat"
            New-TestSkill -Name "refactor" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }

        It "does NOT load skills from room config.json skill_refs" {
            $roomDir = New-TestRoom
            $configFile = Join-Path $roomDir "config.json"
            @{ skill_refs = @("lang", "validate-output") } |
                ConvertTo-Json | Out-File -FilePath $configFile -Encoding utf8

            New-TestSkill -Name "lang" -Location "flat"
            New-TestSkill -Name "validate-output" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }

        It "does NOT auto-load role-private skills" {
            $roomDir = New-TestRoom

            New-TestSkill -Name "build-ui" -Location "roles/engineer"
            New-TestSkill -Name "build-anim" -Location "roles/engineer"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }

        It "does NOT load plan-level override skills" {
            $roomDir = New-TestRoom

            $planDir = Join-Path $script:fakeHome ".ostwin" ".agents" "plans"
            New-Item -ItemType Directory -Path $planDir -Force | Out-Null
            @{ engineer = @{ skill_refs = @("lang", "write-tests") } } |
                ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $planDir "test-plan.roles.json") -Encoding utf8

            New-TestSkill -Name "lang" -Location "flat"
            New-TestSkill -Name "write-tests" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -PlanId "test-plan" -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }
    }

    # =======================================================================
    # LOCAL RESOLUTION OF API-RETURNED REFS
    # =======================================================================
    Context "Hierarchical resolution: flat path" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "lang" }) }
        }

        It "resolves from flat skills/<ref>/SKILL.md" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "lang" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 1
            $skills[0].Name | Should -Be "lang"
            $skills[0].Tier | Should -Be "Explicit"
        }
    }

    Context "Hierarchical resolution: own-role path" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "build-ui" }) }
        }

        It "resolves from skills/roles/<RoleName>/<ref>/SKILL.md" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "build-ui" -Location "roles/game-engineer"

            $skills = & $script:resolveScript -RoleName "game-engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            ($skills | Where-Object { $_.Name -eq "build-ui" }) | Should -Not -BeNullOrEmpty
        }
    }

    Context "Hierarchical resolution: global path" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "auto-memory" }) }
        }

        It "resolves from skills/global/<ref>/SKILL.md" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "auto-memory" -Location "global"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            ($skills | Where-Object { $_.Name -eq "auto-memory" }) | Should -Not -BeNullOrEmpty
        }
    }

    Context "Hierarchical resolution: cross-role path" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "code-review" }) }
        }

        It "resolves from another role's directory when not in own role" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "code-review" -Location "roles/qa"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            ($skills | Where-Object { $_.Name -eq "code-review" }) | Should -Not -BeNullOrEmpty
        }
    }

    Context "Hierarchical resolution: own-role priority" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "review-skill" }) }
        }

        It "prefers own role's skill directory over other roles" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "review-skill" -Location "roles/engineer" -Content "Engineer version"
            New-TestSkill -Name "review-skill" -Location "roles/qa" -Content "QA version"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $resolved = $skills | Where-Object { $_.Name -eq "review-skill" }
            $resolved | Should -Not -BeNullOrEmpty
            $resolved.Path | Should -Match "roles[\\/]engineer[\\/]review-skill"
        }

        It "prefers own-role path over flat path" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "review-skill" -Location "flat" -Content "Flat version"
            New-TestSkill -Name "review-skill" -Location "roles/engineer" -Content "Role version"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $resolved = $skills | Where-Object { $_.Name -eq "review-skill" }
            $resolved | Should -Not -BeNullOrEmpty
            $resolved.Path | Should -Match "roles[\\/]engineer[\\/]review-skill"
        }
    }

    # =======================================================================
    # PLATFORM & ENABLED GATES
    # =======================================================================
    Context "Platform gate" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "win-only" }) }
        }

        It "skips platform-incompatible skills" {
            $roomDir = New-TestRoom
            $frontmatter = @"
---
name: win-only
platform: ["windows"]
---
"@
            New-TestSkill -Name "win-only" -Location "flat" -Frontmatter $frontmatter

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            # On macOS/Linux this should be skipped
            if (-not $IsWindows) {
                $skills.Count | Should -Be 0
            }
        }
    }

    Context "Enabled gate" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "disabled-skill" }) }
        }

        It "skips disabled skills" {
            $roomDir = New-TestRoom
            $frontmatter = @"
---
name: disabled-skill
enabled: false
---
"@
            New-TestSkill -Name "disabled-skill" -Location "flat" -Frontmatter $frontmatter

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            ($skills | Where-Object { $_.Name -eq "disabled-skill" }) | Should -BeNullOrEmpty
        }
    }

    Context "Cross-platform skill inclusion" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "universal" }) }
        }

        It "includes cross-platform skills (no platform field)" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "universal" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 1
        }
    }

    # =======================================================================
    # DEDUPLICATION
    # =======================================================================
    Context "Deduplication" {
        BeforeAll {
            Mock Invoke-RestMethod {
                return @(
                    [PSCustomObject]@{ name = "lang"; relative_path = "skills/lang" },
                    [PSCustomObject]@{ name = "lang"; relative_path = "skills/lang" }
                )
            }
        }

        It "deduplicates when API returns the same skill name twice" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "lang" -Location "flat"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 1
        }
    }

    # =======================================================================
    # GRACEFUL ERROR HANDLING (NO THROW)
    # =======================================================================
    Context "Error handling — never throws" {
        BeforeAll {
            Mock Invoke-RestMethod { return @([PSCustomObject]@{ name = "non-existent-skill" }) }
        }

        It "skips gracefully when API-returned skill is not found locally" {
            $roomDir = New-TestRoom

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }
    }

    Context "Partial resolution" {
        BeforeAll {
            Mock Invoke-RestMethod {
                return @(
                    [PSCustomObject]@{ name = "lang" },
                    [PSCustomObject]@{ name = "missing-one" }
                )
            }
        }

        It "resolves found skills even when some are missing" {
            $roomDir = New-TestRoom
            New-TestSkill -Name "lang" -Location "flat"
            # "missing-one" does not exist locally

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 1
            $skills[0].Name | Should -Be "lang"
        }
    }

    # =======================================================================
    # BACKEND FETCH (Strategy 3)
    # =======================================================================
    Context "Backend fetch for skills not found locally" {
        BeforeAll {
            $script:mockCallCount = 0
            Mock Invoke-RestMethod {
                $script:mockCallCount++
                if ($script:mockCallCount -eq 1) {
                    # Brief search — returns "remote-skill"
                    return @([PSCustomObject]@{ name = "remote-skill" })
                } else {
                    # Per-ref backend fetch — returns skill with content
                    return @([PSCustomObject]@{
                        name = "remote-skill"
                        description = "A remote skill"
                        relative_path = "skills/roles/engineer/remote-skill"
                        content = "# Remote Skill`nDoes remote things."
                        tags = @("remote", "test")
                        trust_level = "community"
                    })
                }
            }
        }

        BeforeEach {
            $script:mockCallCount = 0
        }

        It "downloads and writes skill from backend API response" {
            $roomDir = New-TestRoom
            $env:OSTWIN_API_KEY = "test-key-123"

            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366" -ApiKey "test-key-123"

            $skills.Count | Should -Be 1
            $skills[0].Name | Should -Be "remote-skill"
            $skills[0].Tier | Should -Be "Backend"

            # Verify the file was written
            $writtenFile = $skills[0].Path
            Test-Path $writtenFile | Should -BeTrue
            $content = Get-Content $writtenFile -Raw
            $content | Should -Match "remote-skill"
            
            # Verify clean frontmatter
            $content | Should -Not -Match "tags:"
            $content | Should -Not -Match "trust_level:"
            $content | Should -Not -Match "description: `".*`""
            $content | Should -Match "description: A remote skill"
        }
    }

    # =======================================================================
    # BRIEF TRUNCATION
    # =======================================================================
    Context "Brief content handling" {
        BeforeAll {
            Mock Invoke-RestMethod { return @() }
        }

        It "handles long brief content without error" {
            $longBrief = "x" * 1000
            $roomDir = New-TestRoom -BriefContent $longBrief

            # Should not throw — brief is truncated to 500 chars internally
            $skills = & $script:resolveScript -RoleName "engineer" -RolePath $script:testRolePath `
                -SkillsBaseDir $script:baseDir -RoomDir $roomDir `
                -DashboardUrl "http://mocked:3366"

            $skills.Count | Should -Be 0
        }
    }
}
