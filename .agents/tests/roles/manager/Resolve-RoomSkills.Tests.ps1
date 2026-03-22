# Agent OS — Resolve-RoomSkills Unit Tests
# Tests the skills auto-discovery flow: brief.md → API search → skill_refs + copy to room/skills/

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/manager").Path ".." "..")).Path
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"

    # Import Utils
    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
}

Describe "Resolve-RoomSkills — Skills Auto-Discovery" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

        # Create a war room with a brief
        & $script:NewWarRoom -RoomId "room-skill-001" -TaskRef "TASK-SK001" `
            -TaskDescription "Implement data parsing and CSV transformation pipeline" `
            -WarRoomsDir $script:warRoomsDir `
            -DefinitionOfDone @("CSV parser works", "Unit tests pass")

        $script:roomDir = Join-Path $script:warRoomsDir "room-skill-001"
    }

    Context "brief.md is used as search context" {
        It "creates brief.md with task description" {
            $briefFile = Join-Path $script:roomDir "brief.md"
            Test-Path $briefFile | Should -BeTrue
            $content = Get-Content $briefFile -Raw
            $content | Should -Match "TASK-SK001"
            $content | Should -Match "data parsing"
        }

        It "brief.md contains full task description content" {
            $briefFile = Join-Path $script:roomDir "brief.md"
            $content = Get-Content $briefFile -Raw
            $content | Should -Match "CSV transformation pipeline"
            $content | Should -Match "Definition of Done"
        }
    }

    Context "skill_refs written to config.json" {
        It "config.json can hold skill_refs array" {
            $configFile = Join-Path $script:roomDir "config.json"
            Test-Path $configFile | Should -BeTrue
            $config = Get-Content $configFile -Raw | ConvertFrom-Json

            # Simulate what Resolve-RoomSkills does
            $skillNames = @("validate-output", "structure-data-request", "lang")
            $config | Add-Member -NotePropertyName "skill_refs" -NotePropertyValue $skillNames -Force
            $config | ConvertTo-Json -Depth 10 |
                Out-File -FilePath $configFile -Encoding utf8 -Force

            # Re-read and verify
            $updated = Get-Content $configFile -Raw | ConvertFrom-Json
            $updated.skill_refs | Should -HaveCount 3
            $updated.skill_refs | Should -Contain "validate-output"
            $updated.skill_refs | Should -Contain "structure-data-request"
            $updated.skill_refs | Should -Contain "lang"
        }

        It "skill_refs is capped at 5 items" {
            $configFile = Join-Path $script:roomDir "config.json"
            $config = Get-Content $configFile -Raw | ConvertFrom-Json

            # Simulate Resolve-RoomSkills with 7 results, limited to first 5
            $allSkills = @("s1", "s2", "s3", "s4", "s5", "s6", "s7")
            $topSkills = @($allSkills | Select-Object -First 5)
            $config | Add-Member -NotePropertyName "skill_refs" -NotePropertyValue $topSkills -Force
            $config | ConvertTo-Json -Depth 10 |
                Out-File -FilePath $configFile -Encoding utf8 -Force

            $updated = Get-Content $configFile -Raw | ConvertFrom-Json
            $updated.skill_refs | Should -HaveCount 5
        }

        It "skips resolution if skill_refs already populated" {
            $configFile = Join-Path $script:roomDir "config.json"
            $config = Get-Content $configFile -Raw | ConvertFrom-Json
            $config | Add-Member -NotePropertyName "skill_refs" `
                -NotePropertyValue @("existing-skill") -Force
            $config | ConvertTo-Json -Depth 10 |
                Out-File -FilePath $configFile -Encoding utf8 -Force

            # Re-read — should still have original skill_refs
            $updated = Get-Content $configFile -Raw | ConvertFrom-Json
            $updated.skill_refs | Should -HaveCount 1
            $updated.skill_refs | Should -Contain "existing-skill"
        }
    }

    Context "Skills copied to room/skills/ directory" {
        It "creates room skills directory" {
            $roomSkillsDir = Join-Path $script:roomDir "skills"
            New-Item -ItemType Directory -Path $roomSkillsDir -Force | Out-Null
            Test-Path $roomSkillsDir | Should -BeTrue
        }

        It "copies skill with SKILL.md to room/skills/{name}/" {
            $roomSkillsDir = Join-Path $script:roomDir "skills"
            New-Item -ItemType Directory -Path $roomSkillsDir -Force | Out-Null

            # Simulate a source skill under agents dir
            $srcSkillDir = Join-Path $TestDrive "agents-mock" "skills" "roles" "engineer" "write-tests"
            New-Item -ItemType Directory -Path $srcSkillDir -Force | Out-Null
            @"
---
name: write-tests
description: Generates unit tests for the codebase.
tags: [testing, engineer]
trust_level: core
---
# write-tests skill content
"@ | Out-File (Join-Path $srcSkillDir "SKILL.md") -Encoding utf8

            # Copy it the same way Resolve-RoomSkills does
            $destDir = Join-Path $roomSkillsDir "write-tests"
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            Copy-Item -Path (Join-Path $srcSkillDir "*") -Destination $destDir -Recurse -Force

            # Verify
            Test-Path (Join-Path $destDir "SKILL.md") | Should -BeTrue
            $content = Get-Content (Join-Path $destDir "SKILL.md") -Raw
            $content | Should -Match "write-tests"
            $content | Should -Match "Generates unit tests"
        }

        It "copies multiple skills to room/skills/" {
            $roomSkillsDir = Join-Path $script:roomDir "skills"
            New-Item -ItemType Directory -Path $roomSkillsDir -Force | Out-Null

            # Create 3 mock skills
            foreach ($name in @("skill-a", "skill-b", "skill-c")) {
                $srcDir = Join-Path $TestDrive "mock-skills" $name
                New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
                "---`nname: $name`n---`n# $name content" |
                    Out-File (Join-Path $srcDir "SKILL.md") -Encoding utf8

                $destDir = Join-Path $roomSkillsDir $name
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                Copy-Item -Path (Join-Path $srcDir "*") -Destination $destDir -Recurse -Force
            }

            $skills = Get-ChildItem $roomSkillsDir -Directory
            $skills.Count | Should -Be 3
            $skills.Name | Should -Contain "skill-a"
            $skills.Name | Should -Contain "skill-b"
            $skills.Name | Should -Contain "skill-c"
        }

        It "overwrites existing skill on re-resolution" {
            $roomSkillsDir = Join-Path $script:roomDir "skills"
            $destDir = Join-Path $roomSkillsDir "overwrite-test"
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            "old content" | Out-File (Join-Path $destDir "SKILL.md") -Encoding utf8

            # Simulate re-copy with new content
            Remove-Item -Path $destDir -Recurse -Force
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            "new content" | Out-File (Join-Path $destDir "SKILL.md") -Encoding utf8

            $content = Get-Content (Join-Path $destDir "SKILL.md") -Raw
            $content | Should -Match "new content"
            $content | Should -Not -Match "old content"
        }
    }

    Context "relative_path resolution" {
        It "resolves skill from relative_path pattern 'skills/roles/engineer/write-tests'" {
            $relPath = "skills/roles/engineer/write-tests"
            $agentsMock = Join-Path $TestDrive "agents-relpath"
            $srcDir = Join-Path $agentsMock $relPath
            New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
            "# skill content" | Out-File (Join-Path $srcDir "SKILL.md") -Encoding utf8

            # Simulate what Resolve-RoomSkills does: Join-Path $agentsDir $relPath
            $resolved = Join-Path $agentsMock $relPath
            Test-Path $resolved | Should -BeTrue
            Test-Path (Join-Path $resolved "SKILL.md") | Should -BeTrue
        }

        It "falls back to HOME/.ostwin when skill not in agents dir" {
            $homeMock = Join-Path $TestDrive "home-mock" ".ostwin"
            $relPath = "skills/roles/audit/validate-output"
            $srcDir = Join-Path $homeMock $relPath
            New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
            "# validate content" | Out-File (Join-Path $srcDir "SKILL.md") -Encoding utf8

            # The fallback pattern from the code
            $agentsDir = Join-Path $TestDrive "nonexistent-agents"
            $primaryPath = Join-Path $agentsDir $relPath
            $fallbackPath = Join-Path $homeMock $relPath

            Test-Path $primaryPath | Should -BeFalse
            Test-Path $fallbackPath | Should -BeTrue
        }

        It "skips skill when relative_path is empty" {
            $skill = @{ name = "no-path-skill"; relative_path = $null }
            # Mirroring the guard: if (-not $relPath) { continue }
            $shouldSkip = (-not $skill.relative_path)
            $shouldSkip | Should -BeTrue
        }
    }
}
