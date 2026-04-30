# ChannelCLI.Tests.ps1
# Smoke tests for 'ostwin channel' dispatch.
# Uses -Command instead of -File for Windows compatibility (extensionless script).

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"

    function Invoke-Ostwin {
        param([string[]]$OstwinArgs)
        $escapedPath = $script:ostwin -replace "'", "''"
        $argStr = ($OstwinArgs | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ' '
        $cmd = "& '$escapedPath' $argStr; exit `$LASTEXITCODE"
        $output = pwsh -NoProfile -Command $cmd 2>&1
        return $output
    }
}

Describe "ostwin channel" {
    It "shows help with --help" {
        $result = (Invoke-Ostwin -OstwinArgs @('channel', '--help')) | Out-String
        $LASTEXITCODE | Should -Be 0
        $result | Should -Match "list"
        $result | Should -Match "connect"
    }

    It "rejects unknown subcommands" {
        Invoke-Ostwin -OstwinArgs @('channel', 'bogus') | Out-Null
        $LASTEXITCODE | Should -Be 2
    }

    It "appears in main help" {
        $result = (Invoke-Ostwin -OstwinArgs @('--help')) -join "`n"
        $result | Should -Match "channel"
    }

    It "bot and discord are unknown commands" {
        Invoke-Ostwin -OstwinArgs @('bot') | Out-Null
        $LASTEXITCODE | Should -Be 1
        Invoke-Ostwin -OstwinArgs @('discord') | Out-Null
        $LASTEXITCODE | Should -Be 1
    }
}
