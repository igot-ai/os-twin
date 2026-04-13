# ──────────────────────────────────────────────────────────────────────────────
# Sync-Agents.Tests.ps1 — Tests for installer/Sync-Agents.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Sync-Agents.ps1")
    . $script:_ImportedModuleScript
}

Describe "Sync-OpenCodeAgents" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-sync-$(Get-Random)"
        $installDir = Join-Path $testDir "install"
        $rolesDir = Join-Path $installDir ".agents\roles"
        New-Item -ItemType Directory -Path $rolesDir -Force | Out-Null

        $script:InstallDir = $installDir

        # Override opencode home to use test directory
        $env:XDG_CONFIG_HOME = Join-Path $testDir "config"
    }

    AfterEach {
        Remove-Item Env:XDG_CONFIG_HOME -ErrorAction SilentlyContinue
    }

    It "Should create agents directory" {
        Sync-OpenCodeAgents
        $agentsDir = Join-Path $testDir "config\opencode\agents"
        Test-Path $agentsDir | Should -Be $true
    }

    It "Should sync roles with ROLE.md" {
        # Create a test role
        $roleDir = Join-Path $rolesDir "test-engineer"
        New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
        Set-Content -Path (Join-Path $roleDir "role.json") -Value '{"name": "test-engineer"}'
        Set-Content -Path (Join-Path $roleDir "ROLE.md") -Value "# Test Engineer"

        Sync-OpenCodeAgents

        $agentFile = Join-Path $testDir "config\opencode\agents\test-engineer.md"
        Test-Path $agentFile | Should -Be $true
        Get-Content $agentFile -Raw | Should -Match "# Test Engineer"
    }

    It "Should skip _base directory" {
        $baseDir = Join-Path $rolesDir "_base"
        New-Item -ItemType Directory -Path $baseDir -Force | Out-Null
        Set-Content -Path (Join-Path $baseDir "role.json") -Value '{}'
        Set-Content -Path (Join-Path $baseDir "ROLE.md") -Value "# Base"

        Sync-OpenCodeAgents

        $agentFile = Join-Path $testDir "config\opencode\agents\_base.md"
        Test-Path $agentFile | Should -Be $false
    }

    It "Should skip roles without role.json" {
        $roleDir = Join-Path $rolesDir "invalid-role"
        New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
        # No role.json
        Set-Content -Path (Join-Path $roleDir "ROLE.md") -Value "# Invalid"

        Sync-OpenCodeAgents

        $agentFile = Join-Path $testDir "config\opencode\agents\invalid-role.md"
        Test-Path $agentFile | Should -Be $false
    }

    It "Should skip roles without ROLE.md" {
        $roleDir = Join-Path $rolesDir "no-readme"
        New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
        Set-Content -Path (Join-Path $roleDir "role.json") -Value '{}'
        # No ROLE.md

        Sync-OpenCodeAgents

        $agentFile = Join-Path $testDir "config\opencode\agents\no-readme.md"
        Test-Path $agentFile | Should -Be $false
    }
}

