#Requires -Version 7.0
# Agent OS — Thread Safety Pester Tests
#
# Tests for the concurrency fixes in Utils.psm1:
#   - Set-WarRoomStatus atomic writes under lock
#   - Test-PidAlive start-time cross-check for PID reuse detection
#   - Write-PidFile creates both .pid and .start files
#   - Write-ChannelLine appends correctly under lock

BeforeAll {
    Import-Module (Join-Path (Resolve-Path "$PSScriptRoot/../lib").Path "Lock.psm1") -Force
    Import-Module (Join-Path (Resolve-Path "$PSScriptRoot/../lib").Path "Utils.psm1") -Force
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
    Remove-Module -Name "Lock" -ErrorAction SilentlyContinue
}

# ─── Set-WarRoomStatus — Atomic Writes ──────────────────────────────────────

Describe "Set-WarRoomStatus (thread safety)" {

    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
    }

    It "writes the status file atomically" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "developing"
        $status = (Get-Content (Join-Path $script:roomDir "status") -Raw).Trim()
        $status | Should -Be "developing"
    }

    It "creates a .status.lock file during operation" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        # The lock file should exist (created by Invoke-WithFileLock)
        Test-Path (Join-Path $script:roomDir ".status.lock") | Should -BeTrue
    }

    It "records old status as 'unknown' when no prior status exists" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        $audit = Get-Content (Join-Path $script:roomDir "audit.log") -Raw
        $audit | Should -Match "unknown -> pending"
    }

    It "correctly records status transitions under lock" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "developing"
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "passed"

        $finalStatus = (Get-Content (Join-Path $script:roomDir "status") -Raw).Trim()
        $finalStatus | Should -Be "passed"

        $auditLines = Get-Content (Join-Path $script:roomDir "audit.log")
        $auditLines.Count | Should -Be 3
        $auditLines[0] | Should -Match "unknown -> pending"
        $auditLines[1] | Should -Match "pending -> developing"
        $auditLines[2] | Should -Match "developing -> passed"
    }

    It "writes state_changed_at epoch under lock" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "developing"
        $epoch = (Get-Content (Join-Path $script:roomDir "state_changed_at") -Raw).Trim()
        $epoch | Should -Match '^\d+$'
        [int]$epoch | Should -BeGreaterThan 1700000000
    }

    It "throws when room directory does not exist" {
        { Set-WarRoomStatus -RoomDir "/nonexistent/room-xyz" -NewStatus "pending" } |
            Should -Throw "*not found*"
    }
}

# ─── Test-PidAlive — PID Reuse Detection ────────────────────────────────────

Describe "Test-PidAlive (PID reuse detection)" {

    It "returns false for a non-existent PID file" {
        Test-PidAlive -PidFile "/nonexistent/file.pid" | Should -BeFalse
    }

    It "returns false for a non-running PID" {
        $pidFile = Join-Path $TestDrive "dead.pid"
        "999999" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }

    It "returns false for an empty PID file" {
        $pidFile = Join-Path $TestDrive "empty.pid"
        "" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }

    It "returns false for non-numeric PID file content" {
        $pidFile = Join-Path $TestDrive "bad.pid"
        "not-a-number" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }

    It "returns true for the current process PID (no .start file)" {
        $pidFile = Join-Path $TestDrive "alive.pid"
        $PID.ToString() | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeTrue
    }

    It "returns true when start time matches" {
        $pidFile = Join-Path $TestDrive "match.pid"
        $PID.ToString() | Out-File -FilePath $pidFile -NoNewline

        # Write matching start time
        $startFile = [System.IO.Path]::ChangeExtension($pidFile, '.start')
        $proc = Get-Process -Id $PID
        $proc.StartTime.ToUniversalTime().ToString('o') | Out-File -FilePath $startFile -NoNewline

        Test-PidAlive -PidFile $pidFile | Should -BeTrue
    }

    It "returns false when start time does NOT match (PID reuse)" {
        $pidFile = Join-Path $TestDrive "reuse.pid"
        $PID.ToString() | Out-File -FilePath $pidFile -NoNewline

        # Write a fake start time that doesn't match the actual process
        $startFile = [System.IO.Path]::ChangeExtension($pidFile, '.start')
        "2000-01-01T00:00:00.0000000Z" | Out-File -FilePath $startFile -NoNewline

        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }
}

# ─── Write-PidFile ──────────────────────────────────────────────────────────

Describe "Write-PidFile" {

    It "creates a .pid file with the process ID" {
        $pidFile = Join-Path $TestDrive "agent.pid"
        Write-PidFile -PidFile $pidFile -ProcessId $PID

        Test-Path $pidFile | Should -BeTrue
        $content = (Get-Content $pidFile -Raw).Trim()
        $content | Should -Be $PID.ToString()
    }

    It "creates a companion .start file with the process start time" {
        $pidFile = Join-Path $TestDrive "agent2.pid"
        Write-PidFile -PidFile $pidFile -ProcessId $PID

        $startFile = [System.IO.Path]::ChangeExtension($pidFile, '.start')
        Test-Path $startFile | Should -BeTrue

        $startContent = (Get-Content $startFile -Raw).Trim()
        # Should be an ISO 8601 timestamp
        $startContent | Should -Match '^\d{4}-\d{2}-\d{2}T'
    }

    It "creates files that pass Test-PidAlive validation" {
        $pidFile = Join-Path $TestDrive "roundtrip.pid"
        Write-PidFile -PidFile $pidFile -ProcessId $PID
        Test-PidAlive -PidFile $pidFile | Should -BeTrue
    }

    It "handles a dead process ID gracefully (no .start file, but .pid is written)" {
        $pidFile = Join-Path $TestDrive "deadproc.pid"
        # Use a PID that almost certainly doesn't exist
        Write-PidFile -PidFile $pidFile -ProcessId 999999

        Test-Path $pidFile | Should -BeTrue
        $content = (Get-Content $pidFile -Raw).Trim()
        $content | Should -Be "999999"

        # .start file may or may not exist (process was not found)
        # But the function should not throw
    }
}

# ─── Write-ChannelLine ──────────────────────────────────────────────────────

Describe "Write-ChannelLine" {

    It "appends a single JSON line to the channel file" {
        $channelFile = Join-Path $TestDrive "channel.jsonl"
        # Create an empty file without BOM or extra content
        New-Item -ItemType File -Path $channelFile -Force | Out-Null

        $json = '{"type":"task","body":"hello"}'
        Write-ChannelLine -ChannelFile $channelFile -JsonLine $json

        # Force array to avoid single-string unwrap (indexing a string returns a char)
        [string[]]$lines = @(Get-Content $channelFile | Where-Object { $_ -match '\S' })
        $lines.Count | Should -Be 1
        $lines[0] | Should -Be $json
    }

    It "appends multiple lines in order" {
        $channelFile = Join-Path $TestDrive "channel-multi.jsonl"
        New-Item -ItemType File -Path $channelFile -Force | Out-Null

        Write-ChannelLine -ChannelFile $channelFile -JsonLine '{"seq":1}'
        Write-ChannelLine -ChannelFile $channelFile -JsonLine '{"seq":2}'
        Write-ChannelLine -ChannelFile $channelFile -JsonLine '{"seq":3}'

        $lines = Get-Content $channelFile | Where-Object { $_ -match '\S' }
        $lines.Count | Should -Be 3
        $lines[0] | Should -Be '{"seq":1}'
        $lines[1] | Should -Be '{"seq":2}'
        $lines[2] | Should -Be '{"seq":3}'
    }

    It "creates a .lock file for the channel" {
        $channelFile = Join-Path $TestDrive "channel-lock.jsonl"
        New-Item -ItemType File -Path $channelFile -Force | Out-Null

        Write-ChannelLine -ChannelFile $channelFile -JsonLine '{"test":true}'

        Test-Path "$channelFile.lock" | Should -BeTrue
    }

    It "handles concurrent writers without data loss" {
        $channelFile = Join-Path $TestDrive "channel-concurrent.jsonl"
        New-Item -ItemType File -Path $channelFile -Force | Out-Null

        $jobs = 1..5 | ForEach-Object {
            $idx = $_
            Start-Job -ScriptBlock {
                param($LockModPath, $UtilsModPath, $ChFile, $Index)
                Import-Module $LockModPath -Force
                Import-Module $UtilsModPath -Force
                Write-ChannelLine -ChannelFile $ChFile -JsonLine "{`"writer`":$Index}"
            } -ArgumentList `
                (Join-Path (Resolve-Path "$PSScriptRoot/../.agents/lib").Path "Lock.psm1"),
                (Join-Path (Resolve-Path "$PSScriptRoot/../.agents/lib").Path "Utils.psm1"),
                $channelFile, $idx
        }

        $jobs | Wait-Job -Timeout 30 | Out-Null
        $jobs | ForEach-Object {
            $_ | Receive-Job -ErrorAction SilentlyContinue | Out-Null
            $_ | Remove-Job -Force
        }

        $lines = Get-Content $channelFile | Where-Object { $_ -match '\S' }
        $lines.Count | Should -Be 5
    }
}
