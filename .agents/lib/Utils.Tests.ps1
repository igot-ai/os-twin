# Agent OS — Utils Module Pester Tests

BeforeAll {
    Import-Module (Join-Path $PSScriptRoot "Utils.psm1") -Force
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
}

# ─── Read-OstwinConfig ──────────────────────────────────────────────────────

Describe "Read-OstwinConfig" {
    BeforeAll {
        # Create a test config file
        $script:configFile = Join-Path $TestDrive "config.json"
        @{
            version      = "0.1.0"
            project_name = "test-project"
            manager      = @{
                poll_interval_seconds = 5
                max_concurrent_rooms  = 50
                max_engineer_retries  = 3
                auto_approve_tools    = $true
                state_timeout_seconds = 900
            }
            engineer     = @{
                cli             = "deepagents"
                default_model   = "gemini-3-flash-preview"
                timeout_seconds = 600
                max_prompt_bytes = 102400
            }
            channel      = @{
                format                 = "jsonl"
                max_message_size_bytes = 65536
            }
        } | ConvertTo-Json -Depth 5 | Out-File $script:configFile -Encoding utf8
    }

    It "reads a top-level key" {
        Read-OstwinConfig -KeyPath "version" -ConfigPath $script:configFile | Should -Be "0.1.0"
    }

    It "reads a nested key" {
        Read-OstwinConfig -KeyPath "manager.poll_interval_seconds" -ConfigPath $script:configFile | Should -Be 5
    }

    It "reads a deeply nested key" {
        Read-OstwinConfig -KeyPath "engineer.default_model" -ConfigPath $script:configFile | Should -Be "gemini-3-flash-preview"
    }

    It "reads boolean values as lowercase strings" {
        Read-OstwinConfig -KeyPath "manager.auto_approve_tools" -ConfigPath $script:configFile | Should -Be "true"
    }

    It "reads integer values" {
        Read-OstwinConfig -KeyPath "channel.max_message_size_bytes" -ConfigPath $script:configFile | Should -Be 65536
    }

    It "throws when config file not found" {
        { Read-OstwinConfig -KeyPath "version" -ConfigPath "/nonexistent/config.json" } |
            Should -Throw "*not found*"
    }

    It "throws when key path is invalid" {
        { Read-OstwinConfig -KeyPath "nonexistent.path" -ConfigPath $script:configFile } |
            Should -Throw
    }

    It "uses AGENT_OS_CONFIG env var when ConfigPath not specified" {
        $env:AGENT_OS_CONFIG = $script:configFile
        try {
            Read-OstwinConfig -KeyPath "version" | Should -Be "0.1.0"
        }
        finally {
            Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
        }
    }
}

# ─── Set-WarRoomStatus ───────────────────────────────────────────────────────

Describe "Set-WarRoomStatus" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-test-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
    }

    It "writes the status file" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "engineering"
        $status = (Get-Content (Join-Path $script:roomDir "status") -Raw).Trim()
        $status | Should -Be "engineering"
    }

    It "writes state_changed_at as unix epoch" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        $epoch = (Get-Content (Join-Path $script:roomDir "state_changed_at") -Raw).Trim()
        $epoch | Should -Match '^\d+$'
        [int]$epoch | Should -BeGreaterThan 1700000000  # Sanity: after 2023
    }

    It "appends to audit.log with old -> new status" {
        # Set initial status
        "pending" | Out-File -FilePath (Join-Path $script:roomDir "status") -NoNewline
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "engineering"
        $auditContent = Get-Content (Join-Path $script:roomDir "audit.log") -Raw
        $auditContent | Should -Match "pending -> engineering"
    }

    It "records the correct old status as 'unknown' when status file is missing" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        $auditContent = Get-Content (Join-Path $script:roomDir "audit.log") -Raw
        $auditContent | Should -Match "unknown -> pending"
    }

    It "tracks multiple status transitions" {
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "pending"
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "engineering"
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "qa-review"
        Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "passed"
        $lines = Get-Content (Join-Path $script:roomDir "audit.log")
        $lines.Count | Should -Be 4
        $lines[2] | Should -Match "engineering -> qa-review"
    }

    It "throws for invalid status" {
        { Set-WarRoomStatus -RoomDir $script:roomDir -NewStatus "invalid-status" } |
            Should -Throw
    }

    It "throws when room directory doesn't exist" {
        { Set-WarRoomStatus -RoomDir "/nonexistent/room" -NewStatus "pending" } |
            Should -Throw "*not found*"
    }
}

# ─── Test-PidAlive ───────────────────────────────────────────────────────────

Describe "Test-PidAlive" {
    It "returns false when pid file doesn't exist" {
        Test-PidAlive -PidFile "/nonexistent/file.pid" | Should -BeFalse
    }

    It "returns false for a non-running PID" {
        $pidFile = Join-Path $TestDrive "dead.pid"
        "999999" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }

    It "returns true for the current process PID" {
        $pidFile = Join-Path $TestDrive "alive.pid"
        $PID.ToString() | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeTrue
    }

    It "returns false for empty pid file" {
        $pidFile = Join-Path $TestDrive "empty.pid"
        "" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }

    It "returns false for non-numeric pid file content" {
        $pidFile = Join-Path $TestDrive "bad.pid"
        "notapid" | Out-File -FilePath $pidFile -NoNewline
        Test-PidAlive -PidFile $pidFile | Should -BeFalse
    }
}

# ─── Get-TruncatedText ──────────────────────────────────────────────────────

Describe "Get-TruncatedText" {
    It "returns text unchanged when under limit" {
        Get-TruncatedText -Text "short" -MaxBytes 100 | Should -Be "short"
    }

    It "truncates text over limit and adds notice" {
        $result = Get-TruncatedText -Text "a]long text here" -MaxBytes 5
        $result | Should -BeLike "a]lon*"
        $result | Should -Match "\[TRUNCATED:"
        $result | Should -Match "original size 16 bytes"
    }

    It "returns exact-length text unchanged" {
        Get-TruncatedText -Text "exact" -MaxBytes 5 | Should -Be "exact"
    }

    It "handles empty text" {
        Get-TruncatedText -Text "" -MaxBytes 100 | Should -Be ""
    }
}

# ─── Get-OstwinAgentsDir ────────────────────────────────────────────────────

Describe "Get-OstwinAgentsDir" {
    It "returns AGENTS_DIR env var when set" {
        $env:AGENTS_DIR = "/custom/agents"
        try {
            Get-OstwinAgentsDir | Should -Be "/custom/agents"
        }
        finally {
            Remove-Item Env:AGENTS_DIR -ErrorAction SilentlyContinue
        }
    }
}
