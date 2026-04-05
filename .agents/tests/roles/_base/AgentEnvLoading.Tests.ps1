# Agent OS — agent env loading tests
#
# Validates that the bash agent entrypoint can hydrate provider keys from the
# project root .env file when orchestration exports AGENT_OS_PROJECT_DIR.

BeforeAll {
    $script:agentBin = Join-Path (Resolve-Path "$PSScriptRoot/../../../bin").Path "agent"
}

Describe "bin/agent env loading" {
    It "loads GOOGLE_API_KEY from project root .env via AGENT_OS_PROJECT_DIR" {
        $mockAgentsDir = Join-Path $TestDrive "mock-agents"
        $mockBinDir = Join-Path $mockAgentsDir "bin"
        New-Item -ItemType Directory -Path $mockBinDir -Force | Out-Null
        Copy-Item $script:agentBin (Join-Path $mockBinDir "agent")

        @'
import os
import sys

print(os.environ.get("GOOGLE_API_KEY", ""))
sys.exit(0)
'@ | Out-File (Join-Path $mockBinDir "cli.py") -Encoding utf8 -NoNewline

        $projectDir = Join-Path $TestDrive "project"
        New-Item -ItemType Directory -Path $projectDir -Force | Out-Null
        "GOOGLE_API_KEY=project-root-key" | Out-File (Join-Path $projectDir ".env") -Encoding utf8 -NoNewline

        $homeDir = Join-Path $TestDrive "home"
        New-Item -ItemType Directory -Path $homeDir -Force | Out-Null

        $runnerScript = Join-Path $TestDrive "run-agent-env.sh"
        $safeHomeDir = $homeDir -replace '\\', '/'
        $safeProjectDir = $projectDir -replace '\\', '/'
        $safeAgentPath = (Join-Path $mockBinDir "agent") -replace '\\', '/'
        $safeRunnerScript = $runnerScript -replace '\\', '/'
        foreach ($varName in @('safeHomeDir', 'safeProjectDir', 'safeAgentPath', 'safeRunnerScript')) {
            $value = Get-Variable -Name $varName -ValueOnly
            if ($value -match '^([A-Za-z]):/(.+)$') {
                Set-Variable -Name $varName -Value "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
            }
        }

@"
#!/bin/bash
set -euo pipefail
unset GOOGLE_API_KEY 2>/dev/null || true
export HOME='$safeHomeDir'
export AGENT_OS_PROJECT_DIR='$safeProjectDir'
exec bash '$safeAgentPath'
"@ | Out-File $runnerScript -Encoding utf8 -NoNewline

        $originalGoogleApiKey = [Environment]::GetEnvironmentVariable("GOOGLE_API_KEY", "Process")
        try {
            [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", $null, "Process")
            $output = & bash -lc "bash '$safeRunnerScript'"
            $LASTEXITCODE | Should -Be 0
            $output.Trim() | Should -Be "project-root-key"
        }
        finally {
            [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", $originalGoogleApiKey, "Process")
        }
    }
}
