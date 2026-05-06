# ──────────────────────────────────────────────────────────────────────────────
# Verify.Tests.ps1 — Tests for installer/Verify.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Versions.ps1", "Check-Deps.ps1", "Verify.ps1")
    . $script:_ImportedModuleScript
}

Describe "Verify-Components" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-verify-$(Get-Random)"
        New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        $script:InstallDir = $testDir
        $script:VenvDir = Join-Path $testDir ".venv"
        $script:DashboardOnly = $false
        $script:PythonVersion = "3.12"
        $script:PwshCurrentVersion = "7.4"
        $script:WinVersion = "11"
        $script:WinBuild = 22631
        $script:DevModeEnabled = $false
    }

    It "Should not throw in full mode" {
        { Verify-Components } | Should -Not -Throw
    }

    It "Should not throw in dashboard-only mode" {
        $script:DashboardOnly = $true
        { Verify-Components } | Should -Not -Throw
    }
}

Describe "Print-CompletionBanner" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-banner-$(Get-Random)"
        New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        $script:InstallDir = $testDir
        $script:DashboardPort = 3366
        $script:TunnelUrl = ""
        $script:StartChannel = $false
    }

    It "Should not throw" {
        { Print-CompletionBanner } | Should -Not -Throw
    }

    It "Should not throw with tunnel URL" {
        $script:TunnelUrl = "https://test.ngrok.io"
        { Print-CompletionBanner } | Should -Not -Throw
    }

    It "Should not throw with channel enabled" {
        $script:StartChannel = $true
        { Print-CompletionBanner } | Should -Not -Throw
    }

    It "Should display API key when available" {
        # Create .env with key
        $envFile = Join-Path $testDir ".env"
        Set-Content -Path $envFile -Value "OSTWIN_API_KEY=test_key_123"

        { Print-CompletionBanner } | Should -Not -Throw
    }
}

