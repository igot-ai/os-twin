# ──────────────────────────────────────────────────────────────────────────────
# Install-Deps.Tests.ps1 — Tests for installer/Install-Deps.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Versions.ps1", "Check-Deps.ps1", "Install-Deps.ps1")
    . $script:_ImportedModuleScript
}

Describe "Install-PesterModule" {
    It "Should not throw" {
        { Install-PesterModule } | Should -Not -Throw
    }

    It "Should find Pester 5+" {
        $installed = Get-Module -ListAvailable Pester | Where-Object { $_.Version.Major -ge 5 }
        # Either it's installed or the function should handle it
        if ($installed) {
            $installed.Version.Major | Should -BeGreaterOrEqual 5
        }
    }
}

Describe "Install-UV" {
    It "Should define the function" {
        Get-Command Install-UV | Should -Not -BeNullOrEmpty
    }

    It "Should have CmdletBinding" {
        $cmd = Get-Command Install-UV
        $cmd.CmdletBinding | Should -Be $true
    }
}

Describe "Install-Python" {
    It "Should define the function" {
        Get-Command Install-Python | Should -Not -BeNullOrEmpty
    }

    It "Should use PythonInstallVersion from Versions.ps1" {
        $script:PythonInstallVersion | Should -Be "3.12"
    }
}

Describe "Install-Pwsh" {
    It "Should define the function" {
        Get-Command Install-Pwsh | Should -Not -BeNullOrEmpty
    }

    It "Should use PwshInstallVersion from Versions.ps1" {
        $script:PwshInstallVersion | Should -Be "7.4.7"
    }
}

Describe "Install-Node" {
    It "Should define the function" {
        Get-Command Install-Node | Should -Not -BeNullOrEmpty
    }

    It "Should use NodeVersion from Versions.ps1" {
        $script:NodeVersion | Should -Be "v25.8.1"
    }
}

Describe "Install-OpenCode" {
    It "Should define the function" {
        Get-Command Install-OpenCode | Should -Not -BeNullOrEmpty
    }
}

Describe "_Select-ObscuraAsset" {
    It "Should define the function" {
        Get-Command _Select-ObscuraAsset | Should -Not -BeNullOrEmpty
    }

    It "Should select asset matching pattern" {
        # Create mock release object
        $mockRelease = @{
            assets = @(
                @{ name = "obscura-x86_64-linux.tar.gz"; browser_download_url = "https://example.com/linux.tar.gz" }
                @{ name = "obscura-x86_64-windows.zip"; browser_download_url = "https://example.com/windows.zip" }
                @{ name = "obscura-aarch64-macos.tar.gz"; browser_download_url = "https://example.com/macos.tar.gz" }
            )
        }

        $result = _Select-ObscuraAsset -Release $mockRelease -AssetPattern "obscura-x86_64-windows\.zip"

        $result | Should -Not -BeNullOrEmpty
        $result.name | Should -Be "obscura-x86_64-windows.zip"
        $result.browser_download_url | Should -Be "https://example.com/windows.zip"
    }

    It "Should return null when no asset matches pattern" {
        $mockRelease = @{
            assets = @(
                @{ name = "other-file.zip"; browser_download_url = "https://example.com/other.zip" }
            )
        }

        $result = _Select-ObscuraAsset -Release $mockRelease -AssetPattern "obscura-x86_64-windows\.zip"

        $result | Should -BeNullOrEmpty
    }
}

Describe "Get-ObscuraVersionSafe" {
    It "Should define the function" {
        Get-Command Get-ObscuraVersionSafe | Should -Not -BeNullOrEmpty
    }

    It "Should return empty string for non-existent path" {
        $result = Get-ObscuraVersionSafe -Path "C:\nonexistent\obscura.exe"
        $result | Should -Be ""
    }

    It "Should not throw for a fake/non-executable file" {
        $fakePath = Join-Path $TestDrive "fake-obscura.exe"
        [System.IO.File]::WriteAllText($fakePath, "not a real exe")

        { Get-ObscuraVersionSafe -Path $fakePath } | Should -Not -Throw
    }

    It "Should return 'installed' fallback for non-executable file" {
        $fakePath = Join-Path $TestDrive "fake-obscura2.exe"
        [System.IO.File]::WriteAllText($fakePath, "not a real exe")

        $result = Get-ObscuraVersionSafe -Path $fakePath
        $result | Should -Be "installed"
    }
}

Describe "Install-Obscura" {
    It "Should define the function" {
        Get-Command Install-Obscura | Should -Not -BeNullOrEmpty
    }

    It "Should have CmdletBinding" {
        $cmd = Get-Command Install-Obscura
        $cmd.CmdletBinding | Should -Be $true
    }

    It "Should not set OBSCURA_ARGS by default" {
        # Verify the function does not set OBSCURA_ARGS
        $funcDef = Get-Command Install-Obscura
        $funcDef.Definition | Should -Not -Match '\$env:OBSCURA_ARGS\s*='
    }

    It "Should use unique temp directory with GUID" {
        $funcDef = Get-Command Install-Obscura
        $funcDef.Definition | Should -Match 'ostwin-obscura-.*New-Guid'
    }

    It "Should not use fixed obscura-windows.zip temp path" {
        $funcDef = Get-Command Install-Obscura
        $funcDef.Definition | Should -Not -Match 'obscura-windows\.zip'
    }

    It "Should cleanup temp directory in finally block" {
        $funcDef = Get-Command Install-Obscura
        $funcDef.Definition | Should -Match 'finally\s*\{'
        $funcDef.Definition | Should -Match 'Remove-Item.*\$tempDir'
    }
}

