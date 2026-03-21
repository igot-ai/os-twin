# SubcommandCLI.Tests.ps1
# Tests the 'ostwin role' CLI dispatch and discovery.

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"
    $script:testHome = Join-Path $TestDrive "home"
    $script:testProject = Join-Path $TestDrive "project"
    
    # Mock AGENTS_DIR/roles/
    $script:mockAgentsRoles = Join-Path $TestDrive "agents/roles"
    New-Item -ItemType Directory -Path $script:mockAgentsRoles -Force | Out-Null
    
    # Mock reporter in AGENTS_DIR
    $reporterDir = New-Item -ItemType Directory -Path (Join-Path $script:mockAgentsRoles "reporter") -Force
    $reporterSubcommands = @{
        role = "reporter"
        language = "python"
        subcommands = @{
            "generate" = @{ invoke = "python -m reporter generate {args}"; description = "Generate report" }
            "list-components" = @{ invoke = "python -m reporter list-components {args}"; description = "List components" }
        }
    }
    $reporterSubcommands | ConvertTo-Json -Depth 5 | Out-File (Join-Path $reporterDir "subcommands.json")
    
    # Mock designer in AGENTS_DIR (no manifest)
    $designerDir = New-Item -ItemType Directory -Path (Join-Path $script:mockAgentsRoles "designer") -Force
    @{ name = "designer" } | ConvertTo-Json | Out-File (Join-Path $designerDir "role.json")

    # Mock HOME/.ostwin/roles/
    $script:mockHomeRoles = Join-Path $script:testHome ".ostwin/roles"
    New-Item -ItemType Directory -Path $script:mockHomeRoles -Force | Out-Null
    
    # Mock user-role in HOME
    $userRoleDir = New-Item -ItemType Directory -Path (Join-Path $script:mockHomeRoles "user-role") -Force
    @{ role = "user-role"; subcommands = @{ "test" = @{ invoke = "echo test"; description = "User test" } } } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $userRoleDir "subcommands.json")
}

Describe "ostwin role discovery" {
    BeforeEach {
        $env:AGENTS_DIR = $script:agentsDir # We need the real one for the script to find its helpers, but we'll override the roles lookup if we can
        # Wait, the script hardcodes some paths or uses AGENTS_DIR. 
        # I'll need to be careful.
    }

    It "lists all discoverable roles" {
        # We need to point the script to our mock directories.
        # Since the script uses AGENTS_DIR/roles, HOME/.ostwin/roles and $(pwd)/.ostwin/roles,
        # we can't easily override them without changing the script or env vars.
        # Let's try overriding AGENTS_DIR and HOME.
        
        $env:HOME = $script:testHome
        # We can't easily override AGENTS_DIR because it's used to find python, etc.
        # But we can override the roles search path if we modify the script to use an env var for roles dir.
        # Looking at ostwin script, it uses $AGENTS_DIR/roles.
        
        # For testing, I'll create a temporary AGENTS_DIR that links back to the real one's bin and lib
        # but has its own roles directory.
        $tempAgentsDir = Join-Path $TestDrive "temp-agents"
        New-Item -ItemType Directory -Path $tempAgentsDir -Force | Out-Null
        Copy-Item -Path (Join-Path $script:agentsDir "bin") -Destination $tempAgentsDir -Recurse
        Copy-Item -Path (Join-Path $script:agentsDir "config.json") -Destination $tempAgentsDir
        # Create roles symlink or copy
        New-Item -ItemType Directory -Path (Join-Path $tempAgentsDir "roles") -Force | Out-Null
        Copy-Item -Path "$script:mockAgentsRoles\*" -Destination (Join-Path $tempAgentsDir "roles") -Recurse

        $env:AGENTS_DIR = $tempAgentsDir
        $env:HOME = $script:testHome
        
        $output = bash $script:ostwin role
        $output | Should -Match "reporter"
        $output | Should -Match "designer"
        $output | Should -Match "user-role"
        $output | Should -Match "2 subcommands"
    }

    It "shows single role info with subcommands" {
        $output = bash $script:ostwin role reporter
        $output | Should -Match "Role: reporter"
        $output | Should -Match "generate"
        $output | Should -Match "List components"
    }

    It "shows info for role without subcommands.json" {
        $output = bash $script:ostwin role designer
        $output | Should -Match "Role: designer"
        $output | Should -Match "no subcommands defined"
    }
}

Describe "ostwin role dispatch" {
    It "dispatches correctly by substituting {args}" {
        # We'll use a mock script that just echoes its arguments
        $mockScript = Join-Path $TestDrive "mock-script.sh"
        "#!/bin/bash`necho CMD: \$*`n" | Out-File $mockScript
        chmod +x $mockScript
        
        # Update reporter manifest to use mock script
        $reporterDir = Join-Path $env:AGENTS_DIR "roles/reporter"
        $reporterSubcommands = @{
            role = "reporter"
            subcommands = @{
                "test-cmd" = @{ invoke = "bash $mockScript {args}"; description = "Test" }
            }
        }
        $reporterSubcommands | ConvertTo-Json -Depth 5 | Out-File (Join-Path $reporterDir "subcommands.json")
        
        $output = bash $script:ostwin role reporter test-cmd --foo bar
        $output | Should -Match "CMD: --foo bar"
    }

    It "handles missing {args} by appending" {
        $mockScript = Join-Path $TestDrive "mock-script-append.sh"
        "#!/bin/bash`necho CMD: \$*`n" | Out-File $mockScript
        chmod +x $mockScript
        
        $reporterDir = Join-Path $env:AGENTS_DIR "roles/reporter"
        $reporterSubcommands = @{
            role = "reporter"
            subcommands = @{
                "test-append" = @{ invoke = "bash $mockScript"; description = "Test" }
            }
        }
        $reporterSubcommands | ConvertTo-Json -Depth 5 | Out-File (Join-Path $reporterDir "subcommands.json")
        
        $output = bash $script:ostwin role reporter test-append --foo bar
        $output | Should -Match "CMD: --foo bar"
    }
}

Describe "ostwin role priority" {
    It "gives project-local override priority" {
        $projectDir = New-Item -ItemType Directory -Path $script:testProject -Force
        $projectRolesDir = New-Item -ItemType Directory -Path (Join-Path $projectDir ".ostwin/roles") -Force
        $localReporterDir = New-Item -ItemType Directory -Path (Join-Path $projectRolesDir "reporter") -Force
        
        @{ role = "reporter"; subcommands = @{ "local" = @{ invoke = "echo local"; description = "Local" } } } | ConvertTo-Json -Depth 5 | Out-File (Join-Path $localReporterDir "subcommands.json")
        
        Push-Location $projectDir
        try {
            $output = bash $script:ostwin role reporter
            $output | Should -Match "local"
            $output | Should -Not -Match "generate"
            $output | Should -Match "Path: $localReporterDir"
        }
        finally {
            Pop-Location
        }
    }
}

Describe "ostwin role errors" {
    It "exits 1 for unknown role" {
        $result = bash $script:ostwin role non-existent 2>&1
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "Role 'non-existent' not found"
    }

    It "exits 1 for unknown subcommand" {
        $result = bash $script:ostwin role reporter unknown-sub 2>&1
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "Unknown subcommand 'unknown-sub' for role 'reporter'"
    }
}
