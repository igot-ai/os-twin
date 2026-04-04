
# Agent OS — Memory Shell Wrapper Pester Tests
# Tests the .agents/bin/memory bash script end-to-end.

BeforeAll {
    $script:MemoryBin = Join-Path (Resolve-Path "$PSScriptRoot/../../bin").Path "memory"
}

Describe "Memory Shell — AGENT_OS_ROOT resolution" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null
        # Create .agents dir so the fallback doesn't trigger
        New-Item -ItemType Directory -Path (Join-Path $script:root ".agents" "memory") -Force | Out-Null
    }

    It "uses AGENT_OS_ROOT when explicitly set" {
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null
        $result = bash $script:MemoryBin publish artifact "test" --tags test --room r1 --ref E1 --role eng 2>&1
        $env:AGENT_OS_ROOT = $null
        $result | Should -Match "^published:mem-art-"
        Test-Path (Join-Path $script:root ".agents" "memory" "ledger.jsonl") | Should -BeTrue
    }

    It "derives AGENT_OS_ROOT from AGENT_OS_ROOM_DIR" {
        $roomDir = Join-Path $script:root ".war-rooms" "room-001"
        New-Item -ItemType Directory -Path $roomDir -Force | Out-Null
        $env:AGENT_OS_ROOT = $null
        $env:AGENT_OS_ROOM_DIR = $roomDir
        $env:AGENT_OS_ROLE = "engineer"
        $result = bash $script:MemoryBin publish artifact "from room" --tags test --ref E1 2>&1
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null
        $result | Should -Match "^published:mem-art-"
        Test-Path (Join-Path $script:root ".agents" "memory" "ledger.jsonl") | Should -BeTrue
    }
}

Describe "Memory Shell — auto-detection" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        $script:roomDir = Join-Path $script:root ".war-rooms" "room-042"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:root ".agents" "memory") -Force | Out-Null
    }

    It "auto-detects --room from AGENT_OS_ROOM_DIR" {
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $script:roomDir
        $env:AGENT_OS_ROLE = "qa"
        bash $script:MemoryBin publish artifact "auto room" --tags test --ref E1 2>&1 | Out-Null
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() } | Select-Object -Last 1) | ConvertFrom-Json
        $entry.room_id | Should -Be "room-042"
    }

    It "auto-detects --role from AGENT_OS_ROLE" {
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $script:roomDir
        $env:AGENT_OS_ROLE = "architect"
        bash $script:MemoryBin publish decision "auto role" --tags test --ref E1 2>&1 | Out-Null
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() } | Select-Object -Last 1) | ConvertFrom-Json
        $entry.author_role | Should -Be "architect"
    }

    It "explicit --room overrides AGENT_OS_ROOM_DIR" {
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $script:roomDir
        $env:AGENT_OS_ROLE = "engineer"
        bash $script:MemoryBin publish artifact "explicit room" --tags test --ref E1 --room room-override 2>&1 | Out-Null
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() } | Select-Object -Last 1) | ConvertFrom-Json
        $entry.room_id | Should -Be "room-override"
    }

    It "explicit --role overrides AGENT_OS_ROLE" {
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $script:roomDir
        $env:AGENT_OS_ROLE = "engineer"
        bash $script:MemoryBin publish artifact "explicit role" --tags test --ref E1 --role manager 2>&1 | Out-Null
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() } | Select-Object -Last 1) | ConvertFrom-Json
        $entry.author_role | Should -Be "manager"
    }
}

Describe "Memory Shell — all commands" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path (Join-Path $script:root ".agents" "memory") -Force | Out-Null
        $env:AGENT_OS_ROOT = $script:root
        $env:AGENT_OS_ROOM_DIR = $null
        $env:AGENT_OS_ROLE = $null
    }

    AfterEach {
        $env:AGENT_OS_ROOT = $null
    }

    It "publish + list round-trip" {
        bash $script:MemoryBin publish code "src/app.py" --tags api --room r1 --ref E1 --role eng 2>&1 | Out-Null
        $result = bash $script:MemoryBin list 2>&1
        if ($result -is [array]) { $result = $result -join "`n" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].kind | Should -Be "code"
    }

    It "search returns results" {
        bash $script:MemoryBin publish artifact "database schema users" --tags db --room r1 --ref E1 --role eng 2>&1 | Out-Null
        $result = bash $script:MemoryBin search "database schema" 2>&1
        if ($result -is [array]) { $result = $result -join "`n" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -BeGreaterThan 0
    }

    It "query filters by kind" {
        bash $script:MemoryBin publish decision "chose JWT" --tags auth --room r1 --ref E1 --role eng 2>&1 | Out-Null
        bash $script:MemoryBin publish artifact "built API" --tags api --room r1 --ref E1 --role eng 2>&1 | Out-Null
        $result = bash $script:MemoryBin query --kind decision 2>&1
        if ($result -is [array]) { $result = $result -join "`n" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].kind | Should -Be "decision"
    }

    It "context excludes own room" {
        bash $script:MemoryBin publish artifact "from r1" --tags test --room room-001 --ref E1 --role eng 2>&1 | Out-Null
        bash $script:MemoryBin publish artifact "from r2" --tags test --room room-002 --ref E2 --role eng 2>&1 | Out-Null
        $result = bash $script:MemoryBin context room-001 2>&1
        if ($result -is [array]) { $result = $result -join "`n" }
        $result | Should -Match "room-002"
        $result | Should -Not -Match "from r1"
    }

    It "help command works" {
        $result = bash $script:MemoryBin help 2>&1
        if ($result -is [array]) { $result = $result -join "`n" }
        $result | Should -Match "Usage: memory"
    }
}
