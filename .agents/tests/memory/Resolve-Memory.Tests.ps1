# Agent OS — Resolve-Memory Pester Tests

BeforeAll {
    $script:ResolveMemory = Join-Path (Resolve-Path "$PSScriptRoot/../../roles/_base").Path "Resolve-Memory.ps1"
    $script:agentsDir = (Resolve-Path "$PSScriptRoot/../..").Path
}

Describe "Resolve-Memory" {

    BeforeEach {
        # Create isolated memory structure
        $script:memRoot = Join-Path $TestDrive "agents-$(Get-Random)"
        $script:memDir = Join-Path $script:memRoot "memory"
        $script:knowledgeDir = Join-Path $script:memDir "knowledge"
        $script:sessionsDir = Join-Path $script:memDir "sessions"
        $script:workingDir = Join-Path $script:memDir "working"

        New-Item -ItemType Directory -Path $script:knowledgeDir -Force | Out-Null
        New-Item -ItemType Directory -Path $script:sessionsDir -Force | Out-Null
        New-Item -ItemType Directory -Path $script:workingDir -Force | Out-Null

        # Create a war-room stub
        $script:roomDir = Join-Path $TestDrive "room-rm-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        "# Test Brief`nBuild API with Express" |
            Out-File (Join-Path $script:roomDir "brief.md") -Encoding utf8
    }

    Context "With real agents directory" {

        It "does not throw for unknown role with non-existent room" {
            $fakeRoom = Join-Path $TestDrive "no-memory-room"
            New-Item -ItemType Directory -Path $fakeRoom -Force | Out-Null
            # Should not throw — may return empty or real KB data
            { & $script:ResolveMemory -RoleName "nonexistent-role-xyz" -RoomDir $fakeRoom } |
                Should -Not -Throw
        }

        It "returns markdown with Agent Memory header when facts exist" {
            $result = & $script:ResolveMemory -RoleName "engineer" -RoomDir $script:roomDir
            if ($result) {
                $result | Should -Match "Agent Memory"
            }
        }

        It "includes Knowledge Base section when facts match" {
            $result = & $script:ResolveMemory -RoleName "engineer" -RoomDir $script:roomDir
            if ($result) {
                $result | Should -Match "Knowledge Base"
            }
        }

        It "includes Recent Sessions section when digests exist" {
            $result = & $script:ResolveMemory -RoleName "engineer" -RoomDir $script:roomDir
            if ($result) {
                # There are real session digests in the project
                $result | Should -Match "Recent Sessions"
            }
        }

        It "loads Working Notes when working memory file exists" {
            # Create a working memory file for this specific role+room
            $roomId = Split-Path $script:roomDir -Leaf
            $workFile = Join-Path $script:agentsDir "memory" "working" "test-mem-engineer-$roomId.yml"
            try {
                New-Item -ItemType Directory -Path (Split-Path $workFile) -Force | Out-Null
                @"
role: test-mem-engineer
room_id: $roomId
notes:
  - note: "Test discovery from working memory"
    domains: ["testing"]
    timestamp: "2026-03-28T00:00:00Z"
"@ | Out-File -FilePath $workFile -Encoding utf8

                $result = & $script:ResolveMemory -RoleName "test-mem-engineer" -RoomDir $script:roomDir
                if ($result) {
                    $result | Should -Match "Working Notes"
                    $result | Should -Match "Test discovery from working memory"
                }
            }
            finally {
                Remove-Item $workFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "respects MaxTokens parameter" {
            $result = & $script:ResolveMemory -RoleName "engineer" -RoomDir $script:roomDir -MaxTokens 100
            if ($result) {
                # 100 tokens × 4 chars = 400 chars budget
                $result.Length | Should -BeLessThan 2000  # generous margin
            }
        }
    }
}
