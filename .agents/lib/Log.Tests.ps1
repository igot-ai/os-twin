# Agent OS — Log Module Pester Tests

BeforeAll {
    # Import the module under test
    $ModulePath = Join-Path $PSScriptRoot "Log.psm1"
    Import-Module $ModulePath -Force
}

AfterAll {
    Remove-Module -Name "Log" -ErrorAction SilentlyContinue
}

Describe "Get-OstwinLogLevel" {
    AfterEach {
        Remove-Item Env:AGENT_OS_LOG_LEVEL -ErrorAction SilentlyContinue
    }

    It "returns INFO by default when env var is not set" {
        Remove-Item Env:AGENT_OS_LOG_LEVEL -ErrorAction SilentlyContinue
        Get-OstwinLogLevel | Should -Be 'INFO'
    }

    It "returns the level from AGENT_OS_LOG_LEVEL env var" {
        $env:AGENT_OS_LOG_LEVEL = 'DEBUG'
        Get-OstwinLogLevel | Should -Be 'DEBUG'
    }

    It "is case-insensitive" {
        $env:AGENT_OS_LOG_LEVEL = 'warn'
        Get-OstwinLogLevel | Should -Be 'WARN'
    }

    It "falls back to INFO for unknown levels" {
        $env:AGENT_OS_LOG_LEVEL = 'TRACE'
        Get-OstwinLogLevel | Should -Be 'INFO'
    }
}

Describe "Get-OstwinLogDir" {
    AfterEach {
        Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
        Remove-Item Env:AGENTS_DIR -ErrorAction SilentlyContinue
    }

    It "returns AGENT_OS_LOG_DIR when set" {
        $testDir = Join-Path $TestDrive "custom-logs"
        $env:AGENT_OS_LOG_DIR = $testDir
        $result = Get-OstwinLogDir
        $result | Should -Be $testDir
        Test-Path $testDir | Should -BeTrue
    }

    It "creates the log directory if it doesn't exist" {
        $testDir = Join-Path $TestDrive "new-logs-$(Get-Random)"
        $env:AGENT_OS_LOG_DIR = $testDir
        Test-Path $testDir | Should -BeFalse
        Get-OstwinLogDir | Out-Null
        Test-Path $testDir | Should -BeTrue
    }
}

Describe "Write-OstwinLog" {
    BeforeEach {
        $script:logDir = Join-Path $TestDrive "logs-$(Get-Random)"
        $env:AGENT_OS_LOG_DIR = $script:logDir
        $env:AGENT_OS_LOG_LEVEL = 'DEBUG'
    }

    AfterEach {
        Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
        Remove-Item Env:AGENT_OS_LOG_LEVEL -ErrorAction SilentlyContinue
    }

    It "writes to the log file" {
        Write-OstwinLog -Level INFO -Message "test message"
        $logFile = Join-Path $script:logDir "ostwin.log"
        Test-Path $logFile | Should -BeTrue
        $content = Get-Content $logFile -Raw
        $content | Should -Match "test message"
    }

    It "includes timestamp, level, and caller in the log line" {
        Write-OstwinLog -Level WARN -Message "warning here" -Caller "TestFunc"
        $logFile = Join-Path $script:logDir "ostwin.log"
        $content = Get-Content $logFile -Raw
        $content | Should -Match "\[WARN\]"
        $content | Should -Match "\[TestFunc\]"
        $content | Should -Match "warning here"
        # ISO 8601 timestamp
        $content | Should -Match "\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]"
    }

    It "appends properties to the log line" {
        Write-OstwinLog -Level INFO -Message "with props" -Properties @{ room_id = "room-001"; task = "TASK-001" }
        $logFile = Join-Path $script:logDir "ostwin.log"
        $content = Get-Content $logFile -Raw
        $content | Should -Match "room_id=room-001"
        $content | Should -Match "task=TASK-001"
    }

    It "respects log level gating — suppresses DEBUG when level is WARN" {
        $env:AGENT_OS_LOG_LEVEL = 'WARN'
        Write-OstwinLog -Level DEBUG -Message "should not appear"
        Write-OstwinLog -Level INFO -Message "should not appear either"
        Write-OstwinLog -Level WARN -Message "should appear"
        $logFile = Join-Path $script:logDir "ostwin.log"
        if (Test-Path $logFile) {
            $content = Get-Content $logFile -Raw
            $content | Should -Not -Match "should not appear"
            $content | Should -Match "should appear"
        }
    }

    It "handles ERROR level" {
        Write-OstwinLog -Level ERROR -Message "critical failure"
        $logFile = Join-Path $script:logDir "ostwin.log"
        $content = Get-Content $logFile -Raw
        $content | Should -Match "\[ERROR\]"
        $content | Should -Match "critical failure"
    }
}

Describe "Write-OstwinJsonLog" {
    BeforeEach {
        $script:logDir = Join-Path $TestDrive "jsonl-logs-$(Get-Random)"
        $env:AGENT_OS_LOG_DIR = $script:logDir
    }

    AfterEach {
        Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
    }

    It "writes valid JSON to ostwin.jsonl" {
        Write-OstwinJsonLog -Level INFO -Event "test_event" -Data @{ key1 = "val1" }
        $jsonlFile = Join-Path $script:logDir "ostwin.jsonl"
        Test-Path $jsonlFile | Should -BeTrue
        $line = Get-Content $jsonlFile | Select-Object -Last 1
        $parsed = $line | ConvertFrom-Json
        $parsed.event | Should -Be "test_event"
        $parsed.level | Should -Be "INFO"
        $parsed.ts.ToString("o") | Should -Match "\d{4}-\d{2}-\d{2}T"
    }

    It "includes data properties in the JSON" {
        Write-OstwinJsonLog -Level WARN -Event "room_stuck" -Data @{ room_id = "room-001"; retries = "3" }
        $jsonlFile = Join-Path $script:logDir "ostwin.jsonl"
        $line = Get-Content $jsonlFile | Select-Object -Last 1
        $parsed = $line | ConvertFrom-Json
        $parsed.data.room_id | Should -Be "room-001"
        $parsed.data.retries | Should -Be "3"
    }

    It "handles empty data" {
        Write-OstwinJsonLog -Level INFO -Event "simple_event"
        $jsonlFile = Join-Path $script:logDir "ostwin.jsonl"
        $line = Get-Content $jsonlFile | Select-Object -Last 1
        $parsed = $line | ConvertFrom-Json
        $parsed.event | Should -Be "simple_event"
    }

    It "appends multiple events to the same file" {
        Write-OstwinJsonLog -Level INFO -Event "event_one"
        Write-OstwinJsonLog -Level INFO -Event "event_two"
        Write-OstwinJsonLog -Level INFO -Event "event_three"
        $jsonlFile = Join-Path $script:logDir "ostwin.jsonl"
        $lines = Get-Content $jsonlFile
        $lines.Count | Should -Be 3
    }
}
