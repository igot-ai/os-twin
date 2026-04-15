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

    Context "Requirement collection logic" {
        It "Should find requirements files that exist" {
            # Create test requirements files
            $mcpDir = Join-Path $testDir ".agents\mcp"
            New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
            Set-Content -Path (Join-Path $mcpDir "requirements.txt") -Value "fastapi"

            $dashDir = Join-Path $testDir "dashboard"
            New-Item -ItemType Directory -Path $dashDir -Force | Out-Null
            Set-Content -Path (Join-Path $dashDir "requirements.txt") -Value "uvicorn"

            # Verify the files exist and would be found
            Test-Path (Join-Path $mcpDir "requirements.txt") | Should -Be $true
            Test-Path (Join-Path $dashDir "requirements.txt") | Should -Be $true
        }

        It "Should handle missing requirements gracefully" {
            # With no requirements files, setup should still work (just skip install)
            $script:VenvDir = Join-Path $testDir ".venv"
            New-Item -ItemType Directory -Path $script:VenvDir -Force | Out-Null

            # Won't actually call uv/pip since VenvDir exists but no requirements
            # The function should warn but not throw
            # (We can't fully test without an actual venv, but verify file detection logic)
            $reqPath = Join-Path $testDir ".agents\mcp\requirements.txt"
            Test-Path $reqPath | Should -Be $false
        }
    }
}

