# ──────────────────────────────────────────────────────────────────────────────
# Patch-MCP.Tests.ps1 — Tests for installer/Patch-MCP.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Patch-MCP.ps1")
    . $script:_ImportedModuleScript
}

Describe "Patch-McpConfig" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-patch-$(Get-Random)"
        $mcpDir = Join-Path $testDir ".agents\mcp"
        New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
        $script:InstallDir = $testDir
        $script:VenvDir = Join-Path $testDir ".venv"
    }

    It "Should return silently when config.json doesn't exist" {
        { Patch-McpConfig } | Should -Not -Throw
    }

    It "Should add AGENT_DIR and OSTWIN_PYTHON to .env when not present" {
        Set-Content -Path (Join-Path $mcpDir "config.json") -Value '{"mcpServers": {}}'
        $envFile = Join-Path $testDir ".env"
        Set-Content -Path $envFile -Value "SOME_KEY=value"

        # Mock the python calls since we don't have a real venv
        $script:PatchScriptsDir = Join-Path $TestDrive "fake-scripts"
        New-Item -ItemType Directory -Path $script:PatchScriptsDir -Force | Out-Null

        Patch-McpConfig 2>$null

        $content = Get-Content $envFile -Raw
        $content | Should -Match 'AGENT_DIR='
        $content | Should -Match 'OSTWIN_PYTHON='
    }

    It "Should not duplicate AGENT_DIR and OSTWIN_PYTHON in .env" {
        Set-Content -Path (Join-Path $mcpDir "config.json") -Value '{"mcpServers": {}}'
        $venvPython = Join-Path $script:VenvDir "Scripts\python.exe"
        $envFile = Join-Path $testDir ".env"
        Set-Content -Path $envFile -Value "AGENT_DIR=$testDir`nOSTWIN_PYTHON=$venvPython"

        $script:PatchScriptsDir = Join-Path $TestDrive "fake-scripts"
        New-Item -ItemType Directory -Path $script:PatchScriptsDir -Force | Out-Null

        Patch-McpConfig 2>$null

        $agentDirLines = Get-Content $envFile | Where-Object { $_ -match 'AGENT_DIR=' }
        $ostwinPythonLines = Get-Content $envFile | Where-Object { $_ -match 'OSTWIN_PYTHON=' }
        $agentDirLines.Count | Should -Be 1
        $ostwinPythonLines.Count | Should -Be 1
    }

    It "Should create .env when it doesn't exist" {
        Set-Content -Path (Join-Path $mcpDir "config.json") -Value '{"mcpServers": {}}'

        $script:PatchScriptsDir = Join-Path $TestDrive "fake-scripts"
        New-Item -ItemType Directory -Path $script:PatchScriptsDir -Force | Out-Null

        Patch-McpConfig 2>$null

        $envFile = Join-Path $testDir ".env"
        Test-Path $envFile | Should -Be $true
    }

    It "Should export AGENT_DIR and OSTWIN_PYTHON" {
        Set-Content -Path (Join-Path $mcpDir "config.json") -Value '{"mcpServers": {}}'
        $envFile = Join-Path $testDir ".env"

        $script:PatchScriptsDir = Join-Path $TestDrive "fake-scripts"
        New-Item -ItemType Directory -Path $script:PatchScriptsDir -Force | Out-Null

        Patch-McpConfig 2>$null

        $content = Get-Content $envFile -Raw
        $content | Should -Match 'export AGENT_DIR='
        $content | Should -Match 'export OSTWIN_PYTHON='
    }
}

