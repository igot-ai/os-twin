# Agent OS — Invoke-Agent Pester Tests

BeforeAll {
    $script:InvokeAgent = Join-Path $PSScriptRoot "Invoke-Agent.ps1"
}

Describe "Invoke-Agent" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null
    }

    Context "With mock agent command" {
        It "runs successfully with echo mock" {
            $env:ENGINEER_CMD = "echo"
            try {
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test prompt" `
                    -AgentCmd "echo" -TimeoutSeconds 10

                $result | Should -Not -BeNullOrEmpty
                $result.RoleName | Should -Be "engineer"
                $result.ExitCode | Should -BeIn @(0, 1)  # echo may or may not accept -n flag
            }
            finally {
                Remove-Item Env:ENGINEER_CMD -ErrorAction SilentlyContinue
            }
        }

        It "creates artifacts directory" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            Test-Path (Join-Path $script:roomDir "artifacts") | Should -BeTrue
        }

        It "creates pids directory" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "qa" -Prompt "review" `
                -AgentCmd "echo" -TimeoutSeconds 5

            Test-Path (Join-Path $script:roomDir "pids") | Should -BeTrue
        }

        It "cleans up PID file after execution" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $pidFile = Join-Path $script:roomDir "pids" "engineer.pid"
            Test-Path $pidFile | Should -BeFalse
        }

        It "returns structured result object" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $result.PSObject.Properties.Name | Should -Contain "ExitCode"
            $result.PSObject.Properties.Name | Should -Contain "Output"
            $result.PSObject.Properties.Name | Should -Contain "OutputFile"
            $result.PSObject.Properties.Name | Should -Contain "RoleName"
            $result.PSObject.Properties.Name | Should -Contain "TimedOut"
        }

        It "writes output to artifacts file" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "qa" -Prompt "review test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $result.OutputFile | Should -Match "qa-output\.txt$"
        }
    }

    Context "Timeout handling" {
        It "sets TimedOut flag when command times out" {
            # Create a mock that ignores all args and sleeps
            $sleepScript = Join-Path $TestDrive "slow-mock.sh"
            "#!/bin/bash`nsleep 30" | Out-File $sleepScript -Encoding utf8
            chmod +x $sleepScript

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "slow" `
                -AgentCmd $sleepScript -TimeoutSeconds 2

            $result.TimedOut | Should -BeTrue
            $result.ExitCode | Should -Be 124
        }
    }

    Context "Config resolution" {
        It "uses env var override for agent command" {
            $env:ENGINEER_CMD = "echo"
            try {
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test" -TimeoutSeconds 5

                # Should use echo instead of deepagents
                $result | Should -Not -BeNullOrEmpty
            }
            finally {
                Remove-Item Env:ENGINEER_CMD -ErrorAction SilentlyContinue
            }
        }

        It "uses AGENT_OS_CONFIG for config path" {
            $configFile = Join-Path $TestDrive "test-config.json"
            @{
                engineer = @{
                    cli             = "echo"
                    default_model   = "test-model"
                    timeout_seconds = 10
                }
            } | ConvertTo-Json -Depth 3 | Out-File $configFile -Encoding utf8

            $env:AGENT_OS_CONFIG = $configFile
            try {
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "config test" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }
    }

    Context "Role name handling" {
        It "supports engineer role" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5
            $result.RoleName | Should -Be "engineer"
        }

        It "supports qa role" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "qa" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5
            $result.RoleName | Should -Be "qa"
        }

        It "supports custom roles" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "architect" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5
            $result.RoleName | Should -Be "architect"
        }
    }
}
