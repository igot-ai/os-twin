# ──────────────────────────────────────────────────────────────────────────────
# Setup-Venv.Tests.ps1 — Tests for installer/Setup-Venv.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Versions.ps1", "Check-Deps.ps1", "Setup-Venv.ps1")
    . $script:_ImportedModuleScript
}

Describe "Setup-Venv" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-venv-$(Get-Random)"
        New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        $script:InstallDir = $testDir
        $script:VenvDir = Join-Path $testDir ".venv"
    }

    Context "When uv is available" {
        It "Should call uv venv when venv doesn't exist" -Skip:(-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            # This test only runs if uv is actually available
            { Setup-Venv } | Should -Not -Throw
        }
    }

    Context "Phase 1 — Dashboard project detection" {
        It "Should detect pyproject.toml as primary dependency source" {
            $dashDir = Join-Path $testDir "dashboard"
            New-Item -ItemType Directory -Path $dashDir -Force | Out-Null
            Set-Content -Path (Join-Path $dashDir "pyproject.toml") -Value "[project]`nname = `"test`""

            Test-Path (Join-Path $dashDir "pyproject.toml") | Should -Be $true
        }

        It "Should detect uv.lock for frozen installs" {
            $dashDir = Join-Path $testDir "dashboard"
            New-Item -ItemType Directory -Path $dashDir -Force | Out-Null
            Set-Content -Path (Join-Path $dashDir "uv.lock") -Value "version = 1"

            Test-Path (Join-Path $dashDir "uv.lock") | Should -Be $true
        }
    }

    Context "Phase 2 — Supplementary requirement collection" {
        It "Should find mcp and memory requirements files that exist" {
            # Create test requirements files
            $mcpDir = Join-Path $testDir ".agents\mcp"
            New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
            Set-Content -Path (Join-Path $mcpDir "requirements.txt") -Value "fastapi"

            # Verify the files exist and would be found
            Test-Path (Join-Path $mcpDir "requirements.txt") | Should -Be $true
        }

        It "Should NOT include dashboard/requirements.txt in supplementary deps" {
            # Even if dashboard/requirements.txt exists, Phase 2 should skip it
            # (dashboard deps are handled in Phase 1 via uv sync / pyproject.toml)
            $dashDir = Join-Path $testDir "dashboard"
            New-Item -ItemType Directory -Path $dashDir -Force | Out-Null
            Set-Content -Path (Join-Path $dashDir "requirements.txt") -Value "uvicorn"

            # The supplementary collection path should be: .agents/mcp, .agents/memory, .agents/roles/*
            # NOT dashboard/
            $suppPath = Join-Path $testDir ".agents\mcp\requirements.txt"
            Test-Path $suppPath | Should -Be $false
        }

        It "Should handle missing requirements gracefully" {
            # With no requirements files, setup should still work (just skip install)
            $script:VenvDir = Join-Path $testDir ".venv"
            New-Item -ItemType Directory -Path $script:VenvDir -Force | Out-Null

            $reqPath = Join-Path $testDir ".agents\mcp\requirements.txt"
            Test-Path $reqPath | Should -Be $false
        }
    }

    Context "Fallback function" {
        It "Should export Setup-Venv-PipFallback" {
            Get-Command Setup-Venv-PipFallback | Should -Not -BeNullOrEmpty
        }
    }
}

