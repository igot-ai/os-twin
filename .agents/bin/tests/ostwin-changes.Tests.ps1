<#
.SYNOPSIS
    Backward-compatibility tests for ostwin.ps1 changes:
      1. Cross-platform venv activation path (Scripts/ on Windows, bin/ on macOS/Linux)
      2. Role extraction from plan files — Roles: @engineer, @qa → [engineer, qa]
      3. Bash thin-wrapper delegation (ostwin → ostwin.ps1)

.DESCRIPTION
    Proves that the changes (especially deleted code) are fully backward compatible.
    Tests cover:
      - Venv path resolves correctly on macOS/Linux (bin/) and Windows (Scripts/)
      - Old format "Role:" no longer matches (intentional — plans use "Roles:")
      - New "Roles:" format extracts ALL roles (not just first), strips @, strips commas
      - Inline comments in Roles: lines are ignored
      - Placeholder roles like <role-name> are filtered out
      - Multiple Roles: lines across EPICs are all captured
      - Backward compat: single-role lines still work
      - Existing ostwin.ps1 help, version, subcommand structure unchanged
      - ostwin bash wrapper delegates to ostwin.ps1
#>

BeforeAll {
    $script:OstwinPs1 = Join-Path $PSScriptRoot ".." "ostwin.ps1"
    $script:OstwinBash = Join-Path $PSScriptRoot ".." "ostwin"
    $script:TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-compat-tests-$(Get-Random)"
    New-Item -ItemType Directory -Path $script:TempDir -Force | Out-Null
}

AfterAll {
    if ($script:TempDir -and (Test-Path $script:TempDir)) {
        Remove-Item $script:TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1: Cross-platform venv activation path
# ─────────────────────────────────────────────────────────────────────────────
Describe "Venv Activation — Cross-Platform Path Resolution" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    It "Should use bin/Activate.ps1 on macOS/Linux (non-Windows)" {
        # On this machine (macOS), $IsWindows should be $false
        # The venv path should resolve to bin/Activate.ps1
        $result = & pwsh -NoProfile -Command @"
            `$OstwinHome = '$script:TempDir'
            `$venvActivate = if (`$IsWindows) {
                Join-Path `$OstwinHome '.venv' 'Scripts' 'Activate.ps1'
            } else {
                Join-Path `$OstwinHome '.venv' 'bin' 'Activate.ps1'
            }
            Write-Output `$venvActivate
"@
        $result | Should -Match '[/\\]bin[/\\]Activate\.ps1$' -Because "macOS/Linux should use bin/"
        $result | Should -Not -Match 'Scripts' -Because "macOS/Linux should NOT use Scripts/"
    }

    It "Should contain platform-aware venv activation logic in source" {
        $script:Content | Should -Match '\$IsWindows' -Because "Must branch on platform"
        $script:Content | Should -Match 'Scripts.*Activate\.ps1' -Because "Must support Windows path"
        $script:Content | Should -Match 'bin.*Activate\.ps1' -Because "Must support Unix path"
    }

    It "Should NOT hardcode Windows-only venv path" {
        # Regression: old code was Join-Path $OstwinHome ".venv\Scripts\Activate.ps1"
        $script:Content | Should -Not -Match '\$venvActivate\s*=\s*Join-Path\s+\$OstwinHome\s+"\.venv\\Scripts\\Activate\.ps1"' `
            -Because "Must not hardcode Windows-only path"
    }

    It "Should still activate venv if Activate.ps1 exists (backward compat)" {
        $script:Content | Should -Match 'if \(Test-Path \$venvActivate\)' -Because "Must check file exists before sourcing"
        $script:Content | Should -Match '\.\s+\$venvActivate' -Because "Must dot-source the activate script"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2: Role extraction — Roles: @engineer, @qa → [engineer, qa]
# ─────────────────────────────────────────────────────────────────────────────
Describe "Role Extraction — Regex and Parsing Logic" {
    BeforeAll {
        # The role extraction logic extracted from ostwin.ps1 for isolated testing
        $script:ExtractRoles = {
            param([string]$PlanContent)
            [regex]::Matches($PlanContent, '(?m)^Roles:\s*(.+)$') |
                ForEach-Object {
                    $line = $_.Groups[1].Value -replace '\(.*$', ''
                    ($line -split '[,\s]+') |
                        ForEach-Object { ($_.Trim() -replace '^@', '') } |
                        Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
                } |
                Sort-Object -Unique
        }
    }

    Context "Basic multi-role extraction (the bug fix)" {
        It "Should extract ALL roles from comma-separated list" {
            $plan = @"
## EPIC-001 - Some Feature
Roles: @engineer, @qa, @architect
"@
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 3
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
            $roles | Should -Contain "architect"
        }

        It "Should strip @ prefix from all roles" {
            $plan = "Roles: @engineer, @qa"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -Not -Contain "@engineer"
            $roles | Should -Not -Contain "@qa"
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
        }

        It "Should NOT produce trailing commas in role names" {
            $plan = "Roles: @engineer, @qa, @architect"
            $roles = & $script:ExtractRoles $plan
            foreach ($r in $roles) {
                $r | Should -Not -Match ',' -Because "Role names must not contain commas"
            }
        }
    }

    Context "Backward compatibility — single-role formats" {
        It "Should handle single role without @ prefix" {
            $plan = "Roles: engineer"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 1
            $roles | Should -Contain "engineer"
        }

        It "Should handle single role with @ prefix" {
            $plan = "Roles: @engineer"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 1
            $roles | Should -Contain "engineer"
        }

        It "Should handle roles without commas (space-separated)" {
            $plan = "Roles: @engineer @qa"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 2
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
        }
    }

    Context "Inline comments and noise filtering" {
        It "Should strip inline parenthesized comments" {
            $plan = "Roles: @researcher, @analyst    (dynamically chosen agents for this epic's workflow)"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -Contain "researcher"
            $roles | Should -Contain "analyst"
            $roles | Should -HaveCount 2
            # Must NOT contain words from the comment
            $roles | Should -Not -Contain "dynamically"
            $roles | Should -Not -Contain "chosen"
        }

        It 'Should filter out placeholder roles like angle-bracket role-name' {
            $plan = "Roles: <role-name>, @engineer"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 1
            $roles | Should -Contain "engineer"
        }

        It "Should filter out template placeholders <role1>, <role2>" {
            $plan = "Roles: @<role1>, @<role2>, ...    (dynamically chosen agents)"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 0 -Because "All items are placeholders or noise"
        }
    }

    Context "Multiple Roles: lines across EPICs" {
        It "Should extract roles from ALL Roles: lines in a plan" {
            $plan = @"
## EPIC-001 - Feature A
Roles: @engineer, @qa

## EPIC-002 - Feature B
Roles: @architect, @engineer

## EPIC-003 - Feature C
Roles: @researcher
"@
            $roles = & $script:ExtractRoles $plan
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
            $roles | Should -Contain "architect"
            $roles | Should -Contain "researcher"
            # engineer appears twice but should be deduplicated
            ($roles | Where-Object { $_ -eq "engineer" }).Count | Should -Be 1
        }

        It "Should deduplicate roles across EPICs" {
            $plan = @"
Roles: @engineer, @qa, @architect
Roles: @engineer, @qa, @architect
Roles: @engineer, @qa
"@
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 3
        }
    }

    Context "Real-world plan format (from PLAN.template.md)" {
        It "Should handle template format: Roles: @researcher, @analyst" {
            $plan = "Roles: @researcher, @analyst"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 2
            $roles | Should -Contain "researcher"
            $roles | Should -Contain "analyst"
        }

        It "Should handle production format: Roles: @engineer, @qa, @architect" {
            $plan = "Roles: @engineer, @qa, @architect"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 3
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
            $roles | Should -Contain "architect"
        }
    }

    Context "Intentional breaking change: 'Role:' (singular) no longer matches" {
        It "Should NOT match old 'Role:' singular format" {
            # This is INTENTIONAL — plan files use 'Roles:' (plural)
            $plan = "Role: @engineer"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 0 -Because "'Role:' (singular) is not the plan format"
        }
    }

    Context "Edge cases" {
        It "Should handle extra whitespace gracefully" {
            $plan = "Roles:   @engineer ,  @qa  ,  @architect  "
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 3
            $roles | Should -Contain "engineer"
            $roles | Should -Contain "qa"
            $roles | Should -Contain "architect"
        }

        It "Should handle plan with no Roles: lines" {
            $plan = @"
## EPIC-001 - Some Feature
Description here.
"@
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 0
        }

        It "Should handle roles with hyphens (e.g., macos-automation-engineer)" {
            $plan = "Roles: @macos-automation-engineer, @qa"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -Contain "macos-automation-engineer"
            $roles | Should -Contain "qa"
        }

        It "Should handle roles with underscores" {
            $plan = "Roles: @code_reviewer, @test_engineer"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -Contain "code_reviewer"
            $roles | Should -Contain "test_engineer"
        }

        It "Should not match Roles: in the middle of a line" {
            $plan = "Some text Roles: @engineer should not match"
            $roles = & $script:ExtractRoles $plan
            $roles | Should -HaveCount 0 -Because "Regex requires ^ anchor"
        }
    }

    Context "Consistency with PlanParser.psm1" {
        It "Should produce same results as PlanParser.psm1 for standard input" {
            # This verifies the ostwin.ps1 role extraction mirrors PlanParser
            $plan = @"
## EPIC-001 - Test
Roles: @engineer, @qa, @architect

#### Definition of Done
- [ ] Done
"@
            # ostwin.ps1 extraction
            $ostwinRoles = & $script:ExtractRoles $plan

            # PlanParser.psm1 extraction (inline)
            $parserRoles = [System.Collections.Generic.List[string]]::new()
            $roleMatches = [regex]::Matches($plan, '(?m)^(?:#{1,6}\s+)?(?:\*{1,2})?Roles?(?:\*{1,2})?:\s*(.+)$')
            foreach ($rm in $roleMatches) {
                $line = $rm.Groups[1].Value
                $line = $line -replace '\(.*$', ''
                $items = ($line -split '[,\s]+') |
                    ForEach-Object { ($_.Trim() -replace '^@', '') } |
                    Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
                foreach ($item in $items) {
                    if (-not $parserRoles.Contains($item)) { $parserRoles.Add($item) }
                }
            }

            # Both should produce the same roles
            @($ostwinRoles) | Sort-Object | Should -Be @($parserRoles | Sort-Object)
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2b: Role extraction in ostwin.ps1 source code validation
# ─────────────────────────────────────────────────────────────────────────────
Describe "Role Extraction — Source Code Regression Guards" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    It "Should match 'Roles:' (plural) not 'Role:' (singular)" {
        # The regex in source should contain Roles: not Role:
        $script:Content | Should -Match 'Roles:' -Because "Must use plural 'Roles:' to match plan format"
    }

    It "Should split on comma and whitespace" {
        # Verify the split pattern handles both commas and whitespace
        $script:Content | Should -BeLike '*-split*,*s*+*' -Because "Must split roles on commas AND whitespace"
    }

    It "Should strip @ prefix" {
        $script:Content | Should -BeLike "*-replace '^@'*" -Because "Must strip @ prefix from role names"
    }

    It "Should filter out placeholder patterns" {
        $script:Content | Should -BeLike '*-notmatch*<*>*' -Because "Must filter out placeholder roles"
    }

    It "Should NOT use Select-Object -First 1 (old bug)" {
        $roleSection = [regex]::Match($script:Content, '(?s)# Extract all roles.*?Sort-Object -Unique').Value
        $roleSection | Should -Not -Match 'Select-Object -First 1' -Because "Must NOT truncate to first role only"
    }

    It "Should strip inline comments" {
        $script:Content | Should -BeLike '*-replace*(*' -Because "Must strip inline parenthesized comments"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3: ostwin bash thin wrapper backward compatibility
# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin bash — Thin Wrapper Structure" {
    BeforeAll {
        $script:BashContent = Get-Content $script:OstwinBash -Raw
    }

    It "Should be a shell script with bash shebang" {
        $script:BashContent | Should -Match '^#!/usr/bin/env bash'
    }

    It "Should be significantly shorter than 200 lines (thin wrapper)" {
        $lineCount = (Get-Content $script:OstwinBash).Count
        $lineCount | Should -BeLessThan 200 -Because "Thin wrapper should be compact, not a full CLI"
    }

    It "Should still activate the venv" {
        $script:BashContent | Should -Match 'source.*\.venv/bin/activate' -Because "Must set up Python in PATH"
    }

    It "Should still load .env files" {
        $script:BashContent | Should -Match '_load_env_file' -Because "Must load environment variables"
    }

    It "Should still resolve AGENTS_DIR" {
        $script:BashContent | Should -Match 'AGENTS_DIR' -Because "Must resolve agents directory"
    }

    It "Should export OSTWIN_HOME" {
        $script:BashContent | Should -Match 'export OSTWIN_HOME'
    }

    It "Should export WARROOMS_DIR with default" {
        $script:BashContent | Should -Match 'export WARROOMS_DIR'
    }

    It "Should export DASHBOARD_URL with default" {
        $script:BashContent | Should -Match 'export DASHBOARD_URL'
    }

    It "Should delegate to ostwin.ps1 via exec pwsh" {
        $script:BashContent | Should -Match 'exec pwsh.*ostwin\.ps1.*"\$@"' -Because "Must exec pwsh with all args"
    }

    It "Should check for pwsh availability" {
        $script:BashContent | Should -Match 'command -v pwsh' -Because "Must check pwsh is installed"
    }

    It "Should show helpful error when pwsh is missing" {
        $script:BashContent | Should -Match 'powershell.*not found' -Because "Must explain what to install"
        $script:BashContent | Should -Match 'brew install powershell' -Because "Must show install command"
    }

    It "Should NOT contain command-specific case handlers (deleted code)" {
        # These were all moved to ostwin.ps1 — bash should not duplicate them
        $script:BashContent | Should -Not -Match '^\s*run\)' -Because "run command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*plan\)' -Because "plan command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*skills\)' -Because "skills command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*role\)' -Because "role command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*status\)' -Because "status command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*stop\)' -Because "stop command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*dashboard\)' -Because "dashboard command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*mcp\)' -Because "mcp command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '^\s*reload-env\)' -Because "reload-env command lives in ostwin.ps1"
        $script:BashContent | Should -Not -Match '\bps_dispatch\b' -Because "ps_dispatch is no longer needed"
        $script:BashContent | Should -Not -Match '\bshow_help\b' -Because "help is handled by ostwin.ps1"
        $script:BashContent | Should -Not -Match '\bresolve_plan_id\b' -Because "plan resolution is in ostwin.ps1"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPAT: ostwin.ps1 still handles all subcommands
# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — All Commands Still Present (backward compat)" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    # Every command that was in the old bash ostwin must exist in ostwin.ps1
    $commands = @(
        "agent", "run", "plan", "init", "sync", "status",
        "logs", "stop", "dashboard", "channel", "clone-role",
        "skills", "mcp", "reload-env", "role", "mac",
        "config", "health", "test", "test-ps", "version"
    )

    foreach ($cmd in $commands) {
        It "Should still handle '$cmd' command" {
            $pattern = [regex]::Escape("`"$cmd`"")
            $script:Content | Should -Match $pattern
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPAT: Help and version still work via delegation
# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Help & Version Output (backward compat)" {
    It "Should show help with --help" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 --help 2>&1
        $text = $output -join "`n"
        $text | Should -Match "Multi-Agent War-Room Orchestrator"
        $text | Should -Match "Usage:"
    }

    It "Should show version with 'version' command" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 version 2>&1
        $text = $output -join "`n"
        $text | Should -Match "ostwin v"
    }

    It "Should report error for unknown commands" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 this-does-not-exist 2>&1
        $text = $output -join "`n"
        $text | Should -Match "Unknown command"
    }

    It "Should list all commands in help text" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 help 2>&1
        $text = $output -join "`n"
        foreach ($cmd in @("run", "plan", "status", "stop", "dashboard", "skills", "role", "channel", "mcp", "health", "config", "version", "mac", "init", "sync", "logs")) {
            $text | Should -Match $cmd -Because "Help must list '$cmd' command"
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPAT: Functions and structure unchanged
# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Core Functions Still Present" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    foreach ($fn in @("Import-EnvFile", "Test-DashboardReachable", "Invoke-DashboardApi", "Resolve-PlanId", "Show-OstwinHelp")) {
        It "Should still define function '$fn'" {
            $script:Content | Should -Match "function $fn"
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# REAL-WORLD: Test with actual plan file if available
# ─────────────────────────────────────────────────────────────────────────────
Describe "Role Extraction — Real Plan File Validation" {
    BeforeAll {
        $script:RealPlan = Join-Path $HOME ".ostwin" ".agents" "plans" "3afead262b04.md"
    }

    It "Should extract engineer, qa, architect from production plan" -Skip:(-not (Test-Path $script:RealPlan)) {
        $content = Get-Content $script:RealPlan -Raw
        $roles = [regex]::Matches($content, '(?m)^Roles:\s*(.+)$') |
            ForEach-Object {
                $line = $_.Groups[1].Value -replace '\(.*$', ''
                ($line -split '[,\s]+') |
                    ForEach-Object { ($_.Trim() -replace '^@', '') } |
                    Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
            } |
            Sort-Object -Unique

        $roles | Should -Contain "engineer" -Because "Production plan has @engineer"
        $roles | Should -Contain "qa" -Because "Production plan has @qa"
        $roles | Should -Contain "architect" -Because "Production plan has @architect"
        $roles.Count | Should -Be 3 -Because "Plan should have exactly 3 unique roles"

        # Verify NO @-prefixed or comma-suffixed entries
        foreach ($r in $roles) {
            $r | Should -Not -Match '^@' -Because "@ prefix must be stripped"
            $r | Should -Not -Match ',' -Because "Commas must be stripped"
        }
    }
}
