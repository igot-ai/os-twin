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

        # Create a config with mock that ignores the prompt and prints MOCK_OUT
        $script:mockAgentPath = Join-Path $TestDrive "mock-arch.sh"
        "echo `"`$MOCK_OUT`"" | Out-File $script:mockAgentPath -Encoding ascii
        $script:configFile = Join-Path $TestDrive "config-arch.json"
        @{
            engineer = @{
                cli              = "bash ""$script:mockAgentPath"""
                default_model    = "test-model"
                timeout_seconds  = 10
            }
            qa = @{
                cli             = "bash ""$script:mockAgentPath"""
                default_model   = "test-model"
                timeout_seconds = 10
            }
            architect = @{
                cli             = "bash ""$script:mockAgentPath"""
                default_model   = "test-model"
                timeout_seconds = 10
            }
            channel = @{
                format                 = "jsonl"
                max_message_size_bytes = 65536
            }
        } | ConvertTo-Json -Depth 3 | Out-File $script:configFile -Encoding utf8
        $env:AGENT_OS_CONFIG = $script:configFile
        $env:ARCHITECT_CMD = "bash ""$script:mockAgentPath"""
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

    Context "Tool Noise Stripping" {
        It "removes MCP and tool call noise from output" {
            $env:MOCK_OUT = "Loading MCP`n🔧 Calling tool: read_file`nSystem.Management.Automation noise`n`nHere is the architecture:`nVERDICT: PASS"
            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5
            
            $passMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "pass" -Last 1 -AsObject
            $body = $passMsgs[0].body
            $body | Should -Not -Match "Loading MCP"
            $body | Should -Not -Match "🔧 Calling tool"
            $body | Should -Match "Here is the architecture:"
        }
    }

    Context "Verdict Fallback" {
        It "injects VERDICT: PASS and posts pass signal if no verdict is present" {
            $env:MOCK_OUT = 'RECOMMENDATION: REDESIGN'
            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5
            
            $passMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "pass" -Last 1 -AsObject
            $passMsgs.Count | Should -Be 1
            $passMsgs[0].body | Should -Match "RECOMMENDATION: REDESIGN"
            $passMsgs[0].body | Should -Match "VERDICT: PASS"

            # Ensure 'done' is not double-posted
            $doneMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "done" -Last 1 -AsObject
            if ($doneMsgs) { $doneMsgs.Count | Should -Be 0 }
        }

        It "does not override explicit VERDICT: REJECT" {
            $env:MOCK_OUT = "RECOMMENDATION: REDESIGN`n`nVERDICT: REJECT"
            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5
            
            $failMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "fail" -Last 1 -AsObject
            $failMsgs.Count | Should -Be 1
            $failMsgs[0].body | Should -Match "VERDICT: REJECT"
            $failMsgs[0].body | Should -Not -Match "VERDICT: PASS"
        }

        It "posts error instead of PASS when the architect subprocess exits non-zero without a verdict" {
            $failingAgentPath = Join-Path $TestDrive "mock-arch-fail.sh"
            @"
#!/bin/bash
echo 'runtime failure'
exit 1
"@ | Out-File $failingAgentPath -Encoding ascii -NoNewline
            $env:ARCHITECT_CMD = "bash ""$failingAgentPath"""

            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5

            $errorMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "error" -Last 1 -AsObject
            $passMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "pass" -Last 1 -AsObject

            $errorMsgs.Count | Should -Be 1
            $errorMsgs[0].body | Should -Match "Architect exited with code 1"
            if ($passMsgs) { $passMsgs.Count | Should -Be 0 }
        }

        It "disables MCP for PLAN-REVIEW so architect signaling stays in-process" {
            "PLAN-REVIEW" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline

            $slowAgentPath = Join-Path $TestDrive "mock-arch-slow.sh"
            @"
#!/bin/bash
sleep 1
echo 'VERDICT: PASS'
"@ | Out-File $slowAgentPath -Encoding ascii -NoNewline
            $env:ARCHITECT_CMD = "bash ""$slowAgentPath"""

            $job = Start-Job -ScriptBlock {
                param($startArchitect, $roomDir)
                & $startArchitect -RoomDir $roomDir -TimeoutSeconds 10
            } -ArgumentList $script:StartArchitect, $script:roomDir

            try {
                $wrapperFile = Join-Path $script:roomDir "artifacts" "run-agent.sh"
                $deadline = (Get-Date).AddSeconds(5)
                while (-not (Test-Path $wrapperFile) -and (Get-Date) -lt $deadline) {
                    Start-Sleep -Milliseconds 50
                }

                Test-Path $wrapperFile | Should -BeTrue
                $wrapperContent = Get-Content $wrapperFile -Raw
                $wrapperContent | Should -Match -- "--no-mcp"
                $wrapperContent | Should -Not -Match -- "--mcp-config"
            }
            finally {
                $job | Wait-Job -Timeout 15 | Out-Null
                $job | Remove-Job -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Context "Signal Broadcasting" {
        It "posts a 'pass' signal when output explicitly contains VERDICT: PASS" {
            $env:MOCK_OUT = "Review completed.`n`nVERDICT: PASS"
            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5
            
            $passMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "pass" -Last 1 -AsObject
            $passMsgs.Count | Should -Be 1
            $passMsgs[0].body | Should -Match "VERDICT: PASS"
        }

        It "posts a 'fail' signal when output explicitly contains VERDICT: REJECT" {
            $env:MOCK_OUT = "Review rejected.`n`nVERDICT: REJECT"
            & $script:StartArchitect -RoomDir $script:roomDir -TimeoutSeconds 5
            
            $failMsgs = & $script:ReadMessages -RoomDir $script:roomDir -FilterType "fail" -Last 1 -AsObject
            $failMsgs.Count | Should -Be 1
            $failMsgs[0].body | Should -Match "VERDICT: REJECT"
        }
    }
}
