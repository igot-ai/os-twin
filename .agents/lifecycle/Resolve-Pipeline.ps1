<#
.SYNOPSIS
    Generates a lifecycle.json (v2) for a war-room based on explicit pipeline,
    capabilities, candidate roles, or default fallback.
 
.PARAMETER PipelineString
    Explicit pipeline like "engineer -> security-review -> qa".
.PARAMETER RequiredCapabilities
    Array of capabilities. Used to insert review stages.
.PARAMETER AssignedRole
    The primary role. Used for role-derived pipeline generation.
.PARAMETER CandidateRoles
    Ordered list of candidate roles from DAG.json. [0] = primary worker,
    [1..N] = reviewers. Takes precedence over RequiredCapabilities.
.PARAMETER MaxRetries
    Max retries for the lifecycle. Default: 3.
.PARAMETER OutputPath
    Where to write the lifecycle.json. If empty, outputs JSON to stdout.
.PARAMETER AgentsDir
    Path to the .agents directory.
 
.OUTPUTS
    JSON string (lifecycle definition) or writes to OutputPath.
#>
[CmdletBinding()]
param(
    [string]$PipelineString = '',
    [string[]]$RequiredCapabilities = @(),
    [string]$AssignedRole = 'engineer',
    [string[]]$CandidateRoles = @(),
    [int]$MaxRetries = 3,
    [string]$OutputPath = '',
    [string]$AgentsDir = ''
)
 
if (-not $AgentsDir) {
    $AgentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
 
$defaultLifecyclePath = Join-Path $AgentsDir "lifecycle" "default.json"
 
# ------------------------------------------------------------------
# V2 LIFECYCLE BUILDER — signal-based, role-per-state state machine
# ------------------------------------------------------------------
function Build-LifecycleV2 {
    param(
        [PSCustomObject[]]$RoleOverrides, # Array of @{ Name, InstanceType }
        [int]$MaxRetries = 3
    )

    $states = [ordered]@{}
    $firstState = $null
    $lastWorkerOptimize = $null

    # Pre-compute state names
    $stateNames = @()
    $hasReview = $false
    for ($i = 0; $i -lt $RoleOverrides.Count; $i++) {
        $type = $RoleOverrides[$i].InstanceType
        $roleName = $RoleOverrides[$i].Name
        if ($i -eq 0 -and $type -ne 'evaluator') {
            $stateNames += "developing"
        } elseif ($type -eq 'evaluator') {
            if (-not $hasReview) {
                $stateNames += "review"
                $hasReview = $true
            } else {
                $stateNames += "review-$roleName"
            }
        } else {
            $stateNames += $roleName
        }
    }

    for ($i = 0; $i -lt $RoleOverrides.Count; $i++) {
        $roleInfo = $RoleOverrides[$i]
        $roleName = $roleInfo.Name
        $type = $roleInfo.InstanceType

        $isFirstWorker = ($i -eq 0 -and $type -ne 'evaluator')
        $stateName = $stateNames[$i]
        if (-not $firstState) { $firstState = $stateName }

        $nextTarget = 'passed'
        if ($i -lt ($RoleOverrides.Count - 1)) {
            $nextTarget = $stateNames[$i + 1]
        }

        if ($type -eq 'worker') {
            # worker state
            $optimizeState = if ($isFirstWorker) { "optimize" } else { "optimize-$roleName" }
            $lastWorkerOptimize = $optimizeState

            $states[$stateName] = [ordered]@{
                role    = $roleName
                type    = 'work'
                signals = [ordered]@{
                    done  = [ordered]@{ target = $nextTarget }
                    pass  = [ordered]@{ target = $nextTarget }
                    error = [ordered]@{ target = 'failed'; actions = @('increment_retries') }
                }
            }

            # optimize state
            $states[$optimizeState] = [ordered]@{
                role    = $roleName
                type    = 'work'
                signals = [ordered]@{
                    done  = [ordered]@{ target = $nextTarget }
                    pass  = [ordered]@{ target = $nextTarget }
                    error = [ordered]@{ target = 'failed'; actions = @('increment_retries') }
                }
            }
        } else {
            # evaluator state
            $failTarget = if ($lastWorkerOptimize) { $lastWorkerOptimize } else { "failed" }

            $states[$stateName] = [ordered]@{
                role    = $roleName
                type    = 'review'
                signals = [ordered]@{
                    pass     = [ordered]@{ target = $nextTarget }
                    done     = [ordered]@{ target = 'passed' }
                    fail     = [ordered]@{ target = $failTarget; actions = @('increment_retries', 'post_fix') }
                    escalate = [ordered]@{ target = 'triage' }
                }
            }
        }
    }

    # --- triage: manager handles escalations ---
    $states['triage'] = [ordered]@{
        role    = 'manager'
        type    = 'triage'
        signals = [ordered]@{
            fix      = [ordered]@{ target = if ($lastWorkerOptimize) { $lastWorkerOptimize } else { 'failed' }; actions = @('increment_retries') }
            redesign = [ordered]@{ target = if ($firstState) { $firstState } else { 'failed' }; actions = @('increment_retries', 'revise_brief') }
            reject   = [ordered]@{ target = 'failed-final' }
        }
    }

    # --- failed: auto-decision node ---
    $states['failed'] = [ordered]@{
        role            = 'manager'
        type            = 'decision'
        auto_transition = $true
        signals         = [ordered]@{
            retry   = [ordered]@{ target = if ($firstState) { $firstState } else { 'failed-final' }; guard = 'retries < max_retries' }
            exhaust = [ordered]@{ target = 'failed-final'; guard = 'retries >= max_retries' }
        }
    }

    # --- terminal states ---
    $states['passed']       = [ordered]@{ type = 'terminal' }
    $states['failed-final'] = [ordered]@{ type = 'terminal' }

    return [ordered]@{
        version       = 2
        initial_state = if ($firstState) { $firstState } else { 'passed' }
        max_retries   = $MaxRetries
        states        = $states
    }
}

# ------------------------------------------------------------------
# RESOLVE ROLES
# ------------------------------------------------------------------
$resolver = Join-Path $AgentsDir "roles" "_base" "Resolve-Role.ps1"
$candidateList = @()

# MODE 1: Explicit pipeline string
if ($PipelineString) {
    $candidateList = @(($PipelineString -split '\s*->\s*') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
# MODE 2: CandidateRoles from DAG
elseif ($CandidateRoles.Count -gt 0) {
    $orchestratorRoles = @('manager')
    $candidateList = @($CandidateRoles | Where-Object { $_ -notin $orchestratorRoles })
}
# MODE 3: Capability-derived pipeline
elseif ($RequiredCapabilities.Count -gt 0) {
    $baseRole = $AssignedRole -replace ':.*$', ''
    $capReviewerMap = @{
        'security'       = 'security-auditor'
        'database'       = 'database-architect'
        'architecture'   = 'architect'
        'infrastructure' = 'devops'
        'accessibility'  = 'accessibility-specialist'
    }
    $candidateList = @($baseRole)
    foreach ($cap in $RequiredCapabilities) {
        $capLower = $cap.ToLower()
        if ($capReviewerMap.ContainsKey($capLower)) {
            $candidateList += $capReviewerMap[$capLower]
        }
    }
}
# MODE 4: Default fallback
else {
    if (Test-Path $defaultLifecyclePath) {
        $resolvedLifecycle = Get-Content $defaultLifecyclePath -Raw | ConvertFrom-Json
    } else {
        $candidateList = @($AssignedRole)
    }
}

if (-not $resolvedLifecycle -and $candidateList.Count -gt 0) {
    $roleOverrides = @()
    foreach ($role in $candidateList) {
        $baseRole = $role -replace ':.*$', ''
        $roleJsonPath = Join-Path $AgentsDir "roles" $baseRole "role.json"
        $instanceType = 'worker'

        if (Test-Path $roleJsonPath) {
            $roleConfig = Get-Content $roleJsonPath -Raw | ConvertFrom-Json
            if ($roleConfig.instance_type) { $instanceType = $roleConfig.instance_type }
        } else {
            $contribPath = Join-Path $AgentsDir "contributes" $baseRole "role.json"
            if (Test-Path $contribPath) {
                $roleConfig = Get-Content $contribPath -Raw | ConvertFrom-Json
                if ($roleConfig.instance_type) { $instanceType = $roleConfig.instance_type }
            }
        }

        $roleOverrides += [PSCustomObject]@{
            Name         = $role
            InstanceType = $instanceType
        }
    }
    $resolvedLifecycle = Build-LifecycleV2 -RoleOverrides $roleOverrides -MaxRetries $MaxRetries
}

# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------
$json = $resolvedLifecycle | ConvertTo-Json -Depth 10
 
if ($OutputPath) {
    $json | Out-File -FilePath $OutputPath -Encoding utf8 -Force
} else {
    Write-Output $json
}