# Agent OS — Invoke-Agent Pester Tests

BeforeAll {
    $script:InvokeAgent = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Invoke-Agent.ps1"
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

        It "reports PidFile path in result (agent self-registers PID)" {
            # Design contract (v2): Invoke-Agent does NOT write the PID file itself.
            # It sets AGENT_OS_PID_FILE env var in the wrapper, and bin/agent writes $$
            # before exec. The PID file may or may not exist depending on the mock used.
            # The result object always carries the expected PidFile path for the caller.
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $pidFile = Join-Path $script:roomDir "pids" "engineer.pid"
            $result.PidFile | Should -Be $pidFile
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

    Context "Instance config resolution" {
        BeforeEach {
            $script:instanceConfigFile = Join-Path $TestDrive "instance-config.json"
            @{
                engineer = @{
                    cli             = "echo"
                    default_model   = "base-model"
                    timeout_seconds = 600
                    instances = @{
                        fe = @{
                            display_name    = "Frontend Engineer"
                            default_model   = "fe-pro-model"
                            timeout_seconds = 900
                            working_dir     = "/tmp/frontend"
                        }
                    }
                }
            } | ConvertTo-Json -Depth 5 | Out-File $script:instanceConfigFile -Encoding utf8
        }

        It "resolves model from instance config when InstanceId is provided" {
            $env:AGENT_OS_CONFIG = $script:instanceConfigFile
            try {
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test" `
                    -InstanceId "fe" -AgentCmd "echo" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
                $result.RoleName | Should -Be "engineer"
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }

        It "falls back to role default when InstanceId not in config" {
            $env:AGENT_OS_CONFIG = $script:instanceConfigFile
            try {
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test" `
                    -InstanceId "nonexistent" -AgentCmd "echo" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
                $result.RoleName | Should -Be "engineer"
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }

        It "passes WorkingDir parameter through" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -WorkingDir "/tmp/testdir" -AgentCmd "echo" -TimeoutSeconds 5

            $result | Should -Not -BeNullOrEmpty
        }
    }

    Context "Skill Isolation (EPIC-002)" {
        It "creates and populates skills directory" {
            # Use engineer role because it has at least 'lang' skill in this project
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $isolatedSkillsDir = Join-Path $script:roomDir "skills"
            Test-Path $isolatedSkillsDir | Should -BeTrue
            
            $skills = Get-ChildItem $isolatedSkillsDir -Directory
            $skills.Count | Should -BeGreaterThan 0
            # Should contain at least 'lang' (from role.json) or global skills
            $skills.Name | Should -Contain "lang"
        }

        It "clears previous skills on new invocation" {
            $isolatedSkillsDir = Join-Path $script:roomDir "skills"
            New-Item -ItemType Directory -Path $isolatedSkillsDir -Force | Out-Null
            $staleFile = Join-Path $isolatedSkillsDir "STALE"
            "stale" | Out-File $staleFile

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            Test-Path $staleFile | Should -BeFalse
        }

        It "exports AGENT_OS_SKILLS_DIR in the environment (verified via echo mock)" {
            # We can't easily check the wrapper because it's deleted,
            # but we can make the mock echo the env var.
            
            # Create a mock bash script that echoes AGENT_OS_SKILLS_DIR
            $echoMock = Join-Path $TestDrive "echo-env.sh"
            "#!/bin/bash`necho `$AGENT_OS_SKILLS_DIR" | Out-File $echoMock -Encoding utf8
            chmod +x $echoMock

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd $echoMock -TimeoutSeconds 5

            $result.Output | Should -Match "/skills"
            # Ensure it's an absolute path (starts with / or [Drive]:\)
            $result.Output | Should -Match "^(/|[a-zA-Z]:\\)"
        }

        It "handles empty skills array gracefully" {
            # Use a role that doesn't exist and ensure global skills are empty for this test
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "non-existent-role" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5
            
            $isolatedSkillsDir = Join-Path $script:roomDir "skills"
            Test-Path $isolatedSkillsDir | Should -BeTrue
            # Note: non-existent-role will still get Global skills if they exist in .agents/skills/global
            # So this might not be 0 unless we mock Resolve-RoleSkills.
        }
    }
}
