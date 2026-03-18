<#
.SYNOPSIS
    Pester tests for Build-DependencyGraph.ps1
.DESCRIPTION
    Tests topological sorting (Kahn's algorithm), cycle detection, depth/wave
    computation, critical path, virtual node injection (PLAN-REVIEW), and
    WarRooms mode scanning.
#>

Describe "Build-DependencyGraph" {
    BeforeAll {
        $script:builder = Join-Path $PSScriptRoot "Build-DependencyGraph.ps1"
    }

    # =====================================================
    # Input Validation
    # =====================================================
    Context "Input Validation" {

        It "returns empty array for empty input" {
            $result = & $script:builder -Nodes @()
            $result.Count | Should -Be 0
        }

        It "throws on node without Id" {
            { & $script:builder -Nodes @( @{ DependsOn = @('A') } ) } |
                Should -Throw "*All nodes must have an 'Id' property*"
        }

        It "throws on duplicate node Id" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @() },
                @{ Id = 'A'; DependsOn = @() }
            )
            { & $script:builder -Nodes $nodes } |
                Should -Throw "*Duplicate node Id detected: 'A'*"
        }

        It "throws on missing non-virtual dependency" {
            $nodes = @( @{ Id = 'A'; DependsOn = @('B') } )
            { & $script:builder -Nodes $nodes } |
                Should -Throw "*Node 'A' depends on 'B', but 'B' was not found*"
        }
    }

    # =====================================================
    # Topological Sort
    # =====================================================
    Context "Topological Sort" {

        It "sorts a linear chain correctly (A→B→C)" {
            $nodes = @(
                @{ Id = 'TaskC'; DependsOn = @('TaskB') },
                @{ Id = 'TaskA'; DependsOn = @() },
                @{ Id = 'TaskB'; DependsOn = @('TaskA') }
            )
            $result = & $script:builder -Nodes $nodes
            $result[0].Id | Should -Be 'TaskA'
            $result[1].Id | Should -Be 'TaskB'
            $result[2].Id | Should -Be 'TaskC'
        }

        It "sorts multiple independent components" {
            $nodes = @(
                @{ Id = '1'; DependsOn = @() },
                @{ Id = '3'; DependsOn = @('2') },
                @{ Id = '2'; DependsOn = @('1') },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'A'; DependsOn = @() }
            )
            $result = & $script:builder -Nodes $nodes
            $result.Count | Should -Be 5
            $ids = @($result.Id)
            [array]::IndexOf($ids, '1') | Should -BeLessThan ([array]::IndexOf($ids, '2'))
            [array]::IndexOf($ids, '2') | Should -BeLessThan ([array]::IndexOf($ids, '3'))
            [array]::IndexOf($ids, 'A') | Should -BeLessThan ([array]::IndexOf($ids, 'B'))
        }

        It "handles a diamond dependency (A→B,C→D)" {
            $nodes = @(
                @{ Id = 'D'; DependsOn = @('B', 'C') },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'C'; DependsOn = @('A') },
                @{ Id = 'A'; DependsOn = @() }
            )
            $result = & $script:builder -Nodes $nodes
            $ids = @($result.Id)
            [array]::IndexOf($ids, 'A') | Should -BeLessThan ([array]::IndexOf($ids, 'B'))
            [array]::IndexOf($ids, 'A') | Should -BeLessThan ([array]::IndexOf($ids, 'C'))
            [array]::IndexOf($ids, 'B') | Should -BeLessThan ([array]::IndexOf($ids, 'D'))
            [array]::IndexOf($ids, 'C') | Should -BeLessThan ([array]::IndexOf($ids, 'D'))
        }

        It "handles a single node with no dependencies" {
            $result = & $script:builder -Nodes @( @{ Id = 'Alone'; DependsOn = @() } )
            $result.Count | Should -Be 1
            $result[0].Id | Should -Be 'Alone'
        }
    }

    # =====================================================
    # Cycle Detection
    # =====================================================
    Context "Cycle Detection" {

        It "detects a simple 2-node cycle" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @('B') },
                @{ Id = 'B'; DependsOn = @('A') }
            )
            { & $script:builder -Nodes $nodes } |
                Should -Throw "*Circular dependency detected*"
        }

        It "detects a larger cycle (A→B→C→D→A)" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @('B') },
                @{ Id = 'B'; DependsOn = @('C') },
                @{ Id = 'C'; DependsOn = @('D') },
                @{ Id = 'D'; DependsOn = @('A') },
                @{ Id = 'E'; DependsOn = @() }
            )
            { & $script:builder -Nodes $nodes } |
                Should -Throw "*Circular dependency detected involving nodes: A, B, C, D*"
        }
    }

    # =====================================================
    # Depth & Wave Computation
    # =====================================================
    Context "Depth and Wave Computation" {

        It "assigns depth 0 to root nodes" {
            $nodes = @(
                @{ Id = 'Root'; DependsOn = @() },
                @{ Id = 'Child'; DependsOn = @('Root') }
            )
            $result = & $script:builder -Nodes $nodes
            ($result | Where-Object { $_.Id -eq 'Root' }).Depth | Should -Be 0
        }

        It "computes correct depth for a chain" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @() },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'C'; DependsOn = @('B') }
            )
            $result = & $script:builder -Nodes $nodes
            ($result | Where-Object { $_.Id -eq 'A' }).Depth | Should -Be 0
            ($result | Where-Object { $_.Id -eq 'B' }).Depth | Should -Be 1
            ($result | Where-Object { $_.Id -eq 'C' }).Depth | Should -Be 2
        }

        It "computes max depth for a diamond" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @() },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'C'; DependsOn = @('A') },
                @{ Id = 'D'; DependsOn = @('B', 'C') }
            )
            $result = & $script:builder -Nodes $nodes
            ($result | Where-Object { $_.Id -eq 'D' }).Depth | Should -Be 2
        }
    }

    # =====================================================
    # Critical Path
    # =====================================================
    Context "Critical Path" {

        It "finds the longest chain as critical path" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @() },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'C'; DependsOn = @('B') },
                @{ Id = 'X'; DependsOn = @('A') }
            )
            $result = & $script:builder -Nodes $nodes
            # Critical path: A → B → C (length 3)
            ($result | Where-Object { $_.Id -eq 'A' }).OnCriticalPath | Should -Be $true
            ($result | Where-Object { $_.Id -eq 'B' }).OnCriticalPath | Should -Be $true
            ($result | Where-Object { $_.Id -eq 'C' }).OnCriticalPath | Should -Be $true
            ($result | Where-Object { $_.Id -eq 'X' }).OnCriticalPath | Should -Be $false
        }
    }

    # =====================================================
    # Dependents Tracking
    # =====================================================
    Context "Dependents (Reverse Edges)" {

        It "tracks which nodes depend on each node" {
            $nodes = @(
                @{ Id = 'A'; DependsOn = @() },
                @{ Id = 'B'; DependsOn = @('A') },
                @{ Id = 'C'; DependsOn = @('A') }
            )
            $result = & $script:builder -Nodes $nodes
            $aNode = $result | Where-Object { $_.Id -eq 'A' }
            $aNode.Dependents | Should -Contain 'B'
            $aNode.Dependents | Should -Contain 'C'
        }
    }

    # =====================================================
    # PLAN-REVIEW: Virtual Node Auto-Injection
    # =====================================================
    Context "PLAN-REVIEW Virtual Node" {

        It "auto-injects PLAN-REVIEW when referenced but not in node list" {
            # This is the exact scenario from the user's bug report:
            # Epics depend on PLAN-REVIEW, but PLAN-REVIEW isn't in the node list
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-002'; DependsOn = @('PLAN-REVIEW') }
            )
            # Should NOT throw
            $result = & $script:builder -Nodes $nodes
            $result.Count | Should -Be 3
        }

        It "places PLAN-REVIEW at depth 0 (root)" {
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-002'; DependsOn = @('PLAN-REVIEW', 'EPIC-001') }
            )
            $result = & $script:builder -Nodes $nodes
            $pr = $result | Where-Object { $_.Id -eq 'PLAN-REVIEW' }
            $pr.Depth | Should -Be 0
            $pr.DependsOn | Should -HaveCount 0
        }

        It "PLAN-REVIEW comes first in topological order" {
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-002'; DependsOn = @('PLAN-REVIEW') }
            )
            $result = & $script:builder -Nodes $nodes
            $result[0].Id | Should -Be 'PLAN-REVIEW'
        }

        It "PLAN-REVIEW lists its dependents correctly" {
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-002'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-003'; DependsOn = @('PLAN-REVIEW', 'EPIC-001') }
            )
            $result = & $script:builder -Nodes $nodes
            $pr = $result | Where-Object { $_.Id -eq 'PLAN-REVIEW' }
            $pr.Dependents | Should -Contain 'EPIC-001'
            $pr.Dependents | Should -Contain 'EPIC-002'
            $pr.Dependents | Should -Contain 'EPIC-003'
        }

        It "does NOT inject PLAN-REVIEW when it is already in the node list" {
            $nodes = @(
                @{ Id = 'PLAN-REVIEW'; DependsOn = @() },
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') }
            )
            $result = & $script:builder -Nodes $nodes
            # Should be exactly 2 nodes, not 3
            $result.Count | Should -Be 2
        }

        It "still throws for unknown non-virtual dependencies" {
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW', 'NONEXISTENT') }
            )
            { & $script:builder -Nodes $nodes } |
                Should -Throw "*Node 'EPIC-001' depends on 'NONEXISTENT'*"
        }

        It "assigns room-000 and architect role to virtual PLAN-REVIEW" {
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') }
            )
            $result = & $script:builder -Nodes $nodes
            $pr = $result | Where-Object { $_.Id -eq 'PLAN-REVIEW' }
            $pr.RoomId | Should -Be 'room-000'
            $pr.Role | Should -Be 'architect'
        }

        It "handles complex DAG: PLAN-REVIEW → multiple epics with inter-dependencies" {
            # Real-world scenario from a 4-EPIC plan:
            # PLAN-REVIEW → all epics
            # EPIC-002 → EPIC-001
            # EPIC-003 → EPIC-001
            # EPIC-004 → EPIC-002, EPIC-003
            $nodes = @(
                @{ Id = 'EPIC-001'; DependsOn = @('PLAN-REVIEW') },
                @{ Id = 'EPIC-002'; DependsOn = @('PLAN-REVIEW', 'EPIC-001') },
                @{ Id = 'EPIC-003'; DependsOn = @('PLAN-REVIEW', 'EPIC-001') },
                @{ Id = 'EPIC-004'; DependsOn = @('PLAN-REVIEW', 'EPIC-002', 'EPIC-003') }
            )
            $result = & $script:builder -Nodes $nodes

            # 5 nodes total (4 epics + injected PLAN-REVIEW)
            $result.Count | Should -Be 5

            # Topological order: PLAN-REVIEW first, EPIC-004 last
            $result[0].Id | Should -Be 'PLAN-REVIEW'
            $result[-1].Id | Should -Be 'EPIC-004'

            # Depth check
            ($result | Where-Object { $_.Id -eq 'PLAN-REVIEW' }).Depth | Should -Be 0
            ($result | Where-Object { $_.Id -eq 'EPIC-001' }).Depth | Should -Be 1
            ($result | Where-Object { $_.Id -eq 'EPIC-002' }).Depth | Should -Be 2
            ($result | Where-Object { $_.Id -eq 'EPIC-003' }).Depth | Should -Be 2
            ($result | Where-Object { $_.Id -eq 'EPIC-004' }).Depth | Should -Be 3
        }
    }

    # =====================================================
    # Output Shape
    # =====================================================
    Context "Output Shape" {

        It "enriched objects have all expected properties" {
            $nodes = @( @{ Id = 'A'; DependsOn = @() } )
            $result = & $script:builder -Nodes $nodes
            $result[0].PSObject.Properties.Name | Should -Contain 'Id'
            $result[0].PSObject.Properties.Name | Should -Contain 'DependsOn'
            $result[0].PSObject.Properties.Name | Should -Contain 'Dependents'
            $result[0].PSObject.Properties.Name | Should -Contain 'Depth'
            $result[0].PSObject.Properties.Name | Should -Contain 'OnCriticalPath'
            $result[0].PSObject.Properties.Name | Should -Contain 'RoomId'
            $result[0].PSObject.Properties.Name | Should -Contain 'Role'
            $result[0].PSObject.Properties.Name | Should -Contain 'CandidateRoles'
        }
    }

    # =====================================================
    # WarRooms Mode
    # =====================================================
    Context "WarRooms Mode" {

        BeforeAll {
            $script:testWarRooms = Join-Path ([System.IO.Path]::GetTempPath()) "dag-warrooms-test-$(Get-Random)"
            New-Item -ItemType Directory -Path $script:testWarRooms -Force | Out-Null

            # room-001: EPIC-001, depends on PLAN-REVIEW
            $room1 = Join-Path $script:testWarRooms "room-001"
            New-Item -ItemType Directory -Path $room1 -Force | Out-Null
            @{
                task_ref   = "EPIC-001"
                depends_on = @("PLAN-REVIEW")
                assignment = @{ assigned_role = "engineer"; candidate_roles = @("engineer", "qa") }
            } | ConvertTo-Json -Depth 3 | Out-File -FilePath (Join-Path $room1 "config.json") -Encoding utf8

            # room-002: EPIC-002, depends on PLAN-REVIEW + EPIC-001
            $room2 = Join-Path $script:testWarRooms "room-002"
            New-Item -ItemType Directory -Path $room2 -Force | Out-Null
            @{
                task_ref   = "EPIC-002"
                depends_on = @("PLAN-REVIEW", "EPIC-001")
                assignment = @{ assigned_role = "engineer"; candidate_roles = @("engineer") }
            } | ConvertTo-Json -Depth 3 | Out-File -FilePath (Join-Path $room2 "config.json") -Encoding utf8

            # Note: room-000 does NOT exist — simulating the bug scenario
        }

        AfterAll {
            if (Test-Path $script:testWarRooms) {
                Remove-Item $script:testWarRooms -Recurse -Force
            }
        }

        It "builds DAG from war-rooms without throwing on missing PLAN-REVIEW room" {
            $result = & $script:builder -WarRoomsDir $script:testWarRooms
            $result | Should -Not -BeNullOrEmpty
        }

        It "auto-injects PLAN-REVIEW as virtual node in WarRooms mode" {
            $result = & $script:builder -WarRoomsDir $script:testWarRooms
            $result.Count | Should -Be 3  # PLAN-REVIEW + EPIC-001 + EPIC-002
            ($result | Where-Object { $_.Id -eq 'PLAN-REVIEW' }).Depth | Should -Be 0
        }

        It "writes DAG.json with correct structure" {
            $result = & $script:builder -WarRoomsDir $script:testWarRooms
            $dagFile = Join-Path $script:testWarRooms "DAG.json"
            Test-Path $dagFile | Should -Be $true

            $dag = Get-Content $dagFile -Raw | ConvertFrom-Json
            $dag.total_nodes | Should -Be 3
            $dag.topological_order[0] | Should -Be 'PLAN-REVIEW'
            $dag.nodes.'PLAN-REVIEW'.room_id | Should -Be 'room-000'
        }

        It "validates successfully without writing DAG.json" {
            $dagFile = Join-Path $script:testWarRooms "DAG.json"
            if (Test-Path $dagFile) { Remove-Item $dagFile -Force }

            $tempWarRooms = Join-Path ([System.IO.Path]::GetTempPath()) "dag-validate-$(Get-Random)"
            New-Item -ItemType Directory -Path $tempWarRooms -Force | Out-Null

            $vroom = Join-Path $tempWarRooms "room-001"
            New-Item -ItemType Directory -Path $vroom -Force | Out-Null
            @{
                task_ref   = "EPIC-001"
                depends_on = @("PLAN-REVIEW")
                assignment = @{ assigned_role = "engineer" }
            } | ConvertTo-Json -Depth 3 | Out-File -FilePath (Join-Path $vroom "config.json") -Encoding utf8

            $result = & $script:builder -WarRoomsDir $tempWarRooms -Validate
            $result | Should -Not -BeNullOrEmpty
            Test-Path (Join-Path $tempWarRooms "DAG.json") | Should -Be $false

            Remove-Item $tempWarRooms -Recurse -Force
        }
    }
}