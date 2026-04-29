# ChannelCLI.Tests.ps1
# Tests the 'ostwin channel' CLI dispatch and help text.
# Updated for pure-PowerShell ostwin CLI (zero-bash migration).

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"
}

Describe "ostwin channel help and usage" {
    It "shows channel usage on unknown subcommand" {
        $raw = pwsh -NoProfile -File $script:ostwin channel unknown-sub 2>&1
        $result = ($raw | Out-String)
        $LASTEXITCODE | Should -Be 2
        $result | Should -Match "usage: ostwin channel"
    }

    It "shows channel in main help text" {
        $result = pwsh -NoProfile -File $script:ostwin --help 2>&1
        $result = $result -join "`n"
        $result | Should -Match "channel"
    }

    It "does NOT show 'bot' as a separate command in help text" {
        $result = pwsh -NoProfile -File $script:ostwin --help 2>&1
        $result = $result -join "`n"
        $result | Should -Not -Match "^\s+bot\s+Manage"
    }

    It "shows help with --help flag" {
        $result = pwsh -NoProfile -File $script:ostwin channel --help 2>&1
        $joined = ($result | Out-String)
        $LASTEXITCODE | Should -Be 0
        $joined | Should -Match "list"
        $joined | Should -Match "connect"
        $joined | Should -Match "disconnect"
        $joined | Should -Match "test"
        $joined | Should -Match "pair"
    }
}

Describe "ostwin channel subcommands" {
    It "list subcommand exists" {
        $result = pwsh -NoProfile -File $script:ostwin channel list --help 2>&1
        $joined = ($result | Out-String)
        $joined | Should -Match "list"
    }
}

Describe "ostwin bot/discord are removed" {
    It "'ostwin bot' is an unknown command" {
        $result = pwsh -NoProfile -File $script:ostwin bot status 2>&1
        $LASTEXITCODE | Should -Be 1
        $result = ($result | Out-String)
        $result | Should -Match "Unknown command"
    }

    It "'ostwin discord' is an unknown command" {
        $result = pwsh -NoProfile -File $script:ostwin discord status 2>&1
        $LASTEXITCODE | Should -Be 1
        $result = ($result | Out-String)
        $result | Should -Match "Unknown command"
    }
}
