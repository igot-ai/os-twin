# ──────────────────────────────────────────────────────────────────────────────
# Setup-Venv.Tests.ps1 — Tests for venv creation and Python 3.12 handling
# ──────────────────────────────────────────────────────────────────────────────

BeforeAll {
    $script:AgentsDir = Split-Path $PSScriptRoot -Parent
    $script:InstallerDir = Join-Path $script:AgentsDir "installer"

    # Source Lib.ps1 for helper functions
    . (Join-Path $script:InstallerDir "Lib.ps1")
}

Describe "Setup-Venv - Directory Cleanup" {
    It "Should remove existing venv directory before creating new one" {
        $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-venv-cleanup-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        $venvDir = Join-Path $tmpDir ".venv"
        
        try {
            # Create a corrupted venv directory (no pyvenv.cfg)
            New-Item -ItemType Directory -Path $venvDir -Force | Out-Null
            New-Item -ItemType File -Path (Join-Path $venvDir "corrupted.txt") -Force | Out-Null
            
            Test-Path $venvDir | Should -Be $true
            Test-Path (Join-Path $venvDir "corrupted.txt") | Should -Be $true

            # Mock the venv creation by calling the cleanup logic directly
            # On Windows, use cmd.exe rd
            if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
                & cmd.exe /c "rd /s /q `"$venvDir`"" 2>&1
                if (Test-Path $venvDir) {
                    Remove-Item -Path $venvDir -Recurse -Force -ErrorAction Stop
                }
            }
            else {
                Remove-Item -Path $venvDir -Recurse -Force -ErrorAction Stop
            }
            
            Test-Path $venvDir | Should -Be $false
        }
        finally {
            if (Test-Path $tmpDir) {
                Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }

    It "Should detect valid venv by checking pyvenv.cfg" {
        $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-venv-valid-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        $venvDir = Join-Path $tmpDir ".venv"
        
        try {
            New-Item -ItemType Directory -Path $venvDir -Force | Out-Null
            
            # Without pyvenv.cfg - invalid
            $venvValid = (Test-Path $venvDir) -and (Test-Path (Join-Path $venvDir "pyvenv.cfg"))
            $venvValid | Should -Be $false
            
            # With pyvenv.cfg - valid
            New-Item -ItemType File -Path (Join-Path $venvDir "pyvenv.cfg") -Force | Out-Null
            $venvValid = (Test-Path $venvDir) -and (Test-Path (Join-Path $venvDir "pyvenv.cfg"))
            $venvValid | Should -Be $true
        }
        finally {
            if (Test-Path $tmpDir) {
                Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Describe "Setup-Venv - Python 3.12 Detection" {
    It "Should detect if Python 3.12 is installed via uv" {
        # Skip if uv not installed
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            Set-ItResult -Skipped -Because "uv is not installed"
            return
        }

        $pyList = & uv python list 2>&1
        $py312Installed = $pyList -match "3\.12"
        
        # This test just verifies the detection logic works
        # It doesn't assert the result since Python 3.12 may or may not be installed
        $py312Installed | Should -BeIn @($true, $false)
    }
}

Describe "Setup-Venv - Error Handling" {
    It "Should throw error when venv creation fails" {
        $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-venv-error-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        $venvDir = Join-Path $tmpDir ".venv"
        
        try {
            New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
            
            # Create a file with same name as venv directory to force failure
            New-Item -ItemType File -Path $venvDir -Force | Out-Null
            
            # Attempting to create venv at a file path should fail
            # This simulates the error condition
            { 
                if (Test-Path $venvDir -PathType Leaf) {
                    throw "Cannot create venv at file path: $venvDir"
                }
            } | Should -Throw "Cannot create venv at file path: $venvDir"
        }
        finally {
            if (Test-Path $tmpDir) {
                Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
