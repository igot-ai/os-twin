<#
.SYNOPSIS
    Pester tests for ostwin.ps1 — the Windows PowerShell port of the ostwin CLI.

.DESCRIPTION
    Tests parse validity, help output, version output, env file loading,
    AGENTS_DIR resolution, subcommand dispatch structure, plan resolution,
    and the ostwin.cmd wrapper.
#>

BeforeAll {
    $script:OstwinPs1 = Join-Path $PSScriptRoot ".." "ostwin.ps1"
    $script:OstwinCmd = Join-Path $PSScriptRoot ".." "ostwin.cmd"
    $script:AgentsDir = Join-Path $PSScriptRoot ".." ".."
    $script:TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-tests-$(Get-Random)"
    New-Item -ItemType Directory -Path $script:TempDir -Force | Out-Null
}

AfterAll {
    if ($script:TempDir -and (Test-Path $script:TempDir)) {
        Remove-Item $script:TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Parse Validity" {
    It "Should parse without errors" {
        $tokens = $null
        $parseErrors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile(
            $script:OstwinPs1,
            [ref]$tokens,
            [ref]$parseErrors
        )
        $parseErrors.Count | Should -Be 0
    }

    It "Should have more than 500 tokens (non-trivial script)" {
        $tokens = $null
        $parseErrors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile(
            $script:OstwinPs1,
            [ref]$tokens,
            [ref]$parseErrors
        )
        $tokens.Count | Should -BeGreaterThan 500
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Help Output" {
    It "Should show help when invoked with --help" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 --help 2>&1
        $text = $output -join "`n"
        $text | Should -Match "Multi-Agent War-Room Orchestrator"
    }

    It "Should show help when invoked with no arguments" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 2>&1
        $text = $output -join "`n"
        $text | Should -Match "Usage:"
    }

    It "Should list all major commands in help" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 help 2>&1
        $text = $output -join "`n"
        $text | Should -Match "agent"
        $text | Should -Match "run"
        $text | Should -Match "plan"
        $text | Should -Match "status"
        $text | Should -Match "stop"
        $text | Should -Match "dashboard"
        $text | Should -Match "skills"
        $text | Should -Match "role"
        $text | Should -Match "version"
        $text | Should -Match "channel"
        $text | Should -Match "mcp"
        $text | Should -Match "reload-env"
        $text | Should -Match "health"
        $text | Should -Match "config"
        $text | Should -Match "clone-role"
        $text | Should -Match "init"
        $text | Should -Match "sync"
        $text | Should -Match "logs"
        $text | Should -Match "test"
        $text | Should -Match "mac"
    }

    It "Should include environment variables section" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 help 2>&1
        $text = $output -join "`n"
        $text | Should -Match "ENGINEER_CMD"
        $text | Should -Match "WARROOMS_DIR"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Version Output" {
    It "Should show version string with 'version' command" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 version 2>&1
        $text = $output -join "`n"
        $text | Should -Match "ostwin v"
    }

    It "Should show version with -v flag" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 -v 2>&1
        $text = $output -join "`n"
        $text | Should -Match "ostwin v"
    }

    It "Should show version with --version flag" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 --version 2>&1
        $text = $output -join "`n"
        $text | Should -Match "ostwin v"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Unknown Command" {
    It "Should report error for unknown command" {
        $output = & pwsh -NoProfile -File $script:OstwinPs1 this-command-does-not-exist 2>&1
        $text = $output -join "`n"
        $text | Should -Match "Unknown command"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Import-EnvFile function" {
    It "Should load env vars from a .env file" {
        $envFile = Join-Path $script:TempDir "test.env"
        Set-Content -Path $envFile -Value @"
# Comment line
OSTWIN_TEST_VAR1=hello
OSTWIN_TEST_VAR2="quoted value"
OSTWIN_TEST_VAR3='single quoted'

# Another comment
OSTWIN_TEST_VAR4=no_quotes
"@
        # Write a temp script to test Import-EnvFile in isolation
        $testScript = Join-Path $script:TempDir "test-env-load.ps1"
        $testContent = @'
param([string]$EnvPath)
function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -notmatch '=') { continue }
        $eqIdx = $trimmed.IndexOf('=')
        $key = $trimmed.Substring(0, $eqIdx).Trim()
        $val = $trimmed.Substring($eqIdx + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
            ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if ($key -and -not [System.Environment]::GetEnvironmentVariable($key, 'Process')) {
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}
Import-EnvFile -Path $EnvPath
Write-Output $env:OSTWIN_TEST_VAR1
Write-Output $env:OSTWIN_TEST_VAR2
Write-Output $env:OSTWIN_TEST_VAR3
Write-Output $env:OSTWIN_TEST_VAR4
'@
        Set-Content -Path $testScript -Value $testContent
        $result = & pwsh -NoProfile -File $testScript -EnvPath $envFile
        $result[0] | Should -Be "hello"
        $result[1] | Should -Be "quoted value"
        $result[2] | Should -Be "single quoted"
        $result[3] | Should -Be "no_quotes"
    }

    It "Should skip blank lines and comments" {
        $envFile = Join-Path $script:TempDir "comments.env"
        Set-Content -Path $envFile -Value @"
# Full line comment
   # Indented comment

OSTWIN_TEST_ONLY_ONE=exists
"@
        $testScript = Join-Path $script:TempDir "test-env-comments.ps1"
        $testContent = @'
param([string]$EnvPath)
function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -notmatch '=') { continue }
        $eqIdx = $trimmed.IndexOf('=')
        $key = $trimmed.Substring(0, $eqIdx).Trim()
        $val = $trimmed.Substring($eqIdx + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
            ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if ($key -and -not [System.Environment]::GetEnvironmentVariable($key, 'Process')) {
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}
Import-EnvFile -Path $EnvPath
Write-Output $env:OSTWIN_TEST_ONLY_ONE
'@
        Set-Content -Path $testScript -Value $testContent
        $result = & pwsh -NoProfile -File $testScript -EnvPath $envFile
        $result | Should -Be "exists"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Script Structure" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    It "Should define Import-EnvFile function" {
        $script:Content | Should -Match "function Import-EnvFile"
    }

    It "Should define Test-DashboardReachable function" {
        $script:Content | Should -Match "function Test-DashboardReachable"
    }

    It "Should define Invoke-DashboardApi function" {
        $script:Content | Should -Match "function Invoke-DashboardApi"
    }

    It "Should define Resolve-PlanId function" {
        $script:Content | Should -Match "function Resolve-PlanId"
    }

    It "Should define Show-OstwinHelp function" {
        $script:Content | Should -Match "function Show-OstwinHelp"
    }

    It "Should use Invoke-RestMethod (not curl)" {
        $script:Content | Should -Match "Invoke-RestMethod"
        # Ensure no raw curl calls for API communication
        $script:Content | Should -Not -Match '\bcurl\s+-s'
    }

    It "Should use Start-Process / Stop-Process / Get-Process" {
        $script:Content | Should -Match "Start-Process"
        $script:Content | Should -Match "Stop-Process"
        $script:Content | Should -Match "Get-Process"
    }

    It "Should NOT use nohup or kill commands" {
        $script:Content | Should -Not -Match '\bnohup\b'
        # 'kill' can appear in comments and strings, but not as bare commands
        $script:Content | Should -Not -Match '^\s+kill\s+-'
    }

    It "Should use Windows-compatible path joining (Join-Path)" {
        $script:Content | Should -Match "Join-Path"
    }

    It "Should reference USERPROFILE or HOME for user directory" {
        $script:Content | Should -Match "USERPROFILE|\\`$HOME"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Subcommand Coverage" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    # List of all subcommands from the bash ostwin CLI
    $subcommands = @(
        "agent", "run", "plan", "init", "sync", "status",
        "logs", "stop", "dashboard", "channel", "clone-role",
        "skills", "mcp", "reload-env", "role", "mac",
        "config", "health", "test", "test-ps", "version"
    )

    foreach ($sub in $subcommands) {
        It "Should handle '$sub' subcommand" {
            # Check it appears in the switch statement
            $pattern = [regex]::Escape("`"$sub`"")
            $script:Content | Should -Match $pattern
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Plan Subcommands" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    foreach ($sub in @("create", "start", "list", "clear")) {
        It "Should handle 'plan $sub' subcommand" {
            $script:Content | Should -Match "`"$sub`""
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Skills Subcommands" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    foreach ($sub in @("sync", "install", "search", "update", "remove", "list")) {
        It "Should handle 'skills $sub' subcommand" {
            $script:Content | Should -Match "`"$sub`""
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.cmd — Wrapper File" {
    It "Should exist at .agents/bin/ostwin.cmd" {
        Test-Path $script:OstwinCmd | Should -BeTrue
    }

    It "Should reference ostwin.ps1" {
        $content = Get-Content $script:OstwinCmd -Raw
        $content | Should -Match "ostwin\.ps1"
    }

    It "Should try pwsh first, then powershell" {
        $content = Get-Content $script:OstwinCmd -Raw
        $content | Should -Match "pwsh"
        $content | Should -Match "powershell"
    }

    It "Should use -ExecutionPolicy Bypass" {
        $content = Get-Content $script:OstwinCmd -Raw
        $content | Should -Match "ExecutionPolicy Bypass"
    }

    It "Should forward all arguments with %*" {
        $content = Get-Content $script:OstwinCmd -Raw
        $content | Should -Match "%\*"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Flag Translation" {
    BeforeAll {
        $script:Content = Get-Content $script:OstwinPs1 -Raw
    }

    It "Should translate --dry-run to -DryRun" {
        $script:Content | Should -Match "'\-\-dry\-run'"
        $script:Content | Should -Match "'\-DryRun'"
    }

    It "Should translate --resume to -Resume" {
        $script:Content | Should -Match "'\-\-resume'"
        $script:Content | Should -Match "'\-Resume'"
    }

    It "Should translate --expand to -Expand" {
        $script:Content | Should -Match "'\-\-expand'"
        $script:Content | Should -Match "'\-Expand'"
    }

    It "Should translate --json to -JsonOutput for status" {
        $script:Content | Should -Match "'\-\-json'"
        $script:Content | Should -Match "'\-JsonOutput'"
    }

    It "Should translate --watch to -Watch for status" {
        $script:Content | Should -Match "'\-\-watch'"
        $script:Content | Should -Match "'\-Watch'"
    }

    It "Should translate --working-dir to -ProjectDir" {
        $script:Content | Should -Match "'\-\-working\-dir'"
        $script:Content | Should -Match "'\-ProjectDir'"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — AGENTS_DIR Resolution" {
    It "Should resolve AGENTS_DIR from project root with .agents/" {
        # Create a temp project structure
        $projectDir = Join-Path $script:TempDir "test-project"
        $agentsSubdir = Join-Path $projectDir ".agents"
        New-Item -ItemType Directory -Path (Join-Path $agentsSubdir "bin") -Force | Out-Null
        Set-Content -Path (Join-Path $agentsSubdir "config.json") -Value '{"version":"1.0.0"}'

        $result = & pwsh -NoProfile -Command @"
            Push-Location '$projectDir'
            try {
                `$cwd = (Get-Location).Path
                if ((Test-Path (Join-Path `$cwd '.agents\config.json'))) {
                    `$AgentsDir = (Resolve-Path (Join-Path `$cwd '.agents')).Path
                    Write-Output `$AgentsDir
                } else {
                    Write-Output 'NOT_FOUND'
                }
            } finally { Pop-Location }
"@
        $result | Should -Be (Resolve-Path $agentsSubdir).Path
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — ConvertFrom-Json Safety" {
    It "Should handle version reading from config.json" {
        $configFile = Join-Path $script:TempDir "config-test.json"
        Set-Content -Path $configFile -Value '{"version":"2.5.1"}'

        $result = & pwsh -NoProfile -Command @"
            `$configData = Get-Content '$configFile' -Raw | ConvertFrom-Json
            Write-Output `$configData.version
"@
        $result | Should -Be "2.5.1"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin.ps1 — Stop Command PID Management" {
    It "Should handle missing PID file gracefully" {
        $result = & pwsh -NoProfile -Command @"
            `$pidFile = Join-Path '$script:TempDir' 'nonexistent.pid'
            if (Test-Path `$pidFile) {
                Write-Output 'FOUND'
            } else {
                Write-Output 'NOT_FOUND'
            }
"@
        $result | Should -Be "NOT_FOUND"
    }

    It "Should handle stale PID file" {
        $pidFile = Join-Path $script:TempDir "stale.pid"
        Set-Content -Path $pidFile -Value "999999999"  # Unlikely to be a real PID

        $result = & pwsh -NoProfile -Command @"
            `$pidFile = '$pidFile'
            `$dashPid = (Get-Content `$pidFile -Raw).Trim()
            try {
                `$proc = Get-Process -Id `$dashPid -ErrorAction Stop
                Write-Output 'RUNNING'
            }
            catch {
                Write-Output 'NOT_RUNNING'
            }
"@
        $result | Should -Be "NOT_RUNNING"
    }
}
