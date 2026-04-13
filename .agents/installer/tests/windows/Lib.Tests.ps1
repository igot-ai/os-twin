# ──────────────────────────────────────────────────────────────────────────────
# Lib.Tests.ps1 — Tests for installer/Lib.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1")
    . $script:_ImportedModuleScript
}

Describe "Write-Header" {
    It "Should not throw" {
        { Write-Header "Test Header" } | Should -Not -Throw
    }
}

Describe "Write-Ok" {
    It "Should not throw" {
        { Write-Ok "Test OK message" } | Should -Not -Throw
    }
}

Describe "Write-Warn" {
    It "Should not throw" {
        { Write-Warn "Test warning" } | Should -Not -Throw
    }
}

Describe "Write-Fail" {
    It "Should not throw" {
        { Write-Fail "Test failure" } | Should -Not -Throw
    }
}

Describe "Write-Info" {
    It "Should not throw" {
        { Write-Info "Test info" } | Should -Not -Throw
    }
}

Describe "Write-Step" {
    It "Should not throw" {
        { Write-Step "Test step" } | Should -Not -Throw
    }
}

Describe "Ask-User" {
    Context "When AutoYes is true" {
        It "Should return true without prompting" {
            $script:AutoYes = $true
            $result = Ask-User "Test prompt"
            $result | Should -Be $true
        }
    }
}

Describe "Compare-VersionGte" {
    It "Should return true when current >= minimum (same version)" {
        Compare-VersionGte -Current "3.12" -Minimum "3.12" | Should -Be $true
    }

    It "Should return true when current > minimum (major)" {
        Compare-VersionGte -Current "4.0" -Minimum "3.12" | Should -Be $true
    }

    It "Should return true when current > minimum (minor)" {
        Compare-VersionGte -Current "3.13" -Minimum "3.12" | Should -Be $true
    }

    It "Should return false when current < minimum" {
        Compare-VersionGte -Current "3.9" -Minimum "3.10" | Should -Be $false
    }

    It "Should handle 'v' prefix gracefully" {
        Compare-VersionGte -Current "v3.12" -Minimum "3.10" | Should -Be $true
    }

    It "Should handle three-part versions" {
        Compare-VersionGte -Current "7.4.7" -Minimum "7.0.0" | Should -Be $true
    }

    It "Should handle exact three-part versions" {
        Compare-VersionGte -Current "7.4.7" -Minimum "7.4.7" | Should -Be $true
    }

    It "Should return false for older three-part version" {
        Compare-VersionGte -Current "7.3.9" -Minimum "7.4.0" | Should -Be $false
    }
}

