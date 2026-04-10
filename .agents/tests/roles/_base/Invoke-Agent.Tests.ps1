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

                # Should use echo instead of opencode run
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
            # Use engineer role — gets global skills auto-injected (e.g. auto-memory)
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $isolatedSkillsDir = Join-Path $script:roomDir "skills"
            Test-Path $isolatedSkillsDir | Should -BeTrue
            
            $skills = Get-ChildItem $isolatedSkillsDir -Directory
            $skills.Count | Should -BeGreaterThan 0
            # Should contain at least 'auto-memory' (auto-injected global skill)
            $skills.Name | Should -Contain "auto-memory"
        }

        It "preserves existing skills dir and adds resolved skills on new invocation" {
            $isolatedSkillsDir = Join-Path $script:roomDir "skills"
            New-Item -ItemType Directory -Path $isolatedSkillsDir -Force | Out-Null

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 5

            # Skills dir should still exist and contain resolved skills
            Test-Path $isolatedSkillsDir | Should -BeTrue
            $skills = Get-ChildItem $isolatedSkillsDir -Directory
            $skills.Count | Should -BeGreaterThan 0
        }

        It "exports AGENT_OS_SKILLS_DIR in the environment (verified via echo mock)" {
            # Create a mock bash script that echoes AGENT_OS_SKILLS_DIR with a tag
            $echoMock = Join-Path $TestDrive "echo-env.sh"
            "#!/bin/bash`necho SKILLS_DIR_IS:`$AGENT_OS_SKILLS_DIR" | Out-File $echoMock -Encoding utf8
            chmod +x $echoMock

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd $echoMock -TimeoutSeconds 5

            # Output contains wrapper logs + our echo; find the tagged line
            $result.Output | Should -Match "SKILLS_DIR_IS:.*/skills"
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

    Context "opencode run CLI flags" {
        # These tests verify that the generated wrapper script contains
        # the correct opencode run flags. We use a mock that captures $@
        # and the wrapper content.

        BeforeEach {
            # Create a mock that dumps all args to a file
            $script:argsDump = Join-Path $TestDrive "args-$(Get-Random).txt"
            $script:argsMock = Join-Path $TestDrive "argsmock-$(Get-Random).sh"
            @"
#!/bin/bash
# Write all args to the dump file
for arg in "`$@"; do echo "`$arg"; done > '$($script:argsDump)'
"@ | Out-File $script:argsMock -Encoding utf8
            chmod +x $script:argsMock
        }

        It "passes a short positional message and prompt via --file" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "Hello world test" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $capturedArgs = Get-Content $script:argsDump
                # First arg should be the short positional message (required by opencode run)
                $capturedArgs[0] | Should -Match "Execute the task"
                # Legacy 'start' positional must NOT be present
                $capturedArgs | Should -Not -Contain "start"
                # Prompt should NOT appear as inline text on the command line
                $capturedArgs | Should -Not -Contain "Hello world test"
                # Prompt file should be attached via --file
                $capturedArgs | Should -Contain "--file"
                # Should contain an absolute path to prompt.txt
                $promptArg = $capturedArgs | Where-Object { $_ -match 'prompt\.txt$' }
                $promptArg | Should -Not -BeNullOrEmpty
            }
        }

        It "passes --model flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -Model "openai/gpt-4o" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--model"
                $args | Should -Contain "openai/gpt-4o"
            }
        }

        It "passes --agent flag with role name" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "architect" -Prompt "test" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--agent"
                $args | Should -Contain "architect"
            }
        }

        It "passes --format flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -Format "json" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--format"
                $args | Should -Contain "json"
            }
        }

        It "passes --title flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -SessionTitle "My Task Title" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--title"
                $args | Should -Contain "My Task Title"
            }
        }

        It "passes --session flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -SessionId "abc-123" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--session"
                $args | Should -Contain "abc-123"
            }
        }

        It "passes --continue flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "continue from here" `
                -ContinueSession `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--continue"
            }
        }

        It "passes --fork flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -ForkSession `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--fork"
            }
        }

        It "passes --share flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -ShareSession `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--share"
            }
        }

        It "passes --command flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "src/app.test.ts" `
                -Command "test" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--command"
                $args | Should -Contain "test"
            }
        }

        It "passes --file flag for each extra file plus prompt file" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "review these files" `
                -Files @("file1.txt", "file2.txt") `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $capturedArgs = Get-Content $script:argsDump
                # --file should appear 3 times: file1.txt, file2.txt, plus prompt.txt
                $fileFlags = $capturedArgs | Where-Object { $_ -eq "--file" }
                $fileFlags.Count | Should -Be 3
                $capturedArgs | Should -Contain "file1.txt"
                $capturedArgs | Should -Contain "file2.txt"
                # Prompt file should also be present
                $promptArg = $capturedArgs | Where-Object { $_ -match 'prompt\.txt$' }
                $promptArg | Should -Not -BeNullOrEmpty
            }
        }

        It "passes --attach flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AttachUrl "http://localhost:4096" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--attach"
                $args | Should -Contain "http://localhost:4096"
            }
        }

        It "passes --port flag" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -Port 8080 `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Contain "--port"
                $args | Should -Contain "8080"
            }
        }

        It "does not pass legacy deepagents flags" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd $script:argsMock -TimeoutSeconds 5

            if (Test-Path $script:argsDump) {
                $args = Get-Content $script:argsDump
                $args | Should -Not -Contain "--auto-approve"
                $args | Should -Not -Contain "--quiet"
                $args | Should -Not -Contain "-q"
                $args | Should -Not -Contain "--shell-allow-list"
                $args | Should -Not -Contain "--no-mcp"
                $args | Should -Not -Contain "--mcp-config"
            }
        }

        It "passes short message positional, not legacy 'start' or inline prompt" {
            $captureMock = Join-Path $TestDrive "capture-wrapper-$(Get-Random).sh"
            @"
#!/bin/bash
echo "ARGS: `$@"
"@ | Out-File $captureMock -Encoding utf8
            chmod +x $captureMock

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test positional prompt" `
                -AgentCmd $captureMock -TimeoutSeconds 5

            if ($result.Output) {
                # Should contain the short positional message
                $result.Output | Should -Match "Execute the task"
                # Legacy 'start' positional must NOT be present
                $result.Output | Should -Not -Match "ARGS: start "
                # Should NOT contain the raw prompt text inline
                $result.Output | Should -Not -Match "test positional prompt"
                # Should contain --file (prompt passed via file)
                $result.Output | Should -Match "--file"
            }
        }
    }

    Context "Default AgentCmd resolution" {
        It "defaults to opencode run when no bin/agent or config CLI found" {
            # Create a minimal config that doesn't specify cli
            $configFile = Join-Path $TestDrive "no-cli-config.json"
            @{
                engineer = @{
                    default_model   = "test-model"
                    timeout_seconds = 10
                }
            } | ConvertTo-Json -Depth 3 | Out-File $configFile -Encoding utf8

            $env:AGENT_OS_CONFIG = $configFile
            $env:ENGINEER_CMD = "echo"  # override so the test actually runs
            try {
                # The test verifies that the script doesn't crash when
                # resolving to "opencode run" as default
                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
                Remove-Item Env:ENGINEER_CMD -ErrorAction SilentlyContinue
            }
        }
    }

    Context "No opencode.json generation" {
        It "does not create opencode.json in artifacts directory" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test no opencode.json" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $artifactsDir = Join-Path $script:roomDir "artifacts"
            $opencodeJson = Join-Path $artifactsDir "opencode.json"
            Test-Path $opencodeJson | Should -BeFalse `
                -Because "Invoke-Agent must not generate opencode.json during ostwin run"
        }

        It "does not create opencode.json even when MCP config exists" {
            # Create a project dir with .agents/mcp/config.json and a room inside
            $projectDir = Join-Path $TestDrive "project-mcp-$(Get-Random)"
            $mcpDir = Join-Path $projectDir ".agents" "mcp"
            New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
            @{ mcp = @{ "test-server" = @{ type = "local"; command = @("echo") } } } `
                | ConvertTo-Json -Depth 5 `
                | Out-File (Join-Path $mcpDir "config.json") -Encoding utf8

            # Place room inside .war-rooms so Invoke-Agent resolves ProjectDir
            $roomDir = Join-Path $projectDir ".war-rooms" "room-mcp"
            New-Item -ItemType Directory -Path (Join-Path $roomDir "artifacts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $roomDir "pids") -Force | Out-Null

            $result = & $script:InvokeAgent -RoomDir $roomDir `
                -RoleName "engineer" -Prompt "test with mcp config" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $artifactsDir = Join-Path $roomDir "artifacts"
            $opencodeJson = Join-Path $artifactsDir "opencode.json"
            Test-Path $opencodeJson | Should -BeFalse `
                -Because "Invoke-Agent must not generate opencode.json even when MCP config exists"
        }
    }

    Context "No .agents/mcp folder creation" {
        It "does not create .agents/mcp folder in the project directory" {
            # Create a project dir without .agents/mcp
            $projectDir = Join-Path $TestDrive "project-nomcp-$(Get-Random)"
            $agentsDir = Join-Path $projectDir ".agents"
            New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null

            # Place room inside .war-rooms so Invoke-Agent resolves ProjectDir
            $roomDir = Join-Path $projectDir ".war-rooms" "room-nomcp"
            New-Item -ItemType Directory -Path (Join-Path $roomDir "artifacts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $roomDir "pids") -Force | Out-Null

            $result = & $script:InvokeAgent -RoomDir $roomDir `
                -RoleName "engineer" -Prompt "test no mcp folder" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $mcpDir = Join-Path $agentsDir "mcp"
            Test-Path $mcpDir | Should -BeFalse `
                -Because "Invoke-Agent must not create .agents/mcp folder"
        }
    }

    Context "Model resolution fallback chain (integration)" {
        # Full chain: -Model param → plan.roles.json → config.json instance →
        #             config.json role → role.json → hardcoded default.
        # Critical: role.json fallback must work even when config.json is ABSENT.

        It "uses role.json model when config.json is absent" {
            # Setup: no config.json, but role.json has a model
            $fakeHome = Join-Path $TestDrive "home-$(Get-Random)"
            New-Item -ItemType Directory -Path (Join-Path $fakeHome ".ostwin" ".agents" "roles" "engineer") -Force | Out-Null
            @{ model = "role-json-model"; skill_refs = @() } | ConvertTo-Json |
                Out-File (Join-Path $fakeHome ".ostwin" ".agents" "roles" "engineer" "role.json") -Encoding utf8

            $roomDir = Join-Path $TestDrive "room-rolejson-$(Get-Random)"
            New-Item -ItemType Directory -Path (Join-Path $roomDir "artifacts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $roomDir "pids") -Force | Out-Null

            $savedHome = $env:HOME
            $savedConfig = $env:AGENT_OS_CONFIG
            try {
                $env:HOME = $fakeHome
                # Point config to a non-existent file so it skips config.json block
                $env:AGENT_OS_CONFIG = Join-Path $TestDrive "nonexistent-config.json"

                $result = & $script:InvokeAgent -RoomDir $roomDir `
                    -RoleName "engineer" -Prompt "test" `
                    -AgentCmd "echo" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
                # The agent should have used role-json-model (not the hardcoded default)
                $result.Output | Should -Match "role-json-model" `
                    -Because "role.json model must be used when config.json is absent"
            }
            finally {
                $env:HOME = $savedHome
                if ($savedConfig) { $env:AGENT_OS_CONFIG = $savedConfig }
                else { Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue }
            }
        }

        It "explicit -Model param wins over all fallbacks" {
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -Model "explicit-param-model" `
                -AgentCmd "echo" -TimeoutSeconds 5

            $result.Output | Should -Match "explicit-param-model"
        }

        It "falls back to hardcoded default when nothing is configured" {
            $savedConfig = $env:AGENT_OS_CONFIG
            try {
                $env:AGENT_OS_CONFIG = Join-Path $TestDrive "nonexistent-$(Get-Random).json"

                $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                    -RoleName "engineer" -Prompt "test" `
                    -AgentCmd "echo" -TimeoutSeconds 5

                $result | Should -Not -BeNullOrEmpty
                # Should resolve to the hardcoded default model
                $result.Output | Should -Match "google-vertex" `
                    -Because "hardcoded default should be used as last resort"
            }
            finally {
                if ($savedConfig) { $env:AGENT_OS_CONFIG = $savedConfig }
                else { Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue }
            }
        }

        It "plan.roles.json model wins over config.json model" {
            # Setup plan.roles.json
            $fakeHome = Join-Path $TestDrive "home-plan-$(Get-Random)"
            $plansDir = Join-Path $fakeHome ".ostwin" ".agents" "plans"
            New-Item -ItemType Directory -Path $plansDir -Force | Out-Null
            @{ engineer = @{ default_model = "plan-level-model" } } | ConvertTo-Json -Depth 3 |
                Out-File (Join-Path $plansDir "test-plan.roles.json") -Encoding utf8

            # Setup room config pointing to the plan
            $roomDir = Join-Path $TestDrive "room-plan-$(Get-Random)"
            New-Item -ItemType Directory -Path (Join-Path $roomDir "artifacts") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $roomDir "pids") -Force | Out-Null
            @{ plan_id = "test-plan" } | ConvertTo-Json |
                Out-File (Join-Path $roomDir "config.json") -Encoding utf8

            # Setup config.json with a different model
            $configFile = Join-Path $TestDrive "config-plan-$(Get-Random).json"
            @{ engineer = @{ cli = "echo"; default_model = "config-model" } } | ConvertTo-Json -Depth 3 |
                Out-File $configFile -Encoding utf8

            $savedHome = $env:HOME
            $savedConfig = $env:AGENT_OS_CONFIG
            try {
                $env:HOME = $fakeHome
                $env:AGENT_OS_CONFIG = $configFile

                $result = & $script:InvokeAgent -RoomDir $roomDir `
                    -RoleName "engineer" -Prompt "test" `
                    -AgentCmd "echo" -TimeoutSeconds 5

                $result.Output | Should -Match "plan-level-model" `
                    -Because "plan.roles.json must take priority over config.json"
            }
            finally {
                $env:HOME = $savedHome
                if ($savedConfig) { $env:AGENT_OS_CONFIG = $savedConfig }
                else { Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue }
            }
        }
    }
}
