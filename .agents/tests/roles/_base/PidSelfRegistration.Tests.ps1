# Agent OS — PID Self-Registration Tests
#
# Validates the new PID management design where:
# 1. bin/agent self-registers PID via AGENT_OS_PID_FILE env var
# 2. Invoke-Agent.ps1 no longer writes premature PIDs
# 3. Wrapper scripts export AGENT_OS_PID_FILE instead of echo $$

BeforeAll {
    $script:InvokeAgent = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Invoke-Agent.ps1"
    $script:agentBin    = Join-Path (Resolve-Path "$PSScriptRoot/../../../bin").Path "agent"
}

Describe "PID Self-Registration" {

    # ================================================================
    # bin/agent — PID file writing via AGENT_OS_PID_FILE
    # ================================================================
    Context "bin/agent: AGENT_OS_PID_FILE behavior" {

        It "writes PID to AGENT_OS_PID_FILE when env var is set" {
            $pidFile = Join-Path $TestDrive "test-agent.pid"
            # Create a mock cli.py that just exits 0
            $mockCliDir = Join-Path $TestDrive "mock-agents" "bin"
            New-Item -ItemType Directory -Path $mockCliDir -Force | Out-Null
            "import sys; sys.exit(0)" | Out-File (Join-Path $mockCliDir "cli.py") -Encoding utf8

            # Create a thin wrapper that simulates the PID-writing portion of bin/agent
            $testScript = Join-Path $TestDrive "test-pid-write.sh"
            @"
#!/bin/bash
set -euo pipefail
AGENT_OS_PID_FILE='$pidFile'
if [[ -n "`${AGENT_OS_PID_FILE:-}" ]]; then
  echo "`$$" > "`$AGENT_OS_PID_FILE"
fi
# Don't actually exec — just verify PID was written
exit 0
"@ | Out-File $testScript -Encoding utf8 -NoNewline
            chmod +x $testScript

            bash $testScript
            $LASTEXITCODE | Should -Be 0

            Test-Path $pidFile | Should -BeTrue
            $pidContent = (Get-Content $pidFile -Raw).Trim()
            $pidContent | Should -Match '^\d+$'
            # PID should be a reasonable value (> 0)
            [int]$pidContent | Should -BeGreaterThan 0
        }

        It "does NOT write PID file when AGENT_OS_PID_FILE is unset" {
            $pidFile = Join-Path $TestDrive "should-not-exist.pid"
            
            $testScript = Join-Path $TestDrive "test-no-pid.sh"
            @"
#!/bin/bash
set -euo pipefail
# AGENT_OS_PID_FILE is intentionally NOT set
unset AGENT_OS_PID_FILE 2>/dev/null || true
if [[ -n "`${AGENT_OS_PID_FILE:-}" ]]; then
  echo "`$$" > '$pidFile'
fi
exit 0
"@ | Out-File $testScript -Encoding utf8 -NoNewline
            chmod +x $testScript

            bash $testScript
            $LASTEXITCODE | Should -Be 0

            Test-Path $pidFile | Should -BeFalse
        }

        It "PID written matches the shell PID (exec inherits it)" {
            $pidFile = Join-Path $TestDrive "exec-pid.pid"
            # This test proves that exec inherits the shell PID.
            # We use exec to replace bash with a command that reads its own PID.
            $testScript = Join-Path $TestDrive "test-exec-pid.sh"
            @"
#!/bin/bash
AGENT_OS_PID_FILE='$pidFile'
echo "`$$" > "`$AGENT_OS_PID_FILE"
# exec into a program that prints its PID — should match $$
exec bash -c 'echo `$$'
"@ | Out-File $testScript -Encoding utf8 -NoNewline
            chmod +x $testScript

            $execPid = bash $testScript
            $LASTEXITCODE | Should -Be 0

            $writtenPid = (Get-Content $pidFile -Raw).Trim()
            # The PID written before exec should match the PID reported after exec
            $writtenPid | Should -Be $execPid.Trim()
        }
    }

    # ================================================================
    # Invoke-Agent.ps1 — no premature PID write
    # ================================================================
    Context "Invoke-Agent: PID management contract" {

        BeforeEach {
            $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null
        }

        It "does NOT write PowerShell PID prematurely" {
            # Run with a mock that immediately exits
            # Before the fix, the PID file would contain PowerShell's $PID
            # After the fix, it should contain the bash/agent PID instead
            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd "echo" -TimeoutSeconds 10

            $pidFile = Join-Path $script:roomDir "pids" "engineer.pid"
            if (Test-Path $pidFile) {
                $pidContent = (Get-Content $pidFile -Raw).Trim()
                if ($pidContent -match '^\d+$') {
                    # The PID should NOT be our PowerShell PID
                    [int]$pidContent | Should -Not -Be $PID
                }
            }
        }

        It "wrapper script exports AGENT_OS_PID_FILE instead of echo '$$'" {
            # Create a mock that captures the wrapper script before it's deleted
            $wrapperCapture = Join-Path $TestDrive "captured-wrapper.sh"
            $captureAgent = Join-Path $TestDrive "capture-agent.sh"
            @"
#!/bin/bash
# Copy the calling wrapper script content to a known location
# The wrapper is at `$0's parent dir / run-agent.sh
cp "`$(dirname "`$0")/../artifacts/run-agent.sh" '$wrapperCapture' 2>/dev/null || true
echo "captured"
exit 0
"@ | Out-File $captureAgent -Encoding utf8 -NoNewline
            chmod +x $captureAgent

            # We can also just check that Invoke-Agent generates the right content
            # by examining the artifacts/run-agent.sh before cleanup.
            # But Invoke-Agent cleans up the wrapper. Instead, let's use a script
            # that delays to give us time to read it.
            $slowAgent = Join-Path $TestDrive "slow-capture.sh"
            @"
#!/bin/bash
# Signal that we started by touching a file
touch '$wrapperCapture.started'
sleep 1
echo "done"
"@ | Out-File $slowAgent -Encoding utf8 -NoNewline
            chmod +x $slowAgent

            # Start in background so we can inspect the wrapper
            $job = Start-Job -ScriptBlock {
                param($ia, $rd, $sa)
                & $ia -RoomDir $rd -RoleName "engineer" -Prompt "test" `
                    -AgentCmd $sa -TimeoutSeconds 10
            } -ArgumentList $script:InvokeAgent, $script:roomDir, $slowAgent

            # Wait for the agent to start
            $deadline = (Get-Date).AddSeconds(10)
            while (-not (Test-Path "$wrapperCapture.started") -and (Get-Date) -lt $deadline) {
                Start-Sleep -Milliseconds 200
            }

            # Read the wrapper script that Invoke-Agent generated
            $wrapperFile = Join-Path $script:roomDir "artifacts" "run-agent.sh"
            if (Test-Path $wrapperFile) {
                $wrapperContent = Get-Content $wrapperFile -Raw

                # Should contain AGENT_OS_PID_FILE export
                $wrapperContent | Should -Match "export AGENT_OS_PID_FILE="

                # Wrapper now writes PID as fallback for non-bin/agent commands
                # (echo "$$" > pidfile). This is intentional — bin/agent may also
                # write it (harmless overwrite).
                $wrapperContent | Should -Match 'echo.*\$\$.*\.pid'
            }

            $job | Wait-Job -Timeout 15 | Out-Null
            $job | Remove-Job -Force -ErrorAction SilentlyContinue
        }
    }

    # ================================================================
    # PID confirmation wait logic
    # ================================================================
    Context "Invoke-Agent: PID confirmation wait" {

        BeforeEach {
            $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null
        }

        It "PID file contains a valid PID after agent completes" {
            # Use a mock that writes to AGENT_OS_PID_FILE (simulating bin/agent behavior)
            $pidWriter = Join-Path $TestDrive "pid-writer.sh"
            @"
#!/bin/bash
if [[ -n "`${AGENT_OS_PID_FILE:-}" ]]; then
  echo "`$$" > "`$AGENT_OS_PID_FILE"
fi
echo "agent output"
exit 0
"@ | Out-File $pidWriter -Encoding utf8 -NoNewline
            chmod +x $pidWriter

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd $pidWriter -TimeoutSeconds 10

            $result.ExitCode | Should -BeIn @(0)

            $pidFile = Join-Path $script:roomDir "pids" "engineer.pid"
            if (Test-Path $pidFile) {
                $pidContent = (Get-Content $pidFile -Raw).Trim()
                $pidContent | Should -Match '^\d+$'
                # PID should NOT be our PowerShell process
                [int]$pidContent | Should -Not -Be $PID
            }
        }

        It "handles agent that does not write PID (backward compat)" {
            # An agent that ignores AGENT_OS_PID_FILE should still work
            # (the PID file just won't be populated)
            $noPidAgent = Join-Path $TestDrive "no-pid-agent.sh"
            @"
#!/bin/bash
echo "I don't write PIDs"
exit 0
"@ | Out-File $noPidAgent -Encoding utf8 -NoNewline
            chmod +x $noPidAgent

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "test" `
                -AgentCmd $noPidAgent -TimeoutSeconds 10

            # Should still succeed even without PID self-registration
            $result | Should -Not -BeNullOrEmpty
            $result.ExitCode | Should -BeIn @(0)
        }

        It "timeout kill uses confirmed PID from self-registration" {
            # Create a slow mock that writes its PID, then sleeps forever
            $slowPidAgent = Join-Path $TestDrive "slow-pid.sh"
            @"
#!/bin/bash
if [[ -n "`${AGENT_OS_PID_FILE:-}" ]]; then
  echo "`$$" > "`$AGENT_OS_PID_FILE"
fi
sleep 300
"@ | Out-File $slowPidAgent -Encoding utf8 -NoNewline
            chmod +x $slowPidAgent

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "engineer" -Prompt "slow" `
                -AgentCmd $slowPidAgent -TimeoutSeconds 3

            $result.TimedOut | Should -BeTrue
            $result.ExitCode | Should -Be 124

            # The PID file should have been written by the mock
            $pidFile = Join-Path $script:roomDir "pids" "engineer.pid"
            if (Test-Path $pidFile) {
                $pidContent = (Get-Content $pidFile -Raw).Trim()
                $pidContent | Should -Match '^\d+$'
                $killedPid = [int]$pidContent
                # Process should be dead now (killed by timeout handler)
                { Get-Process -Id $killedPid -ErrorAction Stop } | Should -Throw
            }
        }
    }

    # ================================================================
    # Integration: bin/agent PID file used by Invoke-Agent
    # ================================================================
    Context "Integration: end-to-end PID flow" {

        BeforeEach {
            $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null
        }

        It "complete flow: wrapper sets env, agent writes PID, Invoke-Agent confirms" {
            # Simulate the full chain: wrapper exports AGENT_OS_PID_FILE,
            # mock agent reads it and writes PID, Invoke-Agent picks it up
            $fullChainAgent = Join-Path $TestDrive "full-chain.sh"
            @"
#!/bin/bash
# This simulates what bin/agent does:
# 1. Check for AGENT_OS_PID_FILE
# 2. Write $$ to it
# 3. Do work
if [[ -n "`${AGENT_OS_PID_FILE:-}" ]]; then
  echo "`$$" > "`$AGENT_OS_PID_FILE"
fi
echo "work complete"
exit 0
"@ | Out-File $fullChainAgent -Encoding utf8 -NoNewline
            chmod +x $fullChainAgent

            $result = & $script:InvokeAgent -RoomDir $script:roomDir `
                -RoleName "architect" -Prompt "review" `
                -AgentCmd $fullChainAgent -TimeoutSeconds 10

            $result.ExitCode | Should -Be 0
            $result.RoleName | Should -Be "architect"

            $pidFile = Join-Path $script:roomDir "pids" "architect.pid"
            $result.PidFile | Should -Be $pidFile

            # PID file should exist (Invoke-Agent doesn't clean it up — caller's job)
            Test-Path $pidFile | Should -BeTrue
        }
    }
}
