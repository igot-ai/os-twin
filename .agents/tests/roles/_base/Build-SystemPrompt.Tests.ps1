# Agent OS — Build-SystemPrompt Pester Tests

BeforeAll {
    $script:BuildPrompt = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Build-SystemPrompt.ps1"
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path ".." "..")).Path
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
}

Describe "Build-SystemPrompt" {
    Context "Role-based prompt" {
        It "builds prompt from JSON role definition" {
            $rolePath = Join-Path $TestDrive "role-bp-$(Get-Random)"
            New-Item -ItemType Directory -Path $rolePath -Force | Out-Null

            @{
                name         = "test-role"
                description  = "A test role for validation"
                capabilities = @("code-gen", "testing")
                prompt_file  = "ROLE.md"
                quality_gates = @("lint", "tests")
                skills       = @("python", "go")
            } | ConvertTo-Json -Depth 3 | Out-File (Join-Path $rolePath "role.json") -Encoding utf8

            "# Test Role`nYou are a test role agent." |
                Out-File (Join-Path $rolePath "ROLE.md") -Encoding utf8

            $prompt = & $script:BuildPrompt -RolePath $rolePath
            $prompt | Should -Match "Test Role"
            $prompt | Should -Match "test role agent"
        }

        It "includes capabilities section" {
            $rolePath = Join-Path $TestDrive "role-cap-$(Get-Random)"
            New-Item -ItemType Directory -Path $rolePath -Force | Out-Null

            @{
                name         = "cap-role"
                capabilities = @("code-gen", "file-editing", "shell-execution")
            } | ConvertTo-Json -Depth 3 | Out-File (Join-Path $rolePath "role.json") -Encoding utf8

            $prompt = & $script:BuildPrompt -RolePath $rolePath
            $prompt | Should -Match "Capabilities"
            $prompt | Should -Match "code-gen"
            $prompt | Should -Match "shell-execution"
        }

        It "includes quality gates section" {
            $rolePath = Join-Path $TestDrive "role-qg-$(Get-Random)"
            New-Item -ItemType Directory -Path $rolePath -Force | Out-Null

            @{
                name          = "qg-role"
                quality_gates = @("unit-tests", "lint-clean", "security-scan")
            } | ConvertTo-Json -Depth 3 | Out-File (Join-Path $rolePath "role.json") -Encoding utf8

            $prompt = & $script:BuildPrompt -RolePath $rolePath
            $prompt | Should -Match "Quality Gates"
            $prompt | Should -Match "unit-tests"
            $prompt | Should -Match "security-scan"
        }

        It "does NOT concatenate skills into the prompt (skills via AGENT_OS_SKILLS_DIR)" {
            $rolePath = Join-Path $TestDrive "role-sk-$(Get-Random)"
            New-Item -ItemType Directory -Path $rolePath -Force | Out-Null

            # Create global skill — should NOT appear in the prompt
            $skillsDir = Join-Path $TestDrive "skills"
            New-Item -ItemType Directory -Path (Join-Path $skillsDir "global" "test-skill") -Force | Out-Null
            "Test Skill content" | Out-File (Join-Path $skillsDir "global" "test-skill" "SKILL.md")

            @{
                name   = "sk-role"
            } | ConvertTo-Json -Depth 3 | Out-File (Join-Path $rolePath "role.json") -Encoding utf8

            $prompt = & $script:BuildPrompt -RolePath $rolePath
            # Skills should NOT be in the prompt — they are loaded via AGENT_OS_SKILLS_DIR by Invoke-Agent.ps1
            $prompt | Should -Not -Match "## Skills"
            $prompt | Should -Not -Match "### Skill:"
            $prompt | Should -Not -Match "Test Skill content"
        }
    }

    Context "War-room context injection" {
        BeforeEach {
            $script:warRoomsDir = Join-Path $TestDrive "wr-bp-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

            & $script:NewWarRoom -RoomId "room-bp-001" -TaskRef "TASK-BP" `
                -TaskDescription "Build the auth module" `
                -WarRoomsDir $script:warRoomsDir `
                -DefinitionOfDone @("JWT working", "Tests pass") `
                -AcceptanceCriteria @("POST /login returns 200")

            $script:roomDir = Join-Path $script:warRoomsDir "room-bp-001"

            $script:rolePath = Join-Path $TestDrive "role-ctx-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:rolePath -Force | Out-Null
            @{ name = "ctx-role" } | ConvertTo-Json | Out-File (Join-Path $script:rolePath "role.json")
        }

        It "includes task brief from war-room" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Build the auth module"
        }

        It "includes goals from config.json" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Definition of Done"
            $prompt | Should -Match "JWT working"
            $prompt | Should -Match "Tests pass"
        }

        It "includes acceptance criteria" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Acceptance Criteria"
            $prompt | Should -Match "POST /login returns 200"
        }

        It "includes quality requirements" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Quality Requirements"
            $prompt | Should -Match "80"
        }

        It "includes QA feedback when available" {
            & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-BP" -Body "Missing input validation"

            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Missing input validation"
        }

        It "includes TASKS.md for epics" {
            "- [x] TASK-001 — Design`n- [ ] TASK-002 — Implement" |
                Out-File (Join-Path $script:roomDir "TASKS.md") -Encoding utf8

            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Sub-Tasks"
            $prompt | Should -Match "TASK-001"
        }
    }

    Context "Override parameters" {
        BeforeEach {
            $script:rolePath = Join-Path $TestDrive "role-ov-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:rolePath -Force | Out-Null
            @{ name = "ov-role" } | ConvertTo-Json | Out-File (Join-Path $script:rolePath "role.json")
        }

        It "includes task reference" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -TaskRef "EPIC-042"
            $prompt | Should -Match "EPIC-042"
        }

        It "includes task body" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath `
                -TaskBody "Implement the dashboard widget"
            $prompt | Should -Match "Implement the dashboard widget"
        }

        It "includes extra context" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath `
                -ExtraContext "The project uses React 19 with TypeScript."
            $prompt | Should -Match "React 19"
            $prompt | Should -Match "Additional Context"
        }
    }

    Context "Built-in roles" {
        It "builds prompt for engineer role" {
            $engPath = Join-Path $script:agentsDir "roles" "engineer"
            if (Test-Path $engPath) {
                $prompt = & $script:BuildPrompt -RolePath $engPath
                $prompt.Length | Should -BeGreaterThan 0
            }
        }

        It "builds prompt for qa role" {
            $qaPath = Join-Path $script:agentsDir "roles" "qa"
            if (Test-Path $qaPath) {
                $prompt = & $script:BuildPrompt -RolePath $qaPath
                $prompt.Length | Should -BeGreaterThan 0
            }
        }

        It "builds prompt for architect role" {
            $archPath = Join-Path $script:agentsDir "roles" "architect"
            if (Test-Path $archPath) {
                $prompt = & $script:BuildPrompt -RolePath $archPath
                $prompt | Should -Match "architect"
            }
        }
    }

    Context "Error handling" {
        It "fails when no role specified" {
            $output = & $script:BuildPrompt 2>&1
            $output | Should -Match "must be specified"
        }
    }
}
