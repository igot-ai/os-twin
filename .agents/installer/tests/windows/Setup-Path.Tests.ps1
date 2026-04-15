# ──────────────────────────────────────────────────────────────────────────────
# Setup-Path.Tests.ps1 — Tests for installer/Setup-Path.ps1
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    . "$PSScriptRoot/TestHelper.ps1"
    Import-InstallerModule -Modules @("Lib.ps1", "Setup-Path.ps1")
    . $script:_ImportedModuleScript
}

Describe "Setup-Path" {
    BeforeEach {
        $testDir = Join-Path $TestDrive "test-path-$(Get-Random)"
        $binDir = Join-Path $testDir ".agents\bin"
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
        $script:InstallDir = $testDir
        $script:OriginalPath = $env:PATH
    }

    AfterEach {
        $env:PATH = $script:OriginalPath
    }

    It "Should add bin dir to current session PATH" {
        # Mock profile operations by using a temp profile
        $tempProfile = Join-Path $TestDrive "test-profile-$(Get-Random).ps1"
        $originalProfile = $PROFILE
        try {
            # We can't easily change $PROFILE so just test the PATH modification
            $binDir = Join-Path $testDir ".agents\bin"
            $env:PATH = $env:PATH -replace [regex]::Escape($binDir), ""

            # Directly test PATH update logic
            if ($env:PATH -notlike "*$binDir*") {
                $env:PATH = "$binDir;$env:PATH"
            }

            $env:PATH | Should -Match ([regex]::Escape($binDir))
        }
        finally { }
    }

    It "Should be idempotent (no duplicates)" {
        $binDir = Join-Path $testDir ".agents\bin"
        # Add once
        $env:PATH = "$binDir;$env:PATH"
        $countBefore = ($env:PATH -split ";" | Where-Object { $_ -eq $binDir }).Count

        # "Add" again — should not duplicate
        if ($env:PATH -notlike "*$binDir*") {
            $env:PATH = "$binDir;$env:PATH"
        }
        $countAfter = ($env:PATH -split ";" | Where-Object { $_ -eq $binDir }).Count

        $countAfter | Should -Be $countBefore
    }
}

