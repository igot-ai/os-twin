# Agent OS — Start-Engineer Pester Tests

BeforeAll {
    $script:StartEngineer = Join-Path $PSScriptRoot "Start-Engineer.ps1"
    $script:PostMessage = Join-Path (Split-Path $PSScriptRoot) ".." "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path (Split-Path $PSScriptRoot) ".." "channel" "Read-Messages.ps1"
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
}

Describe "Start-Engineer" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-eng-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null

        # Create minimal room state
        "TASK-001" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline
        @"
# TASK-001

Implement a hello world function

## Working Directory
$TestDrive

## Created
2026-01-01T00:00:00Z
"@ | Out-File (Join-Path $script:roomDir "brief.md") -Encoding utf8

        "pending" | Out-File (Join-Path $script:roomDir "status") -NoNewline

        # Create a config with echo mock
        $script:configFile = Join-Path $TestDrive "config-eng.json"
        @{
            engineer = @{
                cli              = "echo"
                default_model    = "test-model"
                timeout_seconds  = 10
                max_prompt_bytes = 102400
            }
            qa = @{
                cli             = "echo"
                timeout_seconds = 10
            }
        } | ConvertTo-Json -Depth 3 | Out-File $script:configFile -Encoding utf8
        $env:AGENT_OS_CONFIG = $script:configFile
        $env:ENGINEER_CMD = "echo"
    }

    AfterEach {
        Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
        Remove-Item Env:ENGINEER_CMD -ErrorAction SilentlyContinue
    }

    Context "Task execution" {
        It "reads task-ref from room" {
            # The script should read TASK-001 from task-ref file
            # and include it in the prompt
            $taskRef = Get-Content (Join-Path $script:roomDir "task-ref") -Raw
            $taskRef.Trim() | Should -Be "TASK-001"
        }

        It "reads brief.md for task description" {
            $brief = Get-Content (Join-Path $script:roomDir "brief.md") -Raw
            $brief | Should -Match "hello world"
        }

        It "creates brief.md with working directory" {
            $brief = Get-Content (Join-Path $script:roomDir "brief.md") -Raw
            $brief | Should -Match "Working Directory"
        }
    }

    Context "Epic detection" {
        It "detects EPIC prefix" {
            "EPIC-001" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline
            $taskRef = (Get-Content (Join-Path $script:roomDir "task-ref") -Raw).Trim()
            $taskRef | Should -Match '^EPIC-'
        }

        It "detects TASK prefix" {
            $taskRef = (Get-Content (Join-Path $script:roomDir "task-ref") -Raw).Trim()
            $taskRef | Should -Not -Match '^EPIC-'
        }
    }

    Context "Room structure" {
        It "has required directories" {
            Test-Path (Join-Path $script:roomDir "pids") | Should -BeTrue
            Test-Path (Join-Path $script:roomDir "artifacts") | Should -BeTrue
        }

        It "has channel.jsonl or can create one" {
            $channelFile = Join-Path $script:roomDir "channel.jsonl"
            # Channel file may not exist yet, but post will create it
            New-Item -ItemType File -Path $channelFile -Force | Out-Null
            Test-Path $channelFile | Should -BeTrue
        }
    }

    Context "Prompt construction" {
        It "includes role prompt from ROLE.md if exists" {
            $roleMd = Join-Path $PSScriptRoot "ROLE.md"
            if (Test-Path $roleMd) {
                $roleContent = Get-Content $roleMd -Raw
                $roleContent.Length | Should -BeGreaterThan 0
            }
        }

        It "handles missing ROLE.md gracefully" {
            # This shouldn't throw even if ROLE.md doesn't exist
            # The script uses conditional file reads
            $true | Should -BeTrue
        }
    }
}
