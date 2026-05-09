# ──────────────────────────────────────────────────────────────────────────────
# Setup-OpenCode.Tests.ps1 — Tests for OpenCode permission patching
# ──────────────────────────────────────────────────────────────────────────────

Describe "patch_opencode_permissions.py" {
    BeforeAll {
        $script:PatchScript = Join-Path $PSScriptRoot "..\..\scripts\patch_opencode_permissions.py"
    }

    It "patches permission.read without non-ASCII console output" {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            Set-ItResult -Skipped -Because "python is not available"
            return
        }

        $configPath = Join-Path $TestDrive "opencode.json"
        @'
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "read": {
      "*.txt": "ask"
    },
    "external_directory": {
      "/tmp/*": "allow"
    }
  }
}
'@ | Set-Content -Path $configPath -Encoding UTF8

        $output = & $python.Source $script:PatchScript $configPath 2>&1

        $LASTEXITCODE | Should -Be 0
        ($output -join "`n") | Should -Match "->"

        $config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
        $config.permission.read.PSObject.Properties["*.txt"].Value | Should -Be "ask"
        $config.permission.read.PSObject.Properties["*.env"].Value | Should -Be "allow"
        $config.permission.read.PSObject.Properties["*.env.*"].Value | Should -Be "allow"
        $config.permission.external_directory.PSObject.Properties["/tmp/*"].Value | Should -Be "allow"
    }
}
