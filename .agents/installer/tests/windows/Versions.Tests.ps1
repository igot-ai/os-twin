# ──────────────────────────────────────────────────────────────────────────────
# Versions.Tests.ps1 — Tests for installer/Versions.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Versions.ps1")
    . $script:_ImportedModuleScript
}

Describe "Versions.ps1" {
    It "Should define MinPythonVersion" {
        $script:MinPythonVersion | Should -Not -BeNullOrEmpty
    }

    It "Should set MinPythonVersion to 3.10" {
        $script:MinPythonVersion | Should -Be "3.10"
    }

    It "Should define PythonInstallVersion" {
        $script:PythonInstallVersion | Should -Not -BeNullOrEmpty
    }

    It "Should set PythonInstallVersion to 3.12" {
        $script:PythonInstallVersion | Should -Be "3.12"
    }

    It "Should define MinPwshVersion" {
        $script:MinPwshVersion | Should -Not -BeNullOrEmpty
    }

    It "Should set MinPwshVersion to 7" {
        $script:MinPwshVersion | Should -Be "7"
    }

    It "Should define PwshInstallVersion" {
        $script:PwshInstallVersion | Should -Not -BeNullOrEmpty
    }

    It "Should set PwshInstallVersion to 7.4.7" {
        $script:PwshInstallVersion | Should -Be "7.4.7"
    }

    It "Should define NodeVersion" {
        $script:NodeVersion | Should -Not -BeNullOrEmpty
    }

    It "Should set NodeVersion to v25.8.1" {
        $script:NodeVersion | Should -Be "v25.8.1"
    }

    Context "Version constants match bash versions.conf" {
        It "MinPythonVersion should match" {
            $script:MinPythonVersion | Should -Be "3.10"
        }

        It "PythonInstallVersion should match" {
            $script:PythonInstallVersion | Should -Be "3.12"
        }

        It "MinPwshVersion should match" {
            $script:MinPwshVersion | Should -Be "7"
        }

        It "PwshInstallVersion should match" {
            $script:PwshInstallVersion | Should -Be "7.4.7"
        }

        It "NodeVersion should match" {
            $script:NodeVersion | Should -Be "v25.8.1"
        }
    }
}

