<#
.SYNOPSIS
    Builds a Directed Acyclic Graph (DAG) and returns the topological sort of nodes.

.DESCRIPTION
    Takes an array of nodes with their dependencies and returns an ordered array
    where dependencies are listed before the nodes that depend on them.
    Throws an error if a circular dependency (cycle) is detected.

    Also supports -WarRoomsDir mode: scans room-*/config.json for depends_on,
    builds nodes, sorts, and writes DAG.json with depth, waves, and critical path.

.PARAMETER Nodes
    An array of objects representing the nodes. Each object must have an 'Id' property
    and optionally a 'DependsOn' property (array of Ids this node depends on).
.PARAMETER WarRoomsDir
    Path to war-rooms directory. Scans room-*/config.json for depends_on.
.PARAMETER Validate
    Only validate the graph, don't write DAG.json.

.EXAMPLE
    $nodes = @(
        @{ Id = 'TaskC'; DependsOn = @('TaskB') }
        @{ Id = 'TaskA'; DependsOn = @() }
        @{ Id = 'TaskB'; DependsOn = @('TaskA') }
    )
    Build-DependencyGraph -Nodes $nodes

.EXAMPLE
    ./Build-DependencyGraph.ps1 -WarRoomsDir ".war-rooms"
#>
[CmdletBinding(DefaultParameterSetName = 'Nodes')]
param(
    [Parameter(ParameterSetName = 'Nodes', ValueFromPipeline = $true)]
    [AllowEmptyCollection()]
    [object[]]$Nodes = @(),

    [Parameter(ParameterSetName = 'WarRooms', Mandatory)]
    [string]$WarRoomsDir,

    [switch]$Validate
)

process {
    # --- Build nodes from WarRoomsDir if specified ---
    if ($PSCmdlet.ParameterSetName -eq 'WarRooms') {
        $Nodes = @()
        # First pass: collect all task-refs and detect duplicates
        $taskRefCounts = @{}
        $roomDirs = Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue
        foreach ($rd in $roomDirs) {
            $configFile = Join-Path $rd.FullName "config.json"
            if (-not (Test-Path $configFile)) { continue }
            $cfg = Get-Content $configFile -Raw | ConvertFrom-Json
            $tr = $cfg.task_ref
            if ($tr) {
                if (-not $taskRefCounts.ContainsKey($tr)) { $taskRefCounts[$tr] = 0 }
                $taskRefCounts[$tr]++
            }
        }

        # Second pass: build nodes, disambiguating duplicate task-refs with room suffix
        foreach ($rd in $roomDirs) {
            $configFile = Join-Path $rd.FullName "config.json"
            if (-not (Test-Path $configFile)) {
                Write-Warning "No config.json in $($rd.Name) -- skipping"
                continue
            }
            $cfg = Get-Content $configFile -Raw | ConvertFrom-Json
            $taskRef = $cfg.task_ref
            # Disambiguate: if multiple rooms share the same task-ref, append :room-NNN
            $nodeId = if ($taskRefCounts[$taskRef] -gt 1) { "$taskRef`:$($rd.Name)" } else { $taskRef }
            $roomDeps = if ($cfg.depends_on) { @($cfg.depends_on) } else { @() }
            $assignedRole = if ($cfg.assignment -and $cfg.assignment.assigned_role) { $cfg.assignment.assigned_role } else { "engineer" }
            $candidateRoles = @(if ($cfg.assignment -and $cfg.assignment.candidate_roles) { @($cfg.assignment.candidate_roles) } else { @($assignedRole) })
            $Nodes += @{
                Id              = $nodeId
                TaskRef         = $taskRef
                DependsOn       = $roomDeps
                RoomId          = $rd.Name
                Role            = $assignedRole
                CandidateRoles  = $candidateRoles
            }
        }

        # Rewrite depends_on references: if a dependency has been disambiguated,
        # expand it to all its disambiguated variants so the graph stays connected.
        $disambiguated = @{}
        foreach ($n in $Nodes) {
            $tr = $n.TaskRef
            if ($tr -and $n.Id -ne $tr) {
                if (-not $disambiguated.ContainsKey($tr)) { $disambiguated[$tr] = @() }
                $disambiguated[$tr] += $n.Id
            }
        }
        if ($disambiguated.Count -gt 0) {
            foreach ($n in $Nodes) {
                $expandedDeps = @()
                foreach ($dep in $n.DependsOn) {
                    if ($disambiguated.ContainsKey($dep)) {
                        $expandedDeps += $disambiguated[$dep]
                    } else {
                        $expandedDeps += $dep
                    }
                }
                $n.DependsOn = $expandedDeps
            }
        }
    }

    if (-not $Nodes -or $Nodes.Count -eq 0) {
        return @()
    }

    # Normalize input and validate Ids
    $nodeMap = @{}
    foreach ($node in $Nodes) {
        $id = $node.Id
        if (-not $id) {
            throw "All nodes must have an 'Id' property."
        }
        if ($nodeMap.ContainsKey($id)) {
            throw "Duplicate node Id detected: '$id'"
        }
        $nodeMap[$id] = $node
    }

    # --- Auto-inject well-known virtual nodes ---
    # PLAN-REVIEW is always injected by Start-Plan.ps1 as a universal dependency.
    # When Build-DependencyGraph is called in WarRooms mode, room-000 (the plan
    # review room) may not have a config.json, so PLAN-REVIEW won't appear in
    # the scanned nodes. We auto-inject it as a virtual root node (depth 0,
    # no dependencies) so the graph stays valid.
    $virtualNodeIds = @('PLAN-REVIEW')
    foreach ($node in $Nodes) {
        $deps = $node.DependsOn
        if ($null -ne $deps) {
            if ($deps -is [string]) { $deps = @($deps) }
            foreach ($dep in $deps) {
                if (-not $nodeMap.ContainsKey($dep) -and $dep -in $virtualNodeIds) {
                    $virtualNode = @{
                        Id              = $dep
                        DependsOn       = @()
                        RoomId          = "room-000"
                        Role            = "architect"
                        CandidateRoles  = @("manager", "architect")
                        Virtual         = $true
                    }
                    $nodeMap[$dep] = $virtualNode
                    Write-Verbose "[DAG] Auto-injected virtual node '$dep' (referenced but not in node list)"
                }
            }
        }
    }

    # Prepare for Kahn's algorithm
    $inDegree = @{}
    $adjacencyList = @{} # Maps dependency -> list of dependents

    # Initialize all nodes in map
    foreach ($id in $nodeMap.Keys) {
        $inDegree[$id] = 0
        $adjacencyList[$id] = @()
    }

    # Build graph
    foreach ($node in @($nodeMap.Values)) {
        $id = $node.Id
        $deps = $node.DependsOn

        if ($null -ne $deps -and $deps.Count -gt 0) {
            # Normalize to array if it's a single string
            if ($deps -is [string]) { $deps = @($deps) }

            foreach ($dep in $deps) {
                # Ensure the dependency exists in the node list
                if (-not $nodeMap.ContainsKey($dep)) {
                    throw "Node '$id' depends on '$dep', but '$dep' was not found in the Nodes list."
                }

                # Directed edge: Dependency -> Dependent
                $adjacencyList[$dep] += $id
                $inDegree[$id]++
            }
        }
    }

    # Kahn's Algorithm for Topological Sort
    $queue = [System.Collections.Generic.Queue[string]]::new()
    $sortedOrder = [System.Collections.Generic.List[string]]::new()

    # Enqueue all nodes with 0 in-degree (no dependencies)
    foreach ($id in $inDegree.Keys) {
        if ($inDegree[$id] -eq 0) {
            $queue.Enqueue($id)
        }
    }

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        $sortedOrder.Add($current)

        # For each node that depends on the current node, reduce its in-degree
        foreach ($dependent in $adjacencyList[$current]) {
            $inDegree[$dependent]--
            if ($inDegree[$dependent] -eq 0) {
                $queue.Enqueue($dependent)
            }
        }
    }

    # Cycle Detection
    if ($sortedOrder.Count -ne $nodeMap.Count) {
        # Find nodes that are stuck (inDegree > 0)
        $stuckNodes = @()
        foreach ($id in $inDegree.Keys) {
            if ($inDegree[$id] -gt 0) {
                $stuckNodes += $id
            }
        }
        $stuckStr = ($stuckNodes | Sort-Object) -join ', '
        throw "Circular dependency detected involving nodes: $stuckStr"
    }

    # --- Compute depth (wave level) ---
    $depth = @{}
    foreach ($id in $sortedOrder) {
        $nodeDeps = $nodeMap[$id].DependsOn
        if (-not $nodeDeps -or $nodeDeps.Count -eq 0) {
            $depth[$id] = 0
        }
        else {
            $maxDepth = 0
            foreach ($dep in $nodeDeps) {
                if ($depth[$dep] -gt $maxDepth) { $maxDepth = $depth[$dep] }
            }
            $depth[$id] = $maxDepth + 1
        }
    }

    # --- Compute critical path (longest chain) ---
    $pathLen = @{}
    foreach ($id in $sortedOrder) {
        $nodeDeps = $nodeMap[$id].DependsOn
        if (-not $nodeDeps -or $nodeDeps.Count -eq 0) {
            $pathLen[$id] = 1
        }
        else {
            $maxPL = 0
            foreach ($dep in $nodeDeps) {
                if ($pathLen[$dep] -gt $maxPL) { $maxPL = $pathLen[$dep] }
            }
            $pathLen[$id] = $maxPL + 1
        }
    }

    $maxPathLen = if ($pathLen.Count -gt 0) { ($pathLen.Values | Measure-Object -Maximum).Maximum } else { 0 }
    $criticalPath = @()
    if ($maxPathLen -gt 0) {
        $cpNode = $pathLen.GetEnumerator() | Where-Object { $_.Value -eq $maxPathLen } | Select-Object -First 1
        if ($cpNode) {
            $cpId = $cpNode.Key
            $criticalPath = @($cpId)
            while ($true) {
                $nodeDeps = $nodeMap[$cpId].DependsOn
                if (-not $nodeDeps -or $nodeDeps.Count -eq 0) { break }
                $bestPred = $null
                $bestPL = 0
                foreach ($dep in $nodeDeps) {
                    if ($pathLen[$dep] -gt $bestPL) {
                        $bestPL = $pathLen[$dep]
                        $bestPred = $dep
                    }
                }
                if ($bestPred) {
                    $criticalPath = @($bestPred) + $criticalPath
                    $cpId = $bestPred
                }
                else { break }
            }
        }
    }

    $onCriticalPath = @{}
    foreach ($cp in $criticalPath) { $onCriticalPath[$cp] = $true }

    # Return the ordered nodes (full objects with enrichment)
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($id in $sortedOrder) {
        $orig = $nodeMap[$id]
        $enriched = [PSCustomObject]@{
            Id             = $id
            TaskRef        = if ($orig.TaskRef) { $orig.TaskRef } else { $id }
            DependsOn      = if ($orig.DependsOn) { @($orig.DependsOn) } else { @() }
            Dependents     = @($adjacencyList[$id])
            Depth          = $depth[$id]
            OnCriticalPath = [bool]$onCriticalPath[$id]
            RoomId         = if ($orig.RoomId) { $orig.RoomId } else { "" }
            Role           = if ($orig.Role) { $orig.Role } else { "engineer" }
            CandidateRoles = @(if ($orig.CandidateRoles) { @($orig.CandidateRoles) } else { @("engineer") })
        }
        $result.Add($enriched)
    }

    # --- Write DAG.json if in WarRooms mode and not validate-only ---
    if ($PSCmdlet.ParameterSetName -eq 'WarRooms' -and -not $Validate) {
        $waves = @{}
        foreach ($r in $result) {
            $d = $r.Depth.ToString()
            if (-not $waves[$d]) { $waves[$d] = @() }
            $waves[$d] += $r.Id
        }

        $nodesHash = [ordered]@{}
        foreach ($r in $result) {
            $nodesHash[$r.Id] = [ordered]@{
                room_id          = $r.RoomId
                task_ref         = if ($r.TaskRef) { $r.TaskRef } else { $r.Id }
                role             = $r.Role
                candidate_roles  = $r.CandidateRoles
                depends_on       = @($r.DependsOn)
                dependents       = @($r.Dependents)
                depth            = $r.Depth
                on_critical_path = $r.OnCriticalPath
            }
        }

        $dagOutput = [ordered]@{
            generated_at         = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            total_nodes          = $result.Count
            max_depth            = if ($depth.Count -gt 0) { ($depth.Values | Measure-Object -Maximum).Maximum } else { 0 }
            nodes                = $nodesHash
            topological_order    = @($sortedOrder)
            critical_path        = @($criticalPath)
            critical_path_length = $criticalPath.Count
            waves                = $waves
        }

        $dagFile = Join-Path $WarRoomsDir "DAG.json"
        $dagOutput | ConvertTo-Json -Depth 10 | Out-File -FilePath $dagFile -Encoding utf8
        Write-Host "[DAG] Written to $dagFile ($($result.Count) nodes, depth $($dagOutput.max_depth))" -ForegroundColor Cyan
    }

    return $result.ToArray()
}
