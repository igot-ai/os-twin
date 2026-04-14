# Agent OS — Test-DependenciesReady Pester Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "..")).Path
    $script:TestDepsReady = Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "Test-DependenciesReady.ps1"
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"
    # Build-DependencyGraph.ps1 was removed — inline a helper to write DAG.json
    # Test-DependenciesReady expects nodes as object keyed by task_ref
    function script:Write-TestDag {
        param([string]$WarRoomsDir)
        $nodes = @{}
        foreach ($room in (Get-ChildItem $WarRoomsDir -Directory -Filter "room-*")) {
            $cfg = Get-Content (Join-Path $room.FullName "config.json") -Raw | ConvertFrom-Json
            $deps = @()
            if ($cfg.depends_on) { $deps = @($cfg.depends_on) }
            $nodes[$cfg.task_ref] = @{ id = $cfg.task_ref; room_id = $room.Name; depends_on = $deps; depth = 0 }
        }
        foreach ($key in @($nodes.Keys)) {
            if ($nodes[$key].depends_on.Count -gt 0) { $nodes[$key].depth = 1 }
        }
        @{ nodes = $nodes; generated_at = (Get-Date -Format o) } |
            ConvertTo-Json -Depth 5 | Out-File (Join-Path $WarRoomsDir "DAG.json") -Encoding utf8
    }
}

Describe "Test-DependenciesReady" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
    }

    Context "No DAG (legacy mode)" {
        It "returns Ready=true when DAG.json is missing" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-001"

            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $true
        }
    }

    Context "All dependencies passed" {
        It "returns Ready=true when all deps have passed" {
            # Create room-001 (no deps) and room-002 (depends on TASK-001)
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Dashboard" -WarRoomsDir $script:warRoomsDir `
                                 -DependsOn @("TASK-001")

            # Set room-001 to passed
            "passed" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-001" "status") -NoNewline

            # Build DAG
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-002"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $true
        }
    }

    Context "Dependency still pending" {
        It "returns Ready=false, Reason=waiting when dep is pending" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Dashboard" -WarRoomsDir $script:warRoomsDir `
                                 -DependsOn @("TASK-001")

            # room-001 stays pending (default)
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-002"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $false
            $result.Reason | Should -Be "waiting"
            $result.WaitingOn | Should -Be "TASK-001"
        }
    }

    Context "Dependency developing (in progress)" {
        It "returns Ready=false, Reason=waiting when dep is developing" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Dashboard" -WarRoomsDir $script:warRoomsDir `
                                 -DependsOn @("TASK-001")

            "developing" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-001" "status") -NoNewline
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-002"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $false
            $result.Reason | Should -Be "waiting"
        }
    }

    Context "Dependency failed-final" {
        It "returns Ready=false, Reason=blocked when dep failed" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Dashboard" -WarRoomsDir $script:warRoomsDir `
                                 -DependsOn @("TASK-001")

            "failed-final" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-001" "status") -NoNewline
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-002"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $false
            $result.Reason | Should -Be "blocked"
            $result.BlockedBy | Should -Be "TASK-001"
        }
    }

    Context "Dependency blocked" {
        It "returns Ready=false, Reason=blocked when dep is blocked" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Dashboard" -WarRoomsDir $script:warRoomsDir `
                                 -DependsOn @("TASK-001")

            "blocked" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-001" "status") -NoNewline
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-002"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $false
            $result.Reason | Should -Be "blocked"
            $result.BlockedBy | Should -Be "TASK-001"
        }
    }

    Context "Node not in DAG" {
        It "returns Ready=true when room task-ref is not in DAG" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir

            # Build DAG for room-001 only
            Write-TestDag -WarRoomsDir $script:warRoomsDir

            # Create rogue room-002 not in the DAG
            $rogueDir = Join-Path $script:warRoomsDir "room-099"
            New-Item -ItemType Directory -Path $rogueDir -Force | Out-Null
            "TASK-099" | Out-File -FilePath (Join-Path $rogueDir "task-ref") -NoNewline

            $result = & $script:TestDepsReady -RoomDir $rogueDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $true
        }
    }

    Context "No dependencies (root node)" {
        It "returns Ready=true when node has empty depends_on" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Auth" -WarRoomsDir $script:warRoomsDir

            Write-TestDag -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-001"
            $result = & $script:TestDepsReady -RoomDir $roomDir -WarRoomsDir $script:warRoomsDir
            $result.Ready | Should -Be $true
        }
    }
}
