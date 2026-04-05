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

    Context "Bash wrapper path compatibility" {
        It "keeps MCP enabled for architect by emitting --mcp-config instead of --no-mcp" {
            $slowAgent = Join-Path $TestDrive "slow-mcp-arch-agent-$(Get-Random).sh"
            @"
#!/bin/bash
sleep 1
echo "done"
"@ | Out-File $slowAgent -Encoding utf8 -NoNewline
            $bashSlowAgent = ($slowAgent -replace '\\', '/')
            if ($bashSlowAgent -match '^([A-Za-z]):/(.+)$') {
                $bashSlowAgent = "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
            & bash -lc "chmod +x '$bashSlowAgent'"

            $job = Start-Job -ScriptBlock {
                param($invokeAgent, $roomDir, $agentCmd)
                & $invokeAgent -RoomDir $roomDir -RoleName "architect" `
                    -Prompt "architect mcp config test" -AgentCmd $agentCmd -TimeoutSeconds 10
            } -ArgumentList $script:InvokeAgent, $script:roomDir, $bashSlowAgent

            try {
                $wrapperFile = Join-Path $script:roomDir "artifacts" "run-agent.sh"
                $deadline = (Get-Date).AddSeconds(5)
                while (-not (Test-Path $wrapperFile) -and (Get-Date) -lt $deadline) {
                    Start-Sleep -Milliseconds 50
                }

                Test-Path $wrapperFile | Should -BeTrue

                $wrapperContent = Get-Content $wrapperFile -Raw
                $wrapperContent | Should -Match -- "--mcp-config"
                $wrapperContent | Should -Not -Match -- "--no-mcp"
            }
            finally {
                $job | Wait-Job -Timeout 15 | Out-Null
                $job | Remove-Job -Force -ErrorAction SilentlyContinue
            }
        }

        It "honors explicit --no-mcp in ExtraArgs by suppressing --mcp-config" {
            $slowAgent = Join-Path $TestDrive "slow-explicit-no-mcp-agent-$(Get-Random).sh"
            @"
#!/bin/bash
sleep 1
echo "done"
"@ | Out-File $slowAgent -Encoding utf8 -NoNewline
            $bashSlowAgent = ($slowAgent -replace '\\', '/')
            if ($bashSlowAgent -match '^([A-Za-z]):/(.+)$') {
                $bashSlowAgent = "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
            & bash -lc "chmod +x '$bashSlowAgent'"

            $job = Start-Job -ScriptBlock {
                param($invokeAgent, $roomDir, $agentCmd)
                & $invokeAgent -RoomDir $roomDir -RoleName "architect" `
                    -Prompt "architect explicit no mcp test" -AgentCmd $agentCmd `
                    -ExtraArgs @("--no-mcp") -TimeoutSeconds 10
            } -ArgumentList $script:InvokeAgent, $script:roomDir, $bashSlowAgent

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

        It "materializes a local-only MCP config for built-in war-room servers" {
            $slowAgent = Join-Path $TestDrive "slow-local-mcp-agent-$(Get-Random).sh"
            @"
#!/bin/bash
sleep 1
echo "done"
"@ | Out-File $slowAgent -Encoding utf8 -NoNewline
            $bashSlowAgent = ($slowAgent -replace '\\', '/')
            if ($bashSlowAgent -match '^([A-Za-z]):/(.+)$') {
                $bashSlowAgent = "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
            & bash -lc "chmod +x '$bashSlowAgent'"

            $job = Start-Job -ScriptBlock {
                param($invokeAgent, $roomDir, $agentCmd)
                & $invokeAgent -RoomDir $roomDir -RoleName "architect" `
                    -Prompt "architect local mcp config test" -AgentCmd $agentCmd -TimeoutSeconds 10
            } -ArgumentList $script:InvokeAgent, $script:roomDir, $bashSlowAgent

            try {
                $resolvedConfigFile = Join-Path $script:roomDir "artifacts" "mcp-config-resolved.json"
                $deadline = (Get-Date).AddSeconds(5)
                while (-not (Test-Path $resolvedConfigFile) -and (Get-Date) -lt $deadline) {
                    Start-Sleep -Milliseconds 50
                }

                Test-Path $resolvedConfigFile | Should -BeTrue

                $resolvedConfig = Get-Content $resolvedConfigFile -Raw | ConvertFrom-Json
                $serverNames = @($resolvedConfig.mcpServers.PSObject.Properties.Name)
                $serverNames | Should -Contain "channel"
                $serverNames | Should -Contain "warroom"
                $serverNames | Should -Contain "memory"
                $serverNames | Should -Not -Contain "stitch"
                $serverNames | Should -Not -Contain "github"

                foreach ($serverName in $serverNames) {
                    $server = $resolvedConfig.mcpServers.$serverName
                    $server.command | Should -Match "^/"
                    @($server.args)[0] | Should -Match "^/"
                }
            }
            finally {
                $job | Wait-Job -Timeout 15 | Out-Null
                $job | Remove-Job -Force -ErrorAction SilentlyContinue
            }
        }

        It "executes the generated wrapper successfully from a Windows PowerShell invocation" {
            $echoAgent = Join-Path $TestDrive "echo-wrapper-agent-$(Get-Random).sh"
            @"
#!/bin/bash
echo "done"
"@ | Out-File $echoAgent -Encoding utf8 -NoNewline
            $bashEchoAgent = ($echoAgent -replace '\\', '/')
            if ($bashEchoAgent -match '^([A-Za-z]):/(.+)$') {
                $bashEchoAgent = "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
            & bash -lc "chmod +x '$bashEchoAgent'"

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "wrapper exec test" `
                -AgentCmd $bashEchoAgent -TimeoutSeconds 10

            $result.ExitCode | Should -Be 0
            $result.Output | Should -Match "(?m)^done\s*$"
        }

        It "writes bash-style absolute paths into run-agent.sh for local files" {
            $slowAgent = Join-Path $TestDrive "slow-wrapper-agent-$(Get-Random).sh"
            @"
#!/bin/bash
sleep 1
echo "done"
"@ | Out-File $slowAgent -Encoding utf8 -NoNewline
            $bashSlowAgent = ($slowAgent -replace '\\', '/')
            if ($bashSlowAgent -match '^([A-Za-z]):/(.+)$') {
                $bashSlowAgent = "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
            & bash -lc "chmod +x '$bashSlowAgent'"

            $job = Start-Job -ScriptBlock {
                param($invokeAgent, $roomDir, $agentCmd)
                & $invokeAgent -RoomDir $roomDir -RoleName "engineer" `
                    -Prompt "wrapper path test" -AgentCmd $agentCmd -TimeoutSeconds 10
            } -ArgumentList $script:InvokeAgent, $script:roomDir, $bashSlowAgent

            try {
                $wrapperFile = Join-Path $script:roomDir "artifacts" "run-agent.sh"
                $deadline = (Get-Date).AddSeconds(5)
                while (-not (Test-Path $wrapperFile) -and (Get-Date) -lt $deadline) {
                    Start-Sleep -Milliseconds 50
                }

                Test-Path $wrapperFile | Should -BeTrue

                $wrapperContent = Get-Content $wrapperFile -Raw
                $wrapperContent | Should -Match "export AGENT_OS_ROOM_DIR='/"
                $wrapperContent | Should -Match "export AGENT_OS_PID_FILE='/"
                $wrapperContent | Should -Match "export AGENT_OS_SKILLS_DIR='/"
                $wrapperContent | Should -Match "export OSTWIN_HOME='/"
                $wrapperContent | Should -Match "cat '/"
                $wrapperContent | Should -Match ">> '/"
                $wrapperContent | Should -Match "exec '/"

                $wrapperContent | Should -Not -Match "export AGENT_OS_ROOM_DIR='[A-Za-z]:"
                $wrapperContent | Should -Not -Match "export AGENT_OS_PID_FILE='[A-Za-z]:"
                $wrapperContent | Should -Not -Match "exec '[A-Za-z]:"
            }
            finally {
                $job | Wait-Job -Timeout 15 | Out-Null
                $job | Remove-Job -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
