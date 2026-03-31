# Agent OS — Start-Architect Pester Tests

BeforeAll {
    $script:StartArchitect = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/architect").Path "Start-Architect.ps1"
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/architect").Path ".." "..")).Path
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
}

Describe "Start-Architect" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-arch-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null

        # Create minimal room state
        "EPIC-001" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline
        @"
# EPIC-001

Implement user authentication

## Working Directory
$TestDrive

## Created
2026-01-01T00:00:00Z
"@ | Out-File (Join-Path $script:roomDir "brief.md") -Encoding utf8

        "architect-review" | Out-File (Join-Path $script:roomDir "status") -NoNewline
        New-Item -ItemType File -Path (Join-Path $script:roomDir "channel.jsonl") -Force | Out-Null

        # Create a config with echo mock
        $script:configFile = Join-Path $TestDrive "config-arch.json"
        @{
            engineer = @{
                cli              = "echo"
                default_model    = "test-model"
                timeout_seconds  = 10
            }
            qa = @{
                cli             = "echo"
                default_model   = "test-model"
                timeout_seconds = 10
            }
            architect = @{
                cli             = "echo"
                default_model   = "test-model"
                timeout_seconds = 10
            }
            channel = @{
                format                 = "jsonl"
                max_message_size_bytes = 65536
            }
        } | ConvertTo-Json -Depth 3 | Out-File $script:configFile -Encoding utf8
        $env:AGENT_OS_CONFIG = $script:configFile
        $env:ARCHITECT_CMD = "echo"
    }

    AfterEach {
        Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
        Remove-Item Env:ARCHITECT_CMD -ErrorAction SilentlyContinue
    }

    Context "Room state reading" {
        It "reads task-ref from room" {
            $taskRef = (Get-Content (Join-Path $script:roomDir "task-ref") -Raw).Trim()
            $taskRef | Should -Be "EPIC-001"
        }

        It "reads brief.md for original assignment" {
            $brief = Get-Content (Join-Path $script:roomDir "brief.md") -Raw
            $brief | Should -Match "user authentication"
        }
    }



    Context "QA feedback reading" {
        It "reads escalate messages when present" {
            & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                                  -Type "escalate" -Ref "EPIC-001" -Body "This is a design problem"

            $msgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "escalate" -Last 1 -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "design problem"
        }

        It "falls back to fail messages when no escalate" {
            & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                                  -Type "fail" -Ref "EPIC-001" -Body "Tests failing"

            $escalateMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "escalate" -Last 1 -AsObject
            if (-not $escalateMsgs -or $escalateMsgs.Count -eq 0) {
                $failMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "fail" -Last 1 -AsObject
                $failMsgs.Count | Should -Be 1
                $failMsgs[0].body | Should -Match "Tests failing"
            }
        }
    }

    Context "Design review messages" {
        It "reads manager's design-review request" {
            & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "architect" `
                                  -Type "design-review" -Ref "EPIC-001" -Body "Please review this design issue"

            $msgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "design-review" -Last 1 -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "design issue"
        }
    }
}
