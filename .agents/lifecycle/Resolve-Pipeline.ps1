<#
.SYNOPSIS
    Generates a lifecycle.json for a war-room based on explicit pipeline,
    capabilities, or default fallback.
 
.PARAMETER PipelineString
    Explicit pipeline like "engineer -> security-review -> qa".
    Each segment becomes a state. The last segment's "done" transitions to "passed".
.PARAMETER RequiredCapabilities
    Array of capabilities. Used to insert review stages.
.PARAMETER AssignedRole
    The primary role. Used for role-derived pipeline generation.
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
    [string]$OutputPath = '',
    [string]$AgentsDir = ''
)
 
if (-not $AgentsDir) {
    $AgentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
 
$defaultLifecyclePath = Join-Path $AgentsDir "lifecycle" "default.json"
 
# ------------------------------------------------------------------
# HELPER: Build lifecycle from an ordered list of stage definitions
# ------------------------------------------------------------------
function New-LinearPipeline {
    param(
        [PSCustomObject[]]$Stages  # Each: { StateName, Role, Type }
    )
    $states = [ordered]@{}
    for ($i = 0; $i -lt $Stages.Count; $i++) {
        $stage = $Stages[$i]
        $stateName = $stage.StateName
        $nextStateName = $null
 
        # Determine what "done"/"pass" transitions to
        if ($i -lt ($Stages.Count - 1)) {
            $nextStateName = $Stages[$i + 1].StateName
        } else {
            $nextStateName = 'passed'
        }
 
        $transitions = [ordered]@{}
        if ($stage.Type -eq 'review') {
            # Review stages emit pass/fail/escalate
            $transitions['pass'] = $nextStateName
            $transitions['fail'] = 'manager-triage'
            $transitions['escalate'] = 'manager-triage'
        } else {
            # Worker stages emit done
            $transitions['done'] = $nextStateName
        }
 
        $states[$stateName] = [ordered]@{
            type        = 'agent'
            role        = $stage.Role
            transitions = $transitions
        }
    }
 
    # Always include builtin states for triage and plan-revision
    $states['manager-triage'] = [ordered]@{
        type        = 'builtin'
        role        = 'manager'
        transitions = [ordered]@{}
    }
    $states['plan-revision'] = [ordered]@{
        type        = 'builtin'
        role        = 'manager'
        transitions = [ordered]@{}
    }
 
    # fixing state — routes back to the first review stage (or passed)
    $firstReview = $Stages | Where-Object { $_.Type -eq 'review' } | Select-Object -First 1
    $fixTarget = if ($firstReview) { $firstReview.StateName } else { 'passed' }
    $states['fixing'] = [ordered]@{
        type        = 'agent'
        role        = $Stages[0].Role  # Primary role does the fixing
        transitions = [ordered]@{ done = $fixTarget }
    }
 
    $initialState = $Stages[0].StateName
 
    return [ordered]@{
        initial_state = $initialState
        states        = $states
    }
}
 
# ------------------------------------------------------------------
# MODE 1: Explicit pipeline string  (e.g., "engineer -> security-review -> qa")
# ------------------------------------------------------------------
if ($PipelineString) {
    $segments = ($PipelineString -split '\s*->\s*') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
 
    $stages = [System.Collections.Generic.List[PSObject]]::new()
    foreach ($seg in $segments) {
        # Heuristic: if segment contains "review", "qa", "audit", "check", treat as review stage
        $isReview = $seg -match '(review|qa|audit|check|validate|verify|test)'
        $stateName = $seg -replace ':', '-'  # Normalize colons for state names
 
        $stages.Add([PSCustomObject]@{
            StateName = $stateName
            Role      = $seg
            Type      = if ($isReview) { 'review' } else { 'worker' }
        })
    }
 
    $lifecycle = New-LinearPipeline -Stages $stages.ToArray()
}
# ------------------------------------------------------------------
# MODE 2: Capability-derived pipeline (insert review stages for each capability)
# ------------------------------------------------------------------
elseif ($RequiredCapabilities.Count -gt 0) {
    $stages = [System.Collections.Generic.List[PSObject]]::new()
 
    # Primary work stage
    $baseRole = $AssignedRole -replace ':.*$', ''
    $stages.Add([PSCustomObject]@{
        StateName = 'engineering'
        Role      = $AssignedRole
        Type      = 'worker'
    })
 
    # Insert specialized review stages for notable capabilities
    $reviewCapabilities = @{
        'security'       = @{ StateName = 'security-review';  Role = 'security-auditor' }
        'database'       = @{ StateName = 'schema-review';    Role = 'database-architect' }
        'architecture'   = @{ StateName = 'architect-review'; Role = 'architect' }
        'infrastructure' = @{ StateName = 'infra-review';     Role = 'devops' }
        'accessibility'  = @{ StateName = 'a11y-review';      Role = 'accessibility-specialist' }
    }
 
    foreach ($cap in $RequiredCapabilities) {
        $capLower = $cap.ToLower()
        if ($reviewCapabilities.ContainsKey($capLower)) {
            $rc = $reviewCapabilities[$capLower]
            $stages.Add([PSCustomObject]@{
                StateName = $rc.StateName
                Role      = $rc.Role
                Type      = 'review'
            })
        }
    }
 
    # Always end with QA and Reporting
    $stages.Add([PSCustomObject]@{
        StateName = 'qa-review'
        Role      = 'qa'
        Type      = 'review'
    })
    $stages.Add([PSCustomObject]@{
        StateName = 'reporting'
        Role      = 'reporter'
        Type      = 'worker'
    })
 
    $lifecycle = New-LinearPipeline -Stages $stages.ToArray()
}
# ------------------------------------------------------------------
# MODE 3: Default lifecycle fallback
# ------------------------------------------------------------------
else {
    if (Test-Path $defaultLifecyclePath) {
        $lifecycle = Get-Content $defaultLifecyclePath -Raw | ConvertFrom-Json
    } else {
        # Hardcoded minimal default
        $lifecycle = New-LinearPipeline -Stages @(
            [PSCustomObject]@{ StateName = 'engineering'; Role = $AssignedRole; Type = 'worker' },
            [PSCustomObject]@{ StateName = 'qa-review';   Role = 'qa';         Type = 'review' },
            [PSCustomObject]@{ StateName = 'reporting';   Role = 'reporter';   Type = 'worker' }
        )
    }
}
 
# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------
$json = $lifecycle | ConvertTo-Json -Depth 10
 
if ($OutputPath) {
    $json | Out-File -FilePath $OutputPath -Encoding utf8 -Force
} else {
    Write-Output $json
}