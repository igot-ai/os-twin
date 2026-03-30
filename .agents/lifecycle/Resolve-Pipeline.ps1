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
        [string]$PrimaryRole,           # Who does the work (developing/optimize)
        [string[]]$ReviewChain = @(),   # Ordered reviewer roles (may be empty)
        [int]$MaxRetries = 3
    )

    $states = [ordered]@{}

    # --- Determine review chain targets ---
    # developing.done → first reviewer (or review if no chain)
    # optimize.done   → first reviewer (or review if no chain)
    # Each reviewer.pass → next reviewer or "review" (final gate) or "passed"

    $hasExplicitReviewers = $ReviewChain.Count -gt 0
    $firstReviewTarget = if ($hasExplicitReviewers) {
        "$($ReviewChain[0])-review"
    } else {
        'review'
    }

    # --- developing: primary role does initial implementation ---
    $states['developing'] = [ordered]@{
        role    = $PrimaryRole
        type    = 'work'
        signals = [ordered]@{
            done  = [ordered]@{ target = $firstReviewTarget }
            error = [ordered]@{ target = 'failed'; actions = @('increment_retries') }
        }
    }

    # --- optimize: primary role fixes after review feedback ---
    $states['optimize'] = [ordered]@{
        role    = $PrimaryRole
        type    = 'work'
        signals = [ordered]@{
            done  = [ordered]@{ target = $firstReviewTarget }
            error = [ordered]@{ target = 'failed'; actions = @('increment_retries') }
        }
    }

    # --- Review chain: each reviewer in sequence ---
    for ($i = 0; $i -lt $ReviewChain.Count; $i++) {
        $reviewer = $ReviewChain[$i]
        $stateName = "$reviewer-review"

        # Determine pass target: next reviewer, or final "review", or "passed"
        $passTarget = if ($i -lt ($ReviewChain.Count - 1)) {
            "$($ReviewChain[$i + 1])-review"
        } else {
            # Last in chain — goes to final QA review (unless this IS qa)
            if ($reviewer -eq 'qa') { 'passed' } else { 'review' }
        }

        $states[$stateName] = [ordered]@{
            role    = $reviewer
            type    = 'review'
            signals = [ordered]@{
                pass     = [ordered]@{ target = $passTarget }
                fail     = [ordered]@{ target = 'optimize'; actions = @('increment_retries', 'post_fix') }
                escalate = [ordered]@{ target = 'triage' }
            }
        }
    }

    # --- review: final QA gate (if qa not already in the chain) ---
    $qaInChain = $ReviewChain -contains 'qa'
    if (-not $qaInChain) {
        $states['review'] = [ordered]@{
            role    = 'qa'
            type    = 'review'
            signals = [ordered]@{
                pass     = [ordered]@{ target = 'passed' }
                fail     = [ordered]@{ target = 'developing'; actions = @('increment_retries', 'post_fix') }
                escalate = [ordered]@{ target = 'triage' }
            }
        }
    }

    # --- triage: manager handles escalations ---
    $states['triage'] = [ordered]@{
        role    = 'manager'
        type    = 'triage'
        signals = [ordered]@{
            fix      = [ordered]@{ target = 'developing'; actions = @('increment_retries') }
            redesign = [ordered]@{ target = 'developing'; actions = @('increment_retries', 'revise_brief') }
            reject   = [ordered]@{ target = 'failed-final' }
        }
    }

    # --- failed: auto-decision node ---
    $states['failed'] = [ordered]@{
        role            = 'manager'
        type            = 'decision'
        auto_transition = $true
        signals         = [ordered]@{
            retry   = [ordered]@{ target = 'developing'; guard = 'retries < max_retries' }
            exhaust = [ordered]@{ target = 'failed-final'; guard = 'retries >= max_retries' }
        }
    }

    # --- terminal states ---
    $states['passed']       = [ordered]@{ type = 'terminal' }
    $states['failed-final'] = [ordered]@{ type = 'terminal' }

    return [ordered]@{
        version       = 2
        initial_state = 'developing'
        max_retries   = $MaxRetries
        states        = $states
    }
}

# ------------------------------------------------------------------
# MODE 1: Explicit pipeline string  (e.g., "engineer -> security-review -> qa")
# ------------------------------------------------------------------
if ($PipelineString) {
    $segments = ($PipelineString -split '\s*->\s*') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    
    $primaryRole = $segments[0]
    $reviewers = @()
    if ($segments.Count -gt 1) {
        $reviewers = @($segments[1..($segments.Count - 1)])
    }

    $lifecycle = Build-LifecycleV2 -PrimaryRole $primaryRole -ReviewChain $reviewers -MaxRetries $MaxRetries
}
# ------------------------------------------------------------------
# MODE 2: CandidateRoles from DAG (preferred)
# ------------------------------------------------------------------
elseif ($CandidateRoles.Count -gt 0) {
    $primaryRole = $CandidateRoles[0]
    $orchestratorRoles = @('manager')
    $reviewers = @()
    if ($CandidateRoles.Count -gt 1) {
        $reviewers = @($CandidateRoles[1..($CandidateRoles.Count - 1)] | Where-Object { $_ -notin $orchestratorRoles })
    }

    $lifecycle = Build-LifecycleV2 -PrimaryRole $primaryRole -ReviewChain $reviewers -MaxRetries $MaxRetries
}
# ------------------------------------------------------------------
# MODE 3: Capability-derived pipeline
# ------------------------------------------------------------------
elseif ($RequiredCapabilities.Count -gt 0) {
    $baseRole = $AssignedRole -replace ':.*$', ''

    $capReviewerMap = @{
        'security'       = 'security-auditor'
        'database'       = 'database-architect'
        'architecture'   = 'architect'
        'infrastructure' = 'devops'
        'accessibility'  = 'accessibility-specialist'
    }

    $reviewers = [System.Collections.Generic.List[string]]::new()
    foreach ($cap in $RequiredCapabilities) {
        $capLower = $cap.ToLower()
        if ($capReviewerMap.ContainsKey($capLower)) {
            $reviewers.Add($capReviewerMap[$capLower])
        }
    }
    # QA is added automatically by Build-LifecycleV2 if not in chain

    $lifecycle = Build-LifecycleV2 -PrimaryRole $baseRole -ReviewChain $reviewers.ToArray() -MaxRetries $MaxRetries
}
# ------------------------------------------------------------------
# MODE 4: Default lifecycle fallback
# ------------------------------------------------------------------
else {
    if (Test-Path $defaultLifecyclePath) {
        $lifecycle = Get-Content $defaultLifecyclePath -Raw | ConvertFrom-Json
    } else {
        $lifecycle = Build-LifecycleV2 -PrimaryRole $AssignedRole -ReviewChain @() -MaxRetries $MaxRetries
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