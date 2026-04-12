# ──────────────────────────────────────────────────────────────────────────────
# Detect-OS.Tests.ps1 — Tests for installer/Detect-OS.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Detect-OS.ps1")
    . $script:_ImportedModuleScript
}

Describe "Detect-WindowsOS" {
    Context "When running on Windows" {
        BeforeEach {
            # Reset state
            $script:OS = ""
            $script:ARCH = ""
            $script:WinVersion = ""
            $script:WinBuild = 0
            $script:PkgMgr = ""
            $script:DevModeEnabled = $false
        }

        It "Should detect Windows as OS" -Skip:(-not $IsWindows -and $null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue)) {
            Detect-WindowsOS
            $script:OS | Should -Be "windows"
        }

        It "Should detect architecture" -Skip:(-not $IsWindows -and $null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue)) {
            Detect-WindowsOS
            $script:ARCH | Should -BeIn @("x64", "arm64", "x86")
        }

        It "Should detect Windows version" -Skip:(-not $IsWindows -and $null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue)) {
            Detect-WindowsOS
            $script:WinVersion | Should -Match '^\d+$|^\d+\.\d+$'
        }

        It "Should set WinBuild" -Skip:(-not $IsWindows -and $null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue)) {
            Detect-WindowsOS
            $script:WinBuild | Should -BeGreaterThan 0
        }
    }

    Context "When running on non-Windows (Linux/macOS)" {
        It "Should throw on Linux" -Skip:(-not $IsLinux) {
            { Detect-WindowsOS } | Should -Throw "*not Windows*"
        }

        It "Should throw on macOS" -Skip:(-not $IsMacOS) {
            { Detect-WindowsOS } | Should -Throw "*not Windows*"
        }
    }
}

Describe "Detect-WindowsOS package manager detection" {
    Context "When winget is available" {
        It "Should detect winget" -Skip:(-not $IsWindows -and $null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue)) {
            # This test only runs on actual Windows
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                Detect-WindowsOS
                $script:PkgMgr | Should -Be "winget"
            }
            else {
                Set-ItResult -Skipped -Because "winget not installed"
            }
        }
    }
}

