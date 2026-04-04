<#
.SYNOPSIS
    Helper functions for the Manager Loop — extracted for testability & coverage.

.DESCRIPTION
    This module is dot-sourced by Start-ManagerLoop.ps1 and can be independently
    imported by Pester tests to achieve code-coverage instrumentation of the
    manager's core logic without running the infinite while-loop.

    Functions exported:
      Resolve-RoomSkills, Get-ActiveCount, Get-MsgCount, Get-LatestBody,
      Test-StateTimedOut, Stop-RoomProcesses, Write-RoomStatus,
      Find-LatestSignal, Invoke-SignalActions, Write-Log,
      Write-SpawnLock, Test-SpawnLock, Start-WorkerJob,
      Get-CachedDag, Set-BlockedDescendants, Invoke-ManagerTriage,
      Write-TriageContext, Handle-PlanApproval
#>

#region --- Module-level state (injected by Start-ManagerLoop.ps1 via Set-ManagerLoopContext) ---
$script:_ctx = $null

function Set-ManagerLoopContext {
    <#
    .SYNOPSIS
        Injects runtime context from Start-ManagerLoop.ps1 into this module.
        Called once at startup (or from test BeforeAll) to bind all script-scope
        dependencies (paths, config, cache references).
    #>
    param(
        [hashtable]$Context
    )
    $script:_ctx = $Context
}

function Get-ManagerLoopContext { return $script:_ctx }

# Convenience accessors (short names used internally)
function _ctx([string]$Key) { return $script:_ctx[$Key] }
#endregion

# ---------------------------------------------------------------------------
# Resolve-RoomSkills
# ---------------------------------------------------------------------------
function Resolve-RoomSkills {
    param([string]$RoomDir, [string]$TaskRef, [string]$AssignedRole)

    $agentsDir            = _ctx 'agentsDir'
    $dashboardBaseUrl     = _ctx 'dashboardBaseUrl'

    $roomConfigFile = Join-Path $RoomDir "config.json"
    if (-not (Test-Path $roomConfigFile)) { return }
    $rc = Get-Content $roomConfigFile -Raw | ConvertFrom-Json

    if ($rc.skill_refs -and $rc.skill_refs.Count -gt 0) { return }

    $query = $TaskRef
    $briefFile = Join-Path $RoomDir "brief.md"
    if (Test-Path $briefFile) {
        $briefContent = (Get-Content $briefFile -Raw -ErrorAction SilentlyContinue)
        if ($briefContent) { $query = $briefContent }
    }

    try {
        $encodedQuery = [System.Uri]::EscapeDataString($query)
        $encodedRole  = [System.Uri]::EscapeDataString($AssignedRole)
        $url = "${dashboardBaseUrl}/api/skills/search?q=${encodedQuery}&role=${encodedRole}&limit=5"
        $apiHeaders = if (Get-Command Get-OstwinApiHeaders -ErrorAction SilentlyContinue) { Get-OstwinApiHeaders } else { @{} }
        $response = Invoke-RestMethod -Uri $url -Method GET -Headers $apiHeaders -TimeoutSec 5 -ErrorAction Stop
        if ($response -and $response.Count -gt 0) {
            $topSkills  = @($response | Select-Object -First 10)
            $skillNames = @($topSkills | ForEach-Object { $_.name })

            $rc | Add-Member -NotePropertyName "skill_refs" -NotePropertyValue $skillNames -Force
            $rc | ConvertTo-Json -Depth 10 | Out-File -FilePath $roomConfigFile -Encoding utf8 -Force

            $roomSkillsDir = Join-Path $RoomDir "skills"
            if (-not (Test-Path $roomSkillsDir)) {
                New-Item -ItemType Directory -Path $roomSkillsDir -Force | Out-Null
            }

            foreach ($skill in $topSkills) {
                $relPath = $skill.relative_path
                if (-not $relPath) { continue }
                $srcDir = Join-Path $agentsDir $relPath
                if (-not (Test-Path $srcDir)) {
                    $homeSrc = Join-Path (Join-Path $env:HOME ".ostwin") $relPath
                    if (Test-Path $homeSrc) { $srcDir = $homeSrc } else { continue }
                }
                $destDir = Join-Path $roomSkillsDir $skill.name
                if (Test-Path $destDir) { Remove-Item -Path $destDir -Recurse -Force -ErrorAction SilentlyContinue }
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                Copy-Item -Path (Join-Path $srcDir "*") -Destination $destDir -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Log "INFO" "[$TaskRef] Resolved $($skillNames.Count) skills for ${AssignedRole}: $($skillNames -join ', ')"
        }
    }
    catch {
        Write-Log "WARN" "[$TaskRef] Skill resolution failed (dashboard may be offline): $_"
    }
}

# ---------------------------------------------------------------------------
# Get-ActiveCount
# ---------------------------------------------------------------------------
function Get-ActiveCount {
    $WarRoomsDir = _ctx 'WarRoomsDir'
    $count = 0
    Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
        $s = if (Test-Path (Join-Path $_.FullName "status")) {
            (Get-Content (Join-Path $_.FullName "status") -Raw).Trim()
        } else { "pending" }
        if ($s -notin @('pending', 'passed', 'failed-final', 'blocked', '')) { $count++ }
    }
    return $count
}

# ---------------------------------------------------------------------------
# Get-MsgCount
# ---------------------------------------------------------------------------
function Get-MsgCount {
    param([string]$RoomDir, [string]$MsgType)
    $readMessages = _ctx 'readMessages'
    try {
        $msgs = & $readMessages -RoomDir $RoomDir -FilterType $MsgType -AsObject
        if ($msgs) { return $msgs.Count }
    }
    catch { }
    return 0
}

# ---------------------------------------------------------------------------
# Get-LatestBody
# ---------------------------------------------------------------------------
function Get-LatestBody {
    param([string]$RoomDir, [string]$MsgType)
    $readMessages = _ctx 'readMessages'
    try {
        $msgs = & $readMessages -RoomDir $RoomDir -FilterType $MsgType -Last 1 -AsObject
        if ($msgs -and $msgs.Count -gt 0) { return $msgs[-1].body }
    }
    catch { }
    return ""
}

# ---------------------------------------------------------------------------
# Test-StateTimedOut
# ---------------------------------------------------------------------------
function Test-StateTimedOut {
    param([string]$RoomDir)
    $stateTimeout = _ctx 'stateTimeout'
    $changedFile = Join-Path $RoomDir "state_changed_at"
    if (-not (Test-Path $changedFile)) { return $false }
    $changedAt = [int](Get-Content $changedFile -Raw).Trim()
    $now = [int][double]::Parse((Get-Date -UFormat %s))
    return (($now - $changedAt) -gt $stateTimeout)
}

# ---------------------------------------------------------------------------
# Stop-RoomProcesses
# ---------------------------------------------------------------------------
function Stop-RoomProcesses {
    param([string]$RoomDir)
    $pidDir = Join-Path $RoomDir "pids"
    if (-not (Test-Path $pidDir)) { return }
    Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
        $pidVal = (Get-Content $_.FullName -Raw).Trim()
        if ($pidVal -match '^\d+$') {
            try { Stop-Process -Id ([int]$pidVal) -Force -ErrorAction SilentlyContinue } catch { }
        }
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
    Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# Write-RoomStatus
# ---------------------------------------------------------------------------
function Write-RoomStatus {
    param([string]$RoomDir, [string]$NewStatus)
    $oldStatus = if (Test-Path (Join-Path $RoomDir "status")) {
        (Get-Content (Join-Path $RoomDir "status") -Raw).Trim()
    } else { "unknown" }

    if (Get-Command Set-WarRoomStatus -ErrorAction SilentlyContinue) {
        Set-WarRoomStatus -RoomDir $RoomDir -NewStatus $NewStatus
    } else {
        $NewStatus | Out-File -FilePath (Join-Path $RoomDir "status") -Encoding utf8 -NoNewline
        $epoch = [int][double]::Parse((Get-Date -UFormat %s))
        $epoch.ToString() | Out-File -FilePath (Join-Path $RoomDir "state_changed_at") -Encoding utf8 -NoNewline
        $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        "$ts STATUS $oldStatus -> $NewStatus" | Out-File -Append -FilePath (Join-Path $RoomDir "audit.log") -Encoding utf8
    }

    $pidDir = Join-Path $RoomDir "pids"
    if (Test-Path $pidDir) {
        $terminalStates = @('passed', 'failed-final', 'blocked')
        if ($NewStatus -in $terminalStates) {
            Get-ChildItem $pidDir -Filter "*.pid"        -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
            Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        } else {
            $oldRole = $null
            $lcFile = Join-Path $RoomDir "lifecycle.json"
            if (Test-Path $lcFile) {
                try {
                    $lc = Get-Content $lcFile -Raw | ConvertFrom-Json
                    if ($lc.states -and $lc.states.$oldStatus -and $lc.states.$oldStatus.role) {
                        $oldRole = ($lc.states.$oldStatus.role -replace ':.*$', '')
                    }
                } catch { }
            }
            if ($oldRole) {
                Remove-Item (Join-Path $pidDir "$oldRole.pid")        -Force -ErrorAction SilentlyContinue
                Remove-Item (Join-Path $pidDir "$oldRole.spawned_at") -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Find-LatestSignal
# ---------------------------------------------------------------------------
function Find-LatestSignal {
    param(
        [string]$RoomDir,
        [Parameter(Mandatory)]$Lifecycle,
        [Parameter(Mandatory)][string]$StateName
    )
    $readMessages = _ctx 'readMessages'
    $roomId = Split-Path $RoomDir -Leaf

    $stateDef = $Lifecycle.states.$StateName
    if (-not $stateDef -or -not $stateDef.signals) {
        Write-Log "DEBUG" "[Find-LatestSignal][$roomId] state='$StateName' has no signals defined in lifecycle"
        return $null
    }
    $expectedSignals = @($stateDef.signals.PSObject.Properties.Name)
    $expectedRole    = if ($stateDef.role) { ($stateDef.role -replace ':.*$', '') } else { '' }

    $changedAt = 0
    $changedFile = Join-Path $RoomDir "state_changed_at"
    if (Test-Path $changedFile) {
        $changedAt = [int](Get-Content $changedFile -Raw).Trim()
    }
    Write-Log "DEBUG" "[Find-LatestSignal][$roomId] state='$StateName' role='$expectedRole' state_changed_at=$changedAt signals=($($expectedSignals -join ', '))"

    foreach ($sigType in $expectedSignals) {
        try {
            $msgs = & $readMessages -RoomDir $RoomDir -FilterType $sigType -Last 1 -AsObject
            if ($msgs -and $msgs.Count -gt 0) {
                $latest = $msgs[-1]

                $msgTs = 0
                if ($latest.ts) {
                    if ($latest.ts -is [datetime]) {
                        $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
                    } elseif ("$($latest.ts)" -match '^\d+$') {
                        $msgTs = [int]"$($latest.ts)"
                    } else {
                        try { $msgTs = [int][double]::Parse((Get-Date "$($latest.ts)" -UFormat %s)) } catch { }
                    }
                }
                $bodyPreview = if ($latest.body.Length -gt 120) { $latest.body.Substring(0, 120) + '...' } else { $latest.body }

                if ($expectedRole -and $latest.from) {
                    $senderBase = ($latest.from -replace ':.*$', '')
                    if ($senderBase -ne $expectedRole) {
                        Write-Log "DEBUG" "[Find-LatestSignal][$roomId] signal='$sigType' REJECTED: from='$($latest.from)' != lifecycle role='$expectedRole'"
                        continue
                    }
                }

                $accepted = ($msgTs -gt $changedAt)
                Write-Log "DEBUG" "[Find-LatestSignal][$roomId] signal='$sigType' from='$($latest.from)' msgTs=$msgTs changedAt=$changedAt accepted=$accepted body=[$bodyPreview]"
                if ($accepted) { return $sigType }
            } else {
                Write-Log "DEBUG" "[Find-LatestSignal][$roomId] signal='$sigType' — no messages found"
            }
        } catch {
            Write-Log "DEBUG" "[Find-LatestSignal][$roomId] signal='$sigType' — error: $($_.Exception.Message)"
        }
    }
    Write-Log "DEBUG" "[Find-LatestSignal][$roomId] no matching signal found"
    return $null
}

# ---------------------------------------------------------------------------
# Invoke-SignalActions
# ---------------------------------------------------------------------------
function Invoke-SignalActions {
    param([string]$RoomDir, [string[]]$Actions, [string]$TaskRef, [string]$BaseRole)
    $postMessage  = _ctx 'postMessage'
    $readMessages = _ctx 'readMessages'

    foreach ($action in $Actions) {
        switch ($action) {
            'increment_retries' {
                $retriesFile = Join-Path $RoomDir "retries"
                $r = if (Test-Path $retriesFile) { [int](Get-Content $retriesFile -Raw).Trim() } else { 0 }
                ($r + 1).ToString() | Out-File -FilePath $retriesFile -Encoding utf8 -NoNewline
            }
            'post_fix' {
                $feedback = Get-LatestBody $RoomDir "fail"
                if (-not $feedback) { $feedback = Get-LatestBody $RoomDir "escalate" }
                if (-not $feedback) { $feedback = Get-LatestBody $RoomDir "error" }
                if ($feedback) {
                    & $postMessage -RoomDir $RoomDir -From "manager" -To $BaseRole -Type "fix" -Ref $TaskRef -Body $feedback
                }
            }
            'revise_brief' {
                $briefFile   = Join-Path $RoomDir "brief.md"
                $triageFile  = Join-Path $RoomDir "artifacts" "triage-context.md"
                if ((Test-Path $briefFile) -and (Test-Path $triageFile)) {
                    $originalBrief = Get-Content $briefFile -Raw
                    $triageContent = Get-Content $triageFile -Raw
                    $updatedBrief  = $originalBrief + "`n`n---`n`n## Plan Revision Notes`n`n$triageContent"
                    $updatedBrief | Out-File -FilePath $briefFile -Encoding utf8 -Force
                }
                $qaRetriesFile = Join-Path $RoomDir "qa_retries"
                if (Test-Path $qaRetriesFile) { Remove-Item $qaRetriesFile -Force }
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Write-Log
# ---------------------------------------------------------------------------
function Write-Log {
    param([string]$Level, [string]$Message)
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level $Level -Message $Message
    } else {
        Write-Host "[MANAGER] $Message"
    }
}

# ---------------------------------------------------------------------------
# Write-SpawnLock
# ---------------------------------------------------------------------------
function Write-SpawnLock {
    param([string]$RoomDir, [string]$Role)
    $pidDir = Join-Path $RoomDir "pids"
    if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Path $pidDir -Force | Out-Null }
    $lockFile = Join-Path $pidDir "$Role.spawned_at"
    $epoch = [int][double]::Parse((Get-Date -UFormat %s))
    $epoch.ToString() | Out-File -FilePath $lockFile -Encoding utf8 -NoNewline
}

# ---------------------------------------------------------------------------
# Test-SpawnLock
# ---------------------------------------------------------------------------
function Test-SpawnLock {
    param([string]$RoomDir, [string]$Role, [int]$GracePeriodSeconds = 30)
    $lockFile = Join-Path $RoomDir "pids" "$Role.spawned_at"
    if (-not (Test-Path $lockFile)) { return $false }
    try {
        $spawnedAt = [int](Get-Content $lockFile -Raw).Trim()
        $now = [int][double]::Parse((Get-Date -UFormat %s))
        return (($now - $spawnedAt) -lt $GracePeriodSeconds)
    } catch { return $false }
}

# ---------------------------------------------------------------------------
# Start-WorkerJob
# ---------------------------------------------------------------------------
function Start-WorkerJob {
    param(
        [string]$RoomDir,
        [string]$Role,
        [string]$Script,
        [string]$TaskRef = '',
        [string]$RoleName = '',
        [switch]$SkipLockCheck
    )
    if (-not $SkipLockCheck) {
        if (Test-SpawnLock -RoomDir $RoomDir -Role $Role) {
            Write-Log "DEBUG" "[$TaskRef] Spawn lock active for '$Role' — skipping duplicate spawn."
            return $false
        }
        $existingPid = Join-Path $RoomDir "pids" "$Role.pid"
        if (Test-PidAlive $existingPid) {
            Write-Log "DEBUG" "[$TaskRef] Process already alive for '$Role' — skipping duplicate spawn."
            return $false
        }
    }
    Write-SpawnLock -RoomDir $RoomDir -Role $Role
    $effectiveRoleName = if ($RoleName) { $RoleName } else { $Role }
    # Detect whether the target script accepts -RoleName before passing it.
    # Scripts with [CmdletBinding()] will throw a terminating error on unknown
    # parameters, silently killing the Start-Job runspace with zero output.
    $acceptsRoleName = $false
    try {
        $scriptCmd = Get-Command $Script -ErrorAction SilentlyContinue
        if ($scriptCmd -and $scriptCmd.Parameters.ContainsKey('RoleName')) {
            $acceptsRoleName = $true
        }
    } catch { }
    Start-Job -ScriptBlock {
        param($s, $r, $rn, $passRn)
        if ($passRn -and $rn) { & $s -RoomDir $r -RoleName $rn } else { & $s -RoomDir $r }
    } -ArgumentList $Script, $RoomDir, $effectiveRoleName, $acceptsRoleName | Out-Null
    return $true
}

# ---------------------------------------------------------------------------
# Get-CachedDag
# ---------------------------------------------------------------------------
function Get-CachedDag {
    $dagFile        = _ctx 'dagFile'
    $script:dagCache = (_ctx 'dagCache')
    $script:dagMtime = (_ctx 'dagMtime')

    if (-not (Test-Path $dagFile)) { return $null }
    $mtime = (Get-Item $dagFile).LastWriteTimeUtc.Ticks
    if ($script:dagCache -and $script:dagMtime -eq $mtime) {
        return $script:dagCache
    }
    $newCache = Get-Content $dagFile -Raw | ConvertFrom-Json
    # Write back via context — callers update the ctx after call
    return $newCache
}

# ---------------------------------------------------------------------------
# Set-BlockedDescendants
# ---------------------------------------------------------------------------
function Set-BlockedDescendants {
    param([string]$FailedTaskRef)
    $hasDag      = _ctx 'hasDag'
    $WarRoomsDir = _ctx 'WarRoomsDir'

    if (-not $hasDag) { return }
    $dag = Get-CachedDag
    if (-not $dag) { return }

    $bfsQueue = [System.Collections.Queue]::new()
    $bfsQueue.Enqueue($FailedTaskRef)
    $visited = @{}

    while ($bfsQueue.Count -gt 0) {
        $current = $bfsQueue.Dequeue()
        if ($visited.ContainsKey($current)) { continue }
        $visited[$current] = $true

        $node = $dag.nodes.$current
        if (-not $node) { continue }
        $dependents = $node.dependents
        if (-not $dependents) { continue }
        foreach ($dep in $dependents) {
            $depNode = $dag.nodes.$dep
            if (-not $depNode) { continue }
            $depRoomDir = Join-Path $WarRoomsDir $depNode.room_id
            if (-not (Test-Path (Join-Path $depRoomDir "status"))) { continue }
            $depStatus = (Get-Content (Join-Path $depRoomDir "status") -Raw).Trim()
            if ($depStatus -eq "pending") {
                Write-Log "WARN" "[$dep] Blocked: upstream $FailedTaskRef failed"
                Write-RoomStatus $depRoomDir "blocked"
            }
            $bfsQueue.Enqueue($dep)
        }
    }
}

# ---------------------------------------------------------------------------
# Invoke-ManagerTriage
# ---------------------------------------------------------------------------
function Invoke-ManagerTriage {
    param([string]$RoomDir, [string]$QaFeedback)
    $agentsDir    = _ctx 'agentsDir'
    $config       = _ctx 'config'
    $readMessages = _ctx 'readMessages'

    if (-not $QaFeedback -or $QaFeedback.Trim() -eq '') { return 'no-feedback' }

    $designKeywords = 'architecture|design|scope|interface|contract|api-design|redesign|structural'
    $planKeywords   = 'specification|acceptance criteria|definition of done|brief|missing requirement|requirements|out of scope'
    if ($QaFeedback -match $designKeywords) { return 'design-issue' }
    if ($QaFeedback -match $planKeywords)   { return 'plan-gap' }

    $capabilityMatching = $true
    if ($null -ne $config.manager.capability_matching) { $capabilityMatching = $config.manager.capability_matching }

    $roomConfigFile = Join-Path $RoomDir "config.json"
    if (Test-Path $roomConfigFile) {
        $rc           = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
        $assignedRole = if ($rc.assignment -and $rc.assignment.assigned_role) { $rc.assignment.assigned_role } else { "engineer" }
        $baseRole     = $assignedRole -replace ':.*$', ''
        $overrideDir  = Join-Path $RoomDir (Join-Path "overrides" $baseRole)
        $roleDir      = if (Test-Path $overrideDir) { $overrideDir } else { Join-Path $agentsDir (Join-Path "roles" $baseRole) }
        $subcommandsFile = Join-Path $roleDir "subcommands.json"

        if (Test-Path $subcommandsFile) {
            $subcommands = Get-Content $subcommandsFile -Raw | ConvertFrom-Json
            $analyzeSubcommandScript = Join-Path $agentsDir "roles" "_base" "Analyze-SubcommandFailure.ps1"
            if (Test-Path $analyzeSubcommandScript) {
                try {
                    $analysis = & $analyzeSubcommandScript -QaFeedback $QaFeedback -Subcommands $subcommands
                    if ($analysis.Confidence -ge 0.7 -and $analysis.SubcommandName) {
                        return "subcommand-failure:$($analysis.SubcommandName)"
                    }
                } catch { }
            } else {
                foreach ($sc in $subcommands.subcommands.PSObject.Properties) {
                    $scName  = $sc.Name
                    $scEntry = $sc.Value.entrypoint
                    if ($QaFeedback -match $scName -or ($scEntry -and $QaFeedback -match (Split-Path $scEntry -Leaf))) {
                        return "subcommand-failure:$scName"
                    }
                }
            }
        }
    }

    if ($capabilityMatching) {
        $analyzeScript = Join-Path $agentsDir "roles" "_base" "Analyze-TaskRequirements.ps1"
        if (Test-Path $analyzeScript) {
            try {
                $analysis = & $analyzeScript -TaskDescription $QaFeedback -AgentsDir $agentsDir
                if ($analysis.Confidence -ge 0.6 -and $analysis.RequiredCapabilities.Count -gt 0) {
                    $specialistCaps = @('security', 'database', 'infrastructure', 'architecture')
                    $matched = $analysis.RequiredCapabilities | Where-Object { $_ -in $specialistCaps }
                    if ($matched -and $matched.Count -gt 0) { return 'design-issue' }
                }
            } catch { }
        }
    }

    $retries = if (Test-Path (Join-Path $RoomDir "retries")) {
        [int](Get-Content (Join-Path $RoomDir "retries") -Raw).Trim()
    } else { 0 }
    if ($retries -ge 2) {
        try {
            $failMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fail" -AsObject
            if ($failMsgs -and $failMsgs.Count -ge 2) {
                $prev      = $failMsgs[-2].body
                $curr      = $failMsgs[-1].body
                $prevWords = ($prev -split '\W+') | Where-Object { $_.Length -gt 3 } | Sort-Object -Unique
                $currWords = ($curr -split '\W+') | Where-Object { $_.Length -gt 3 } | Sort-Object -Unique
                if ($prevWords.Count -gt 0 -and $currWords.Count -gt 0) {
                    $overlap    = ($prevWords | Where-Object { $currWords -contains $_ }).Count
                    $maxSet     = [Math]::Max($prevWords.Count, $currWords.Count)
                    $similarity = $overlap / $maxSet
                    if ($similarity -ge 0.6) { return 'design-issue' }
                }
            }
        } catch { }
    }
    return 'implementation-bug'
}

# ---------------------------------------------------------------------------
# Write-TriageContext
# ---------------------------------------------------------------------------
function Write-TriageContext {
    param(
        [string]$RoomDir,
        [string]$Classification,
        [string]$QaFeedback,
        [string]$ArchitectGuidance,
        [string]$ManagerNotes
    )
    $artifactsDir = Join-Path $RoomDir "artifacts"
    if (-not (Test-Path $artifactsDir)) {
        New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
    }
    $contextFile = Join-Path $artifactsDir "triage-context.md"
    $actionLine  = switch ($Classification) {
        'implementation-bug' { "Engineer: Fix the specific issues listed in QA's report above." }
        'design-issue'       { "Engineer: Follow the architect's guidance above to redesign the approach." }
        'plan-gap'           { "Engineer: The brief has been updated. Re-read brief.md and implement accordingly." }
        default              { "Engineer: Address the issues identified above." }
    }
    $guidanceSection = if ($ArchitectGuidance) { $ArchitectGuidance } else { "_Not consulted — classified as implementation bug._" }
    $content = @"
# Manager Triage Context

## Classification: $Classification

## QA Failure Report
$QaFeedback

## Architect Guidance
$guidanceSection

## Manager's Direction
$ManagerNotes

## Action Required
$actionLine
"@
    $content | Out-File -FilePath $contextFile -Encoding utf8 -Force
}

# ---------------------------------------------------------------------------
# Handle-PlanApproval
# ---------------------------------------------------------------------------
function Handle-PlanApproval {
    param([string]$TaskRef)
    $agentsDir   = _ctx 'agentsDir'
    $WarRoomsDir = _ctx 'WarRoomsDir'

    if ($TaskRef -eq 'PLAN-REVIEW') {
        Write-Log "INFO" "[PLAN-REVIEW] Plan approved. Unblocking dependent rooms..."
        $buildDagScript = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"
        if (Test-Path $buildDagScript) {
            $null = & $buildDagScript -WarRoomsDir $WarRoomsDir
            # Signal cache invalidation to caller via context
            if ($script:_ctx) { $script:_ctx['dagCache'] = $null }
        }
    }
}

Export-ModuleMember -Function *
