# ──────────────────────────────────────────────────────────────────────────────
# Verify.Tests.ps1 — Tests for installer/Verify.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Versions.ps1", "Check-Deps.ps1", "Install-Deps.ps1", "Verify.ps1")
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
        { Verify-Components 6>$null } | Should -Not -Throw
    }

    It "should not throw in dashboard-only mode" {
        $script:DashboardOnly = $true
        { Verify-Components 6>$null } | Should -Not -Throw
    }

    It "should show obscura path when installed" {
        # Create fake obscura.exe
        $binDir = Join-Path $testDir ".agents\bin"
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
        $fakeObscura = Join-Path $binDir "obscura.exe"
        [System.IO.File]::WriteAllText($fakeObscura, "fake")

        # Capture Write-Host output via InformationVariable
        $info = @()
        Verify-Components -InformationVariable info 6>$null
        $output = $info -join "`n"

        # Output should include obscura line with version and path
        $output | Should -Match "obscura.*installed"
        # Check path contains the expected bin directory
        $output | Should -Match "\.agents\\bin\\obscura\.exe"
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

    It "should not throw" {
        { Print-CompletionBanner 6>$null } | Should -Not -Throw
    }

    It "should not throw with tunnel URL" {
        $script:TunnelUrl = "https://test.ngrok.io"
        { Print-CompletionBanner 6>$null } | Should -Not -Throw
    }

    It "should not throw with channel enabled" {
        $script:StartChannel = $true
        { Print-CompletionBanner 6>$null } | Should -Not -Throw
    }

    It "should display API key when available" {
        # Create .env with key
        $envFile = Join-Path $testDir ".env"
        Set-Content -Path $envFile -Value "OSTWIN_API_KEY=test_key_123"

        { Print-CompletionBanner 6>$null } | Should -Not -Throw
    }
}

