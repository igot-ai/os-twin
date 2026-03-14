<#
.SYNOPSIS
    Architect role runner — reviews QA failures and provides design guidance.

.DESCRIPTION
    When QA fails a war-room and the manager classifies the failure as a
    design issue or plan gap, this script spawns the architect agent to
    analyze the failure and provide guidance.

    Reads QA feedback, engineer output, and original brief, then invokes
    the architect agent to classify and recommend: FIX, REDESIGN, or REPLAN.

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER TimeoutSeconds
    Override timeout. Default: from config.

.EXAMPLE
    ./Start-Architect.ps1 -RoomDir "./war-rooms/room-001"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [int]$TimeoutSeconds = 0
)

# --- Resolve paths ---
$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir ".." "..")).Path
$channelDir = Join-Path $agentsDir "channel"
$invokeAgent = Join-Path $agentsDir "roles" "_base" "Invoke-Agent.ps1"
$postMessage = Join-Path $channelDir "Post-Message.ps1"
$readMessages = Join-Path $channelDir "Read-Messages.ps1"

# --- Import logging ---
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
if (Test-Path $logModule) { Import-Module $logModule -Force }

# --- Load config ---
$configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
              else { Join-Path $agentsDir "config.json" }

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if ($TimeoutSeconds -eq 0 -and $config.architect -and $config.architect.timeout_seconds) {
        $TimeoutSeconds = $config.architect.timeout_seconds
    }
}
if ($TimeoutSeconds -eq 0) { $TimeoutSeconds = 300 }

# --- Read/Create per-role config file (architect_{id}.json) ---
$archConfigs = Get-ChildItem -Path $RoomDir -Filter "architect_*.json" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
if ($archConfigs) {
    $archRoleConfig = Get-Content $archConfigs[0].FullName -Raw | ConvertFrom-Json
    $archRoleConfig.status = "active"
    $archRoleConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $archConfigs[0].FullName -Encoding utf8
    $archRoleConfigFile = $archConfigs[0].FullName
}
else {
    $archModel = "gemini-3-flash-preview"
    if ($config -and $config.architect -and $config.architect.default_model) {
        $archModel = $config.architect.default_model
    }
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $archRoleConfigObj = [ordered]@{
        role          = "architect"
        instance_id   = "001"
        instance_type = ""
        display_name  = "architect #001"
        model         = $archModel
        assigned_at   = $ts
        status        = "active"
        config_override = [ordered]@{}
    }
    $archRoleConfigFile = Join-Path $RoomDir "architect_001.json"
    $archRoleConfigObj | ConvertTo-Json -Depth 5 | Out-File -FilePath $archRoleConfigFile -Encoding utf8
}

# --- Read task ref ---
$taskRef = if (Test-Path (Join-Path $RoomDir "task-ref")) {
    (Get-Content (Join-Path $RoomDir "task-ref") -Raw).Trim()
} else { "UNKNOWN" }

# --- Read the original brief ---
$taskDesc = if (Test-Path (Join-Path $RoomDir "brief.md")) {
    Get-Content (Join-Path $RoomDir "brief.md") -Raw
} else { "No task description found." }

# --- Read the engineer's latest done message ---
$engineerReport = "No engineer report found."
try {
    $doneMsgs = & $readMessages -RoomDir $RoomDir -FilterType "done" -Last 1 -AsObject
    if ($doneMsgs -and $doneMsgs.Count -gt 0) {
        $engineerReport = $doneMsgs[-1].body
    }
}
catch { }

# --- Read QA failure or escalation ---
$qaFeedback = "No QA feedback found."
try {
    # Check for escalate first, then fail
    $escalateMsgs = & $readMessages -RoomDir $RoomDir -FilterType "escalate" -Last 1 -AsObject
    if ($escalateMsgs -and $escalateMsgs.Count -gt 0) {
        $qaFeedback = $escalateMsgs[-1].body
    } else {
        $failMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fail" -Last 1 -AsObject
        if ($failMsgs -and $failMsgs.Count -gt 0) {
            $qaFeedback = $failMsgs[-1].body
        }
    }
}
catch { }

# --- Read manager's design-review request ---
$managerRequest = ""
try {
    $designMsgs = & $readMessages -RoomDir $RoomDir -FilterType "design-review" -Last 1 -AsObject
    if ($designMsgs -and $designMsgs.Count -gt 0) {
        $managerRequest = $designMsgs[-1].body
    }
}
catch { }

# --- Read role prompt ---
$rolePrompt = if (Test-Path (Join-Path $scriptDir "ROLE.md")) {
    Get-Content (Join-Path $scriptDir "ROLE.md") -Raw
} else { "" }

# --- Build the full prompt ---
$prompt = @"
$rolePrompt

---

## Context: QA Failure Triage for $taskRef

You are being called in because QA has failed the engineer's implementation,
and the manager has classified this as a potential design or scope issue.

## Original Brief

$taskDesc

## Engineer's Submission

$engineerReport

## QA's Failure Report

$qaFeedback

## Manager's Request

$managerRequest

## Instructions

Analyze the failure and determine whether this is:
1. An **implementation bug** that the engineer can fix with specific guidance
2. An **architectural/design flaw** that requires a fundamentally different approach
3. A **scope/requirements gap** where the brief or acceptance criteria need updating

Your response MUST include exactly one of these lines:
  RECOMMENDATION: FIX
  RECOMMENDATION: REDESIGN
  RECOMMENDATION: REPLAN

Follow with detailed guidance:
- For FIX: specific code-level guidance for the engineer
- For REDESIGN: the new architectural approach to follow
- For REPLAN: what needs to change in the brief, DoD, or acceptance criteria
"@

# --- Log start ---
if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
    Write-OstwinLog -Level INFO -Message "Starting architect review of $taskRef in $(Split-Path $RoomDir -Leaf)"
}
else {
    Write-Host "[ARCHITECT] Starting review of $taskRef in $(Split-Path $RoomDir -Leaf)"
}

# --- Run the agent ---
$result = & $invokeAgent -RoomDir $RoomDir -RoleName "architect" `
                         -Prompt $prompt -TimeoutSeconds $TimeoutSeconds

# --- Parse recommendation from output ---
$output = $result.Output
$recommendation = ""

# Strategy 1: line starts with RECOMMENDATION:
if ($output -match '(?m)^RECOMMENDATION:\s*(FIX|REDESIGN|REPLAN)') {
    $recommendation = $Matches[1].ToUpper()
}

# Strategy 2: RECOMMENDATION: anywhere in a line
if (-not $recommendation -and $output -match 'RECOMMENDATION:\s*(FIX|REDESIGN|REPLAN)') {
    $recommendation = $Matches[1].ToUpper()
}

# Strategy 3: default to FIX if no recommendation found
if (-not $recommendation) {
    $recommendation = "FIX"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level WARN -Message "Could not parse recommendation for $taskRef. Defaulting to FIX."
    }
}

# --- Post result to channel ---
if ($result.TimedOut) {
    & $postMessage -RoomDir $RoomDir -From "architect" -To "manager" `
                   -Type "error" -Ref $taskRef -Body "Architect timed out after ${TimeoutSeconds}s"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level ERROR -Message "Timed out on $taskRef after ${TimeoutSeconds}s."
    }
}
else {
    & $postMessage -RoomDir $RoomDir -From "architect" -To "manager" `
                   -Type "design-guidance" -Ref $taskRef -Body $output
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level INFO -Message "Architect review complete for $taskRef. Recommendation: $recommendation"
    }
}

# --- Clean up PID file ---
$archPidFile = Join-Path $RoomDir "pids" "architect.pid"
Remove-Item $archPidFile -Force -ErrorAction SilentlyContinue

# --- Update per-role config status ---
if (Test-Path $archRoleConfigFile) {
    $archFinalConfig = Get-Content $archRoleConfigFile -Raw | ConvertFrom-Json
    $archFinalConfig.status = if ($result.ExitCode -eq 0) { "completed" } else { "failed" }
    $archFinalConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $archRoleConfigFile -Encoding utf8
}

exit $result.ExitCode
