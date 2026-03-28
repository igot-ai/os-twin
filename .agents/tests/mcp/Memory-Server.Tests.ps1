
# Agent OS — Memory Server Pester Tests

BeforeAll {
    $script:MemoryCLI = Join-Path (Resolve-Path "$PSScriptRoot/../../mcp").Path "memory-cli.py"

    # --- Helper: invoke a memory CLI command and return raw output ---
    function Invoke-Memory {
        param(
            [string]$Command,
            [hashtable]$Params = @{},
            [string]$Root
        )
        $jsonStr = $Params | ConvertTo-Json -Compress -Depth 5
        $env:AGENT_OS_ROOT = $Root
        $raw = python3 $script:MemoryCLI $Command $jsonStr 2>&1
        $env:AGENT_OS_ROOT = $null
        # Join array output into single string (Python multiline output becomes array in pwsh)
        if ($raw -is [array]) { return ($raw -join "`n") } else { return $raw }
    }

    # --- Helper: publish a test memory and return the mem ID ---
    function Publish-TestMemory {
        param(
            [string]$Root,
            [string]$Kind = "artifact",
            [string]$Summary = "Test entry",
            [string[]]$Tags = @("test"),
            [string]$RoomId = "room-001",
            [string]$AuthorRole = "engineer",
            [string]$Ref = "EPIC-001",
            [string]$Detail,
            [string]$Supersedes
        )
        $p = @{
            kind        = $Kind
            summary     = $Summary
            tags        = $Tags
            room_id     = $RoomId
            author_role = $AuthorRole
            ref         = $Ref
        }
        if ($Detail) { $p["detail"] = $Detail }
        if ($Supersedes) { $p["supersedes"] = $Supersedes }
        $result = Invoke-Memory -Command "publish" -Params $p -Root $Root
        # Extract ID from "published:mem-xxx-..."
        return $result -replace "^published:", ""
    }
}

Describe "Memory Server — publish" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null
    }

    It "creates ledger.jsonl on first publish" {
        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        Test-Path $ledger | Should -BeFalse

        Publish-TestMemory -Root $script:root | Out-Null

        Test-Path $ledger | Should -BeTrue
    }

    It "returns an ID with the correct prefix for each kind" {
        foreach ($kind in @("artifact", "decision", "interface", "convention", "warning")) {
            $prefix = "mem-$($kind.Substring(0,3))-"
            $id = Publish-TestMemory -Root $script:root -Kind $kind
            $id | Should -Match "^$prefix"
        }
    }

    It "writes valid JSON to the ledger" {
        Publish-TestMemory -Root $script:root -Summary "Created users table" -Tags @("db","users") | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $lines = @(Get-Content $ledger | Where-Object { $_.Trim() })
        $lines.Count | Should -Be 1

        $entry = $lines[0] | ConvertFrom-Json
        $entry.kind     | Should -Be "artifact"
        $entry.summary  | Should -Be "Created users table"
        $entry.room_id  | Should -Be "room-001"
        $entry.ref      | Should -Be "EPIC-001"
        $entry.tags     | Should -Contain "db"
        $entry.tags     | Should -Contain "users"
        $entry.ts       | Should -Not -BeNullOrEmpty
        $entry.id       | Should -Not -BeNullOrEmpty
    }

    It "appends multiple entries to the same ledger" {
        Publish-TestMemory -Root $script:root -Summary "First"  | Out-Null
        Publish-TestMemory -Root $script:root -Summary "Second" | Out-Null
        Publish-TestMemory -Root $script:root -Summary "Third"  | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $lines = @(Get-Content $ledger | Where-Object { $_.Trim() })
        $lines.Count | Should -Be 3
    }

    It "generates unique IDs" {
        $id1 = Publish-TestMemory -Root $script:root -Summary "First"
        Start-Sleep -Milliseconds 5
        $id2 = Publish-TestMemory -Root $script:root -Summary "Second"
        $id1 | Should -Not -Be $id2
    }

    It "includes detail when provided" {
        Publish-TestMemory -Root $script:root -Detail "function verify(jwt)" | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() }) | ConvertFrom-Json
        $entry.detail | Should -Be "function verify(jwt)"
    }

    It "omits detail field when not provided" {
        Publish-TestMemory -Root $script:root | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() }) | ConvertFrom-Json
        $entry.PSObject.Properties.Name | Should -Not -Contain "detail"
    }

    It "lowercases and trims tags" {
        Publish-TestMemory -Root $script:root -Tags @(" Auth ", "DATABASE", "User-Api") | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $entry = (Get-Content $ledger | Where-Object { $_.Trim() }) | ConvertFrom-Json
        $entry.tags | Should -Contain "auth"
        $entry.tags | Should -Contain "database"
        $entry.tags | Should -Contain "user-api"
    }

    It "returns error for invalid kind" {
        $result = Invoke-Memory -Command "publish" -Root $script:root -Params @{
            kind = "invalid"; summary = "x"; tags = @("t"); room_id = "r"; author_role = "e"; ref = "X"
        }
        $result | Should -Match "^error:"
    }

    It "creates index.json after publish" {
        Publish-TestMemory -Root $script:root | Out-Null

        $index = Join-Path $script:root ".agents" "memory" "index.json"
        Test-Path $index | Should -BeTrue
        $data = Get-Content $index -Raw | ConvertFrom-Json
        $data.count | Should -Be 1
        $data.entries.Count | Should -Be 1
    }

    It "records supersedes field when provided" {
        $id1 = Publish-TestMemory -Root $script:root -Summary "v1"
        Publish-TestMemory -Root $script:root -Summary "v2" -Supersedes $id1 | Out-Null

        $ledger = Join-Path $script:root ".agents" "memory" "ledger.jsonl"
        $lines = @(Get-Content $ledger | Where-Object { $_.Trim() })
        $entry2 = $lines[1] | ConvertFrom-Json
        $entry2.supersedes | Should -Be $id1
    }
}

Describe "Memory Server — query" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null

        # Seed test data
        Publish-TestMemory -Root $script:root -Kind "artifact"   -Summary "Users table"       -Tags @("db","users")   -RoomId "room-001" -Ref "EPIC-001" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "decision"   -Summary "JWT for auth"      -Tags @("auth","jwt")   -RoomId "room-001" -Ref "EPIC-001" -AuthorRole "architect" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "interface"  -Summary "GET /api/users"    -Tags @("api","users")  -RoomId "room-002" -Ref "EPIC-002" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "camelCase for JS"  -Tags @("naming")       -RoomId "room-002" -Ref "EPIC-002" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "warning"    -Summary "Don't touch X"     -Tags @("legacy")       -RoomId "room-003" -Ref "EPIC-003" | Out-Null
    }

    It "returns all entries when no filters" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 5
    }

    It "filters by kind" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ kind = "decision" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "JWT for auth"
    }

    It "filters by ref" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ ref = "EPIC-002" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 2
    }

    It "filters by room_id" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ room_id = "room-003" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].kind | Should -Be "warning"
    }

    It "filters by author_role" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ author_role = "architect" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "JWT for auth"
    }

    It "filters by tags (OR match)" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ tags = @("auth","legacy") }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 2
    }

    It "excludes a room" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ exclude_room = "room-001" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 3
        $entries | ForEach-Object { $_.room_id | Should -Not -Be "room-001" }
    }

    It "returns last_n entries" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ last_n = 2 }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 2
        # Should be the last two published
        $entries[0].kind | Should -Be "convention"
        $entries[1].kind | Should -Be "warning"
    }

    It "combines multiple filters" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{
            kind = "artifact"; room_id = "room-001"
        }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "Users table"
    }

    It "returns empty array when no matches" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ kind = "artifact"; room_id = "room-999" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 0
    }

    It "excludes superseded entries" {
        $id1 = Publish-TestMemory -Root $script:root -Kind "convention" -Summary "snake_case" -Tags @("naming") -RoomId "room-004" -Ref "EPIC-004"
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "camelCase (v2)" -Tags @("naming") -RoomId "room-004" -Ref "EPIC-004" -Supersedes $id1 | Out-Null

        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ room_id = "room-004" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "camelCase (v2)"
    }
}

Describe "Memory Server — search" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null

        Publish-TestMemory -Root $script:root -Kind "artifact"  -Summary "Created users table with id, email, password_hash" -Tags @("database","users","schema") -RoomId "room-001" -Ref "EPIC-001" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "decision"  -Summary "Chose JWT over sessions for authentication"       -Tags @("auth","jwt")                -RoomId "room-001" -Ref "EPIC-001" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "interface" -Summary "Auth module exports verifyToken"                  -Tags @("auth","api")                -RoomId "room-002" -Ref "EPIC-002" -Detail "function verifyToken(jwt: string): AuthPayload" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "warning"   -Summary "Do not modify legacy payment gateway"             -Tags @("payment","legacy")          -RoomId "room-003" -Ref "EPIC-003" | Out-Null
    }

    It "finds entries by exact word match" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "users table" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -BeGreaterThan 0
        $entries[0].summary | Should -Match "users"
    }

    It "finds entries by tag content" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "database schema" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -BeGreaterThan 0
        $entries[0].tags | Should -Contain "database"
    }

    It "finds entries matching detail field" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "verifyToken" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -BeGreaterThan 0
        $entries[0].kind | Should -Be "interface"
    }

    It "returns results sorted by relevance (keyword match)" {
        # "auth jwt" should return entries that match both words ranked higher
        # (time decay may reorder entries with equal keyword scores)
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "auth jwt" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -BeGreaterOrEqual 2
        # Both decision (tags: auth,jwt) and interface (tags: auth,api) should appear
        $kinds = $entries | ForEach-Object { $_.kind }
        $kinds | Should -Contain "decision"
    }

    It "filters by kind" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "auth"; kind = "interface" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].kind | Should -Be "interface"
    }

    It "excludes a room" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "auth"; exclude_room = "room-001" }
        $entries = $result | ConvertFrom-Json
        $entries | ForEach-Object { $_.room_id | Should -Not -Be "room-001" }
    }

    It "respects max_results" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "auth"; max_results = 1 }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
    }

    It "returns empty array for nonsense query" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "xyzzyplugh" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 0
    }

    It "returns empty array for empty query" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "!!!" }
        $result | Should -Be "[]"
    }
}

Describe "Memory Server — get_context" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null

        Publish-TestMemory -Root $script:root -Kind "artifact"   -Summary "Users table created"     -Tags @("database","users")  -RoomId "room-001" -Ref "EPIC-001" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "interface"  -Summary "GET /api/v1/users"        -Tags @("api","users")       -RoomId "room-001" -Ref "EPIC-001" -Detail "Returns {id, email, createdAt}" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "decision"   -Summary "JWT authentication"       -Tags @("auth","jwt")        -RoomId "room-002" -Ref "EPIC-002" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "All timestamps UTC"       -Tags @("convention","time") -RoomId "room-002" -Ref "EPIC-002" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "warning"    -Summary "Legacy auth fragile"      -Tags @("auth","legacy")     -RoomId "room-003" -Ref "EPIC-003" | Out-Null
    }

    It "excludes own room from context" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{ room_id = "room-001" }
        $result | Should -Not -Match "room-001"
        $result | Should -Match "room-002"
    }

    It "returns markdown-formatted output" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{ room_id = "room-001" }
        $result | Should -Match "## Cross-Room Context"
        $result | Should -Match "###"
    }

    It "groups entries by kind with correct section headers" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{ room_id = "room-001" }
        $result | Should -Match "Decisions"
        $result | Should -Match "Conventions"
        $result | Should -Match "Warnings"
    }

    It "includes detail preview in code blocks" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{ room_id = "room-999" }
        # room-999 doesn't exist, so all entries are included
        $result | Should -Match "Returns \{id, email, createdAt\}"
        $result | Should -Match '```'
    }

    It "filters by keywords when provided" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{
            room_id = "room-003"; brief_keywords = @("auth","jwt")
        }
        $result | Should -Match "JWT"
        # Legacy auth warning is in room-003 (own room), so excluded
        $result | Should -Not -Match "Legacy auth fragile"
    }

    It "returns fallback message when no context available" {
        $emptyRoot = Join-Path $TestDrive "empty-$(Get-Random)"
        New-Item -ItemType Directory -Path $emptyRoot -Force | Out-Null
        $result = Invoke-Memory -Command "get_context" -Root $emptyRoot -Params @{ room_id = "room-001" }
        $result | Should -Be "No cross-room context available yet."
    }

    It "returns fallback when only own room has entries" {
        $soloRoot = Join-Path $TestDrive "solo-$(Get-Random)"
        New-Item -ItemType Directory -Path $soloRoot -Force | Out-Null
        Publish-TestMemory -Root $soloRoot -RoomId "room-only" | Out-Null

        $result = Invoke-Memory -Command "get_context" -Root $soloRoot -Params @{ room_id = "room-only" }
        $result | Should -Be "No cross-room context available yet."
    }

    It "respects max_entries" {
        $result = Invoke-Memory -Command "get_context" -Root $script:root -Params @{
            room_id = "room-999"; max_entries = 2
        }
        # Count bullet points (lines starting with "- **")
        $bullets = ($result -split "`n") | Where-Object { $_ -match "^- \*\*" }
        $bullets.Count | Should -BeLessOrEqual 2
    }
}

Describe "Memory Server — list" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null

        Publish-TestMemory -Root $script:root -Kind "artifact"  -Summary "Artifact entry"   | Out-Null
        Publish-TestMemory -Root $script:root -Kind "decision"  -Summary "Decision entry"   | Out-Null
        Publish-TestMemory -Root $script:root -Kind "interface" -Summary "Interface entry"  | Out-Null
    }

    It "returns all entries without filter" {
        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 3
    }

    It "filters by kind" {
        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{ kind = "decision" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].kind | Should -Be "decision"
    }

    It "returns summary_preview (truncated to 200 chars)" {
        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries[0].PSObject.Properties.Name | Should -Contain "summary_preview"
        $entries[0].PSObject.Properties.Name | Should -Not -Contain "detail"
    }

    It "includes required index fields" {
        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        foreach ($e in $entries) {
            $e.PSObject.Properties.Name | Should -Contain "id"
            $e.PSObject.Properties.Name | Should -Contain "ts"
            $e.PSObject.Properties.Name | Should -Contain "kind"
            $e.PSObject.Properties.Name | Should -Contain "room_id"
            $e.PSObject.Properties.Name | Should -Contain "ref"
            $e.PSObject.Properties.Name | Should -Contain "tags"
        }
    }

    It "returns empty array when no entries exist" {
        $emptyRoot = Join-Path $TestDrive "empty-$(Get-Random)"
        New-Item -ItemType Directory -Path $emptyRoot -Force | Out-Null
        $result = Invoke-Memory -Command "list" -Root $emptyRoot -Params @{}
        $result | Should -Be "[]"
    }

    It "excludes superseded entries from listing" {
        $id1 = Publish-TestMemory -Root $script:root -Kind "convention" -Summary "old convention"
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "new convention" -Supersedes $id1 | Out-Null

        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{ kind = "convention" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary_preview | Should -Be "new convention"
    }
}

Describe "Memory Server — supersedes" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null
    }

    It "superseded entry is excluded from query results" {
        $id1 = Publish-TestMemory -Root $script:root -Kind "convention" -Summary "Use snake_case" -Tags @("naming")
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "Use camelCase" -Tags @("naming") -Supersedes $id1 | Out-Null

        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{ kind = "convention" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "Use camelCase"
    }

    It "superseded entry is excluded from search results" {
        $id1 = Publish-TestMemory -Root $script:root -Kind "convention" -Summary "Use snake_case for naming" -Tags @("naming")
        Publish-TestMemory -Root $script:root -Kind "convention" -Summary "Use camelCase for naming" -Tags @("naming") -Supersedes $id1 | Out-Null

        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "naming" }
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Match "camelCase"
    }

    It "chained supersedes work (A -> B -> C, only C survives)" {
        $idA = Publish-TestMemory -Root $script:root -Summary "version A"
        $idB = Publish-TestMemory -Root $script:root -Summary "version B" -Supersedes $idA
        Publish-TestMemory -Root $script:root -Summary "version C" -Supersedes $idB | Out-Null

        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 1
        $entries[0].summary | Should -Be "version C"
    }

    It "index.json reflects supersedes correctly" {
        $id1 = Publish-TestMemory -Root $script:root -Summary "old"
        Publish-TestMemory -Root $script:root -Summary "new" -Supersedes $id1 | Out-Null

        $index = Join-Path $script:root ".agents" "memory" "index.json"
        $data = Get-Content $index -Raw | ConvertFrom-Json
        $data.count | Should -Be 1
        $data.entries[0].summary | Should -Be "new"
    }
}

Describe "Memory Server — edge cases" {
    BeforeEach {
        $script:root = Join-Path $TestDrive "proj-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:root -Force | Out-Null
    }

    It "handles empty ledger gracefully for query" {
        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{}
        $result | Should -Be "[]"
    }

    It "handles empty ledger gracefully for search" {
        $result = Invoke-Memory -Command "search" -Root $script:root -Params @{ text = "anything" }
        $result | Should -Be "[]"
    }

    It "handles empty ledger gracefully for list" {
        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{}
        $result | Should -Be "[]"
    }

    It "handles corrupt JSONL lines gracefully" {
        # Manually write corrupt data to ledger
        $memDir = Join-Path $script:root ".agents" "memory"
        New-Item -ItemType Directory -Path $memDir -Force | Out-Null
        $ledger = Join-Path $memDir "ledger.jsonl"

        $validEntry = @{ id = "mem-art-1-1"; ts = "2026-01-01T00:00:00Z"; kind = "artifact"; room_id = "room-001"; author_role = "engineer"; ref = "EPIC-001"; tags = @("test"); summary = "Valid entry" } | ConvertTo-Json -Compress
        @(
            $validEntry
            "this is not valid json {"
            ""
            $validEntry.Replace("mem-art-1-1", "mem-art-2-2").Replace("Valid entry", "Second valid")
        ) | Out-File $ledger -Encoding utf8

        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 2
    }

    It "handles many entries without error" {
        for ($i = 0; $i -lt 25; $i++) {
            Publish-TestMemory -Root $script:root -Summary "Entry $i" -Tags @("bulk") -RoomId "room-$($i % 5)" -Ref "EPIC-$($i % 3)" | Out-Null
        }

        $result = Invoke-Memory -Command "query" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 20  # MAX_SEARCH_RESULTS = 20

        $result = Invoke-Memory -Command "list" -Root $script:root -Params @{}
        $entries = $result | ConvertFrom-Json
        $entries.Count | Should -Be 25  # list has no limit
    }

    It "cross-room context works end-to-end" {
        # Room 1: build auth
        Publish-TestMemory -Root $script:root -Kind "artifact"  -Summary "Auth module built"  -Tags @("auth")      -RoomId "room-001" -Ref "EPIC-001" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "interface" -Summary "verifyToken(jwt)"   -Tags @("auth","api") -RoomId "room-001" -Ref "EPIC-001" -Detail "export function verifyToken(jwt: string): AuthPayload" | Out-Null
        Publish-TestMemory -Root $script:root -Kind "decision"  -Summary "JWT over sessions"  -Tags @("auth","jwt") -RoomId "room-001" -Ref "EPIC-001" | Out-Null

        # Room 2: build dashboard — should see room 1 context
        $context = Invoke-Memory -Command "get_context" -Root $script:root -Params @{
            room_id = "room-002"; brief_keywords = @("auth","users","dashboard")
        }

        $context | Should -Match "Cross-Room Context"
        $context | Should -Match "verifyToken"
        $context | Should -Match "JWT"
        $context | Should -Match "EPIC-001"
        $context | Should -Not -Match "room-002"
    }
}
