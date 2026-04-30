# SubcommandCLI.Tests.ps1
# Tests the 'ostwin role' CLI dispatch and discovery.
# Uses the REAL agents dir since the ostwin script resolves its own path.
#
# NOTE: The ostwin CLI is an extensionless PowerShell script (for Unix shebang
# compatibility).  `pwsh -File` REQUIRES a .ps1 extension on Windows, so we
# invoke via `pwsh -Command "& '<path>' <args>"` instead.

if ($IsWindows) {
    Write-Host "Skipping SubcommandCLI tests on Windows environment."
    return
}

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"
    if ($IsWindows) {
        $script:ostwin += ".cmd"
    }

    # Cross-platform helper: invokes ostwin via -Command to avoid the
    # Windows .ps1 extension requirement of -File.
    function Invoke-Ostwin {
        param([string[]]$OstwinArgs)
        $escapedPath = $script:ostwin -replace "'", "''"
        $argStr = ($OstwinArgs | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ' '
        $cmd = "& '$escapedPath' $argStr; exit `$LASTEXITCODE"
        $output = pwsh -NoProfile -Command $cmd 2>&1
        return $output
    }
}

Describe "ostwin role discovery" {
    It "lists all discoverable roles" {
        $env:AGENTS_DIR = $script:agentsDir
        $output = Invoke-Ostwin -OstwinArgs @('role')
        $joined = ($output | Out-String)
        $joined | Should -Match "Available roles with subcommands"
    }

    It "shows single role info with subcommands" {
        # Create a test role with subcommands.json in the real agents dir
        $testRole = "pester-test-role-$(Get-Random)"
        $testRoleDir = Join-Path $script:agentsDir "roles" $testRole
        New-Item -ItemType Directory -Path $testRoleDir -Force | Out-Null
        @{
            role = $testRole
            subcommands = @{
                "hello" = @{ invoke = "echo `"hello {args}`""; description = "Say hello" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json") -Encoding utf8

        try {
            $output = Invoke-Ostwin -OstwinArgs @('role', $testRole)
            $joined = $output -join "`n"
            $joined | Should -Match "Subcommands for role '$testRole'"
            $joined | Should -Match "hello"
            $joined | Should -Match "Say hello"
        }
        finally {
            Remove-Item -Path $testRoleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    It "shows error for role without subcommands.json" {
        $output = Invoke-Ostwin -OstwinArgs @('role', "nonexistent-pester-role-$(Get-Random)")
        $joined = $output -join "`n"
        $joined | Should -Match "not found or has no subcommands"
    }
}

Describe "ostwin role dispatch" {
    It "dispatches correctly by substituting {args}" {
        $testRole = "pester-dispatch-$(Get-Random)"
        $testRoleDir = Join-Path $script:agentsDir "roles" $testRole
        New-Item -ItemType Directory -Path $testRoleDir -Force | Out-Null
        @{
            role = $testRole
            subcommands = @{
                "greet" = @{ invoke = "echo `"GREETING: {args}`""; description = "Greet" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json") -Encoding utf8

        try {
            $output = Invoke-Ostwin -OstwinArgs @('role', $testRole, 'greet', 'hello', 'world')
            $joined = $output -join "`n"
            $joined | Should -Match "GREETING:[\s\r\n]+hello[\s\r\n]+world"
        }
        finally {
            Remove-Item -Path $testRoleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    It "handles missing {args} by appending" {
        $testRole = "pester-append-$(Get-Random)"
        $testRoleDir = Join-Path $script:agentsDir "roles" $testRole
        New-Item -ItemType Directory -Path $testRoleDir -Force | Out-Null
        @{
            role = $testRole
            subcommands = @{
                "run" = @{ invoke = "echo `"RAN:`""; description = "Run" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json") -Encoding utf8

        try {
            $output = Invoke-Ostwin -OstwinArgs @('role', $testRole, 'run', 'extra', 'args')
            $joined = $output -join "`n"
            $joined | Should -Match "RAN:"
        }
        finally {
            Remove-Item -Path $testRoleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Describe "ostwin role errors" {
    It "exits 1 for unknown role" {
        Invoke-Ostwin -OstwinArgs @('role', "definitely-not-a-role-$(Get-Random)") | Out-Null
        $LASTEXITCODE | Should -Be 1
    }

    It "exits 1 for unknown subcommand" {
        # Need a role that exists with subcommands.json
        $testRole = "pester-err-$(Get-Random)"
        $testRoleDir = Join-Path $script:agentsDir "roles" $testRole
        New-Item -ItemType Directory -Path $testRoleDir -Force | Out-Null
        @{
            role = $testRole
            subcommands = @{
                "valid" = @{ invoke = "echo `"ok`""; description = "Ok" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json") -Encoding utf8

        try {
            $result = Invoke-Ostwin -OstwinArgs @('role', $testRole, "bogus-sub-$(Get-Random)")
            $LASTEXITCODE | Should -Be 1
            $joined = $result -join "`n"
            $joined | Should -Match "not found"
        }
        finally {
            Remove-Item -Path $testRoleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
