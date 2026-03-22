# Agent OS — Start-Engineer Prompt Compilation Tests
#
# Validates the exact structure of the compiled prompt for the engineer role.
# Ensures: no duplicate sections, correct ordering, no baked-in skills.

BeforeAll {
    $script:BuildPrompt = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Build-SystemPrompt.ps1"
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path ".." "..")).Path
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:engineerRolePath = Join-Path $script:agentsDir "roles" "engineer"
}

Describe "Engineer Prompt Compilation" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "wr-eng-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

        & $script:NewWarRoom -RoomId "room-eng-001" -TaskRef "TASK-E001" `
            -TaskDescription "Implement the user auth module with JWT tokens" `
            -WarRoomsDir $script:warRoomsDir `
            -DefinitionOfDone @("JWT auth working", "Unit tests pass") `
            -AcceptanceCriteria @("POST /login returns 200 with valid token")

        $script:roomDir = Join-Path $script:warRoomsDir "room-eng-001"
    }

    Context "Task prompt structure" {
        It "contains ROLE.md content at the top" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir -TaskRef "TASK-E001"

            # ROLE.md frontmatter is stripped, but content should be present
            $prompt | Should -Match "Your Responsibilities"
            $prompt | Should -Match "Phase 1"
        }

        It "contains capabilities from role.json" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Your Capabilities"
            $prompt | Should -Match "code-generation"
            $prompt | Should -Match "testing"
        }

        It "contains quality gates from role.json" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Quality Gates"
            $prompt | Should -Match "unit-tests"
            $prompt | Should -Match "lint-clean"
        }

        It "contains brief.md content (task assignment)" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Task Assignment"
            $prompt | Should -Match "user auth module"
            $prompt | Should -Match "JWT tokens"
        }

        It "contains goals from war-room config" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Definition of Done"
            $prompt | Should -Match "JWT auth working"
            $prompt | Should -Match "Acceptance Criteria"
            $prompt | Should -Match "POST /login returns 200"
        }

        It "contains task reference when provided" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir -TaskRef "TASK-E001"

            $prompt | Should -Match "TASK-E001"
        }

        It "includes extra context (workflow instructions)" {
            $instructions = "1. Implement the task described above`n2. Summarize your changes"
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir -ExtraContext $instructions

            $prompt | Should -Match "Additional Context"
            $prompt | Should -Match "Implement the task"
        }
    }

    Context "Epic prompt with TASKS.md" {
        BeforeEach {
            # Create TASKS.md in the war-room
            @"
# Tasks for EPIC-001

- [x] TASK-001 — Set up module structure
- [ ] TASK-002 — Implement core JWT logic
- [ ] TASK-003 — Write unit tests
"@ | Out-File (Join-Path $script:roomDir "TASKS.md") -Encoding utf8
        }

        It "includes TASKS.md content exactly once" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir -TaskRef "EPIC-001"

            # TASKS.md should appear via Build-SystemPrompt Section 5
            $prompt | Should -Match "Sub-Tasks"
            $prompt | Should -Match "TASK-001"
            $prompt | Should -Match "TASK-002"

            # Count occurrences — should be exactly 1
            $matches = [regex]::Matches($prompt, 'Sub-Tasks \(TASKS\.md\)')
            $matches.Count | Should -Be 1
        }

        It "does NOT duplicate TASKS.md in extra context" {
            # Simulate what the cleaned-up Start-Engineer.ps1 would pass
            $instructions = "You are continuing work on an EPIC — TASKS.md already exists (see Sub-Tasks section above)."
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir -ExtraContext $instructions

            # Instructions should reference TASKS.md but NOT contain a second copy
            $prompt | Should -Match "see Sub-Tasks section above"

            # The actual TASKS.md content should appear exactly once (from Section 5)
            $taskMatches = [regex]::Matches($prompt, 'TASK-002 — Implement core JWT logic')
            $taskMatches.Count | Should -Be 1
        }
    }

    Context "Fix cycle prompt (QA feedback)" {
        It "includes QA failure feedback" {
            & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-E001" -Body "Missing input validation on /login endpoint"

            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Previous QA Feedback"
            $prompt | Should -Match "Missing input validation"
        }

        It "includes fix instructions from manager" {
            & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-E001" -Body "Add validation for email and password fields"

            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Match "Fix Instructions"
            $prompt | Should -Match "validation for email"
        }
    }

    Context "No skills in prompt" {
        It "does NOT contain skill sections" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $prompt | Should -Not -Match "## Skills"
            $prompt | Should -Not -Match "### Skill:"
        }
    }

    Context "No duplicate sections" {
        BeforeEach {
            # Set up a full room with TASKS.md + QA feedback
            @"
- [x] TASK-001 — Setup
- [ ] TASK-002 — Implement
"@ | Out-File (Join-Path $script:roomDir "TASKS.md") -Encoding utf8

            & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-E001" -Body "Tests are failing"
        }

        It "brief.md (Task Assignment) appears exactly once" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $matches = [regex]::Matches($prompt, '## Task Assignment')
            $matches.Count | Should -Be 1
        }

        It "TASKS.md appears at most once" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $matches = [regex]::Matches($prompt, 'Sub-Tasks \(TASKS\.md\)')
            $matches.Count | Should -BeLessOrEqual 1
        }

        It "QA feedback appears at most once" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $matches = [regex]::Matches($prompt, 'Previous QA Feedback')
            $matches.Count | Should -BeLessOrEqual 1
        }
    }

    Context "Section ordering" {
        It "ROLE.md appears before Task Assignment" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $roleIdx = $prompt.IndexOf("Your Responsibilities")
            $briefIdx = $prompt.IndexOf("Task Assignment")

            $roleIdx | Should -BeLessThan $briefIdx
        }

        It "Capabilities appear before Task Assignment" {
            $prompt = & $script:BuildPrompt -RolePath $script:engineerRolePath `
                -RoomDir $script:roomDir

            $capIdx = $prompt.IndexOf("Your Capabilities")
            $briefIdx = $prompt.IndexOf("Task Assignment")

            $capIdx | Should -BeLessThan $briefIdx
        }
    }
}
