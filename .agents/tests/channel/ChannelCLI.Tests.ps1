# ChannelCLI.Tests.ps1
# Tests the 'ostwin channel' CLI dispatch and help text.

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:ostwin = Join-Path $script:agentsDir "bin" "ostwin"
}

Describe "ostwin channel help and usage" {
    It "shows channel usage on unknown subcommand" {
        $raw = bash $script:ostwin channel unknown-sub 2>&1
        $result = ($raw | Where-Object { $_ -notmatch "Broken pipe" }) -join "`n"
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "Usage: ostwin channel"
        $result | Should -Match "start"
        $result | Should -Match "stop"
        $result | Should -Match "status"
        $result | Should -Match "logs"
        $result | Should -Match "deploy"
        $result | Should -Match "list"
        $result | Should -Match "connect"
        $result | Should -Match "disconnect"
        $result | Should -Match "test"
        $result | Should -Match "pair"
    }

    It "shows channel in main help text" {
        $result = bash $script:ostwin --help 2>&1
        $result = $result -join "`n"
        $result | Should -Match "channel <sub>"
        $result | Should -Match "Manage communication channels"
    }

    It "does NOT show 'bot' as a separate command in help text" {
        $result = bash $script:ostwin --help 2>&1
        $result = $result -join "`n"
        $result | Should -Not -Match "^\s+bot\s+Manage"
    }
}

Describe "ostwin channel status" {
    It "reports channels not running when no PID file exists" {
        $env:HOME = $TestDrive
        $pidFile = Join-Path $TestDrive ".ostwin" "channel.pid"
        if (Test-Path $pidFile) { Remove-Item $pidFile }

        $result = bash $script:ostwin channel status 2>&1
        $result | Should -Match "Channels not running"
    }

    It "reports stale PID when PID file has dead process" {
        $env:HOME = $TestDrive
        $ostwDir = Join-Path $TestDrive ".ostwin"
        New-Item -ItemType Directory -Path $ostwDir -Force | Out-Null
        "99999999" | Out-File (Join-Path $ostwDir "channel.pid") -NoNewline

        $result = bash $script:ostwin channel status 2>&1
        $result | Should -Match "NOT running"
    }
}

Describe "ostwin channel stop" {
    It "reports channels not running when no PID file" {
        $env:HOME = $TestDrive
        $pidFile = Join-Path $TestDrive ".ostwin" "channel.pid"
        if (Test-Path $pidFile) { Remove-Item $pidFile }

        $result = bash $script:ostwin channel stop 2>&1
        $result | Should -Match "Channels not running"
    }

    It "cleans up stale PID file" {
        $env:HOME = $TestDrive
        $ostwDir = Join-Path $TestDrive ".ostwin"
        New-Item -ItemType Directory -Path $ostwDir -Force | Out-Null
        $pidFile = Join-Path $ostwDir "channel.pid"
        "99999999" | Out-File $pidFile -NoNewline

        $result = bash $script:ostwin channel stop 2>&1
        $result | Should -Match "stale PID file removed"
        Test-Path $pidFile | Should -BeFalse
    }
}

Describe "ostwin channel start validation" {
    It "fails when channel connector dir is not found" {
        $env:HOME = $TestDrive
        $emptyDir = Join-Path $TestDrive "empty-$(Get-Random)"
        New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null

        Push-Location $emptyDir
        try {
            $tempAgents = Join-Path $TestDrive "fake-agents-$(Get-Random)"
            New-Item -ItemType Directory -Path "$tempAgents/bin" -Force | Out-Null
            Copy-Item $script:ostwin "$tempAgents/bin/ostwin"
            '{}' | Out-File "$tempAgents/config.json"

            $env:AGENTS_DIR = $tempAgents
            $result = bash "$tempAgents/bin/ostwin" channel start 2>&1
            $LASTEXITCODE | Should -Be 1
            $result | Should -Match "channel connector dir not found"
        }
        finally {
            Pop-Location
            Remove-Item -Recurse -Force $tempAgents -ErrorAction SilentlyContinue
        }
    }
}

Describe "ostwin channel logs" {
    It "fails when no log file exists" {
        $env:HOME = $TestDrive
        $logFile = Join-Path $TestDrive ".ostwin" "logs" "channel.log"
        if (Test-Path $logFile) { Remove-Item $logFile }

        $result = bash $script:ostwin channel logs 2>&1
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "No log file found"
    }
}

Describe "ostwin bot/discord are removed" {
    It "'ostwin bot' is an unknown command" {
        $result = bash $script:ostwin bot status 2>&1
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "Unknown command"
    }

    It "'ostwin discord' is an unknown command" {
        $result = bash $script:ostwin discord status 2>&1
        $LASTEXITCODE | Should -Be 1
        $result | Should -Match "Unknown command"
    }
}
