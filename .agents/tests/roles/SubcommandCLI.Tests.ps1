# SubcommandCLI.Tests.ps1
# Tests the 'ostwin role' CLI dispatch and discovery.
# Uses the REAL agents dir since the ostwin script resolves its own path.

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"
}

Describe "ostwin role discovery" {
    It "lists all discoverable roles" {
        $env:AGENTS_DIR = $script:agentsDir
        $output = bash -c "AGENTS_DIR='$($script:agentsDir)' '$($script:ostwin)' role" 2>&1
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
                "hello" = @{ invoke = "echo hello {args}"; description = "Say hello" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json")

        try {
            $output = bash $script:ostwin role $testRole
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
        $output = bash $script:ostwin role "nonexistent-pester-role-$(Get-Random)" 2>&1
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
                "greet" = @{ invoke = "echo GREETING: {args}"; description = "Greet" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json")

        try {
            $output = bash $script:ostwin role $testRole greet hello world
            $joined = $output -join "`n"
            $joined | Should -Match "GREETING: hello world"
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
                "run" = @{ invoke = "echo RAN:"; description = "Run" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json")

        try {
            $output = bash $script:ostwin role $testRole run extra args
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
        bash $script:ostwin role "definitely-not-a-role-$(Get-Random)" 2>&1 | Out-Null
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
                "valid" = @{ invoke = "echo ok"; description = "Ok" }
            }
        } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $testRoleDir "subcommands.json")

        try {
            $result = bash $script:ostwin role $testRole "bogus-sub-$(Get-Random)" 2>&1
            $LASTEXITCODE | Should -Be 1
            $joined = $result -join "`n"
            $joined | Should -Match "not found"
        }
        finally {
            Remove-Item -Path $testRoleDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
