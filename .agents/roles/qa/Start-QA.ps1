<#
.SYNOPSIS
    QA role runner — reviews engineer output and posts pass/fail verdict.

.DESCRIPTION
    Reads the engineer's "done" message from the channel, builds a QA review
    prompt, runs the agent via Invoke-Agent.ps1, parses VERDICT from output,
    and posts pass/fail/error back to the channel.

    Replaces: roles/qa/run.sh

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER TimeoutSeconds
    Override timeout. Default: from config.

.EXAMPLE
    ./Start-QA.ps1 -RoomDir "./war-rooms/room-001"
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
    if ($TimeoutSeconds -eq 0) {
        $TimeoutSeconds = $config.qa.timeout_seconds
    }
}
if ($TimeoutSeconds -eq 0) { $TimeoutSeconds = 300 }

# --- Read/Create per-role config file (qa_{id}.json) ---
$qaConfigs = Get-ChildItem -Path $RoomDir -Filter "qa_*.json" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
if ($qaConfigs) {
    # Existing QA config — update status to active
    $qaRoleConfig = Get-Content $qaConfigs[0].FullName -Raw | ConvertFrom-Json
    $qaRoleConfig.status = "active"
    $qaRoleConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $qaConfigs[0].FullName -Encoding utf8
    $qaRoleConfigFile = $qaConfigs[0].FullName
}
else {
    # First QA assignment — create qa_001.json
    $qaModel = "gemini-3-flash-preview"
    if ($config -and $config.qa.default_model) {
        $qaModel = $config.qa.default_model
    }
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $qaRoleConfigObj = [ordered]@{
        role          = "qa"
        instance_id   = "001"
        instance_type = ""
        display_name  = "qa #001"
        model         = $qaModel
        assigned_at   = $ts
        status        = "active"
        config_override = [ordered]@{}
    }
    $qaRoleConfigFile = Join-Path $RoomDir "qa_001.json"
    $qaRoleConfigObj | ConvertTo-Json -Depth 5 | Out-File -FilePath $qaRoleConfigFile -Encoding utf8
}

# --- Read task ref ---
$taskRef = if (Test-Path (Join-Path $RoomDir "task-ref")) {
    (Get-Content (Join-Path $RoomDir "task-ref") -Raw).Trim()
} else { "UNKNOWN" }

# --- Detect Epic vs Task ---
$isEpic = $taskRef -match '^EPIC-'

# --- Read the engineer's "done" message ---
$engineerReport = "No engineer report found."
try {
    $doneMsgs = & $readMessages -RoomDir $RoomDir -FilterType "done" -Last 1 -AsObject
    if ($doneMsgs -and $doneMsgs.Count -gt 0) {
        $engineerReport = $doneMsgs[-1].body
    }
}
catch { }

# --- Read original task ---
$taskDesc = if (Test-Path (Join-Path $RoomDir "brief.md")) {
    Get-Content (Join-Path $RoomDir "brief.md") -Raw
} else { "No task description found." }

# --- Read TASKS.md for Epic reviews ---
$tasksMd = ""
if ($isEpic) {
    $tasksFile = Join-Path $RoomDir "TASKS.md"
    if (Test-Path $tasksFile) {
        $tasksMd = Get-Content $tasksFile -Raw
    }
}

# --- Read role prompt ---
$rolePrompt = if (Test-Path (Join-Path $scriptDir "ROLE.md")) {
    Get-Content (Join-Path $scriptDir "ROLE.md") -Raw
} else { "" }

# --- Build Epic-specific sections ---
$tasksSection = ""
if ($isEpic -and $tasksMd) {
    $tasksSection = @"

## Engineer's Task Breakdown (TASKS.md)

$tasksMd
"@
}

# --- Build review instructions ---
if ($isEpic) {
    $reviewInstructions = @"
You are reviewing an EPIC — a complete feature delivered by the engineer.

1. Review ALL code changes holistically across the full epic
2. Verify the TASKS.md checklist is complete — all sub-tasks must be checked off
3. Verify each sub-task was actually implemented (not just checked off)
4. Run the project test suite
5. Validate the epic delivers the feature described in the brief
6. Provide your verdict
"@
}
else {
    $reviewInstructions = @"
1. Review the code changes described in the engineer's report
2. Verify the implementation meets the task requirements
3. Run tests if applicable
4. Provide your verdict
"@
}

# --- Build the full prompt ---
$prompt = @"
$rolePrompt

---

## Original Assignment

$taskDesc

## Engineer's Report

$engineerReport
$tasksSection
## Instructions

$reviewInstructions

IMPORTANT: Your response MUST include exactly one of these lines:
  VERDICT: PASS
  VERDICT: FAIL
  VERDICT: ESCALATE

Use ESCALATE when the failure is NOT an implementation bug — e.g., the requirements
are wrong, the architecture is fundamentally flawed, or the acceptance criteria are
incomplete. Include a classification: DESIGN | SCOPE | REQUIREMENTS.

Follow with detailed reasoning.
"@

# --- Log start ---
if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
    Write-OstwinLog -Level INFO -Message "Starting review of $taskRef in $(Split-Path $RoomDir -Leaf)"
}
else {
    Write-Host "[QA] Starting review of $taskRef in $(Split-Path $RoomDir -Leaf)"
}

# --- Run the agent ---
$result = & $invokeAgent -RoomDir $RoomDir -RoleName "qa" `
                         -Prompt $prompt -TimeoutSeconds $TimeoutSeconds

# --- Parse verdict from output ---
$output = $result.Output
$verdict = ""

# Strategy 1: Line starts with VERDICT:
if ($output -match '(?m)^VERDICT:\s*(PASS|FAIL|ESCALATE)') {
    $verdict = $Matches[1].ToUpper()
}

# Strategy 2: VERDICT: anywhere in a line
if (-not $verdict -and $output -match 'VERDICT:\s*(PASS|FAIL|ESCALATE)') {
    $verdict = $Matches[1].ToUpper()
}

# Strategy 3: standalone PASS/FAIL/ESCALATE in first 20 lines
if (-not $verdict) {
    $first20 = ($output -split "`n" | Select-Object -First 20) -join "`n"
    if ($first20 -match '\b(PASS|FAIL|ESCALATE)\b') {
        $verdict = $Matches[1].ToUpper()
    }
}

# --- Post result to channel ---
if ($result.TimedOut) {
    & $postMessage -RoomDir $RoomDir -From "qa" -To "manager" `
                   -Type "error" -Ref $taskRef -Body "QA timed out after ${TimeoutSeconds}s"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level ERROR -Message "Timed out on $taskRef after ${TimeoutSeconds}s."
    }
}
elseif ($verdict -eq "PASS") {
    & $postMessage -RoomDir $RoomDir -From "qa" -To "manager" `
                   -Type "pass" -Ref $taskRef -Body $output
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level INFO -Message "PASSED $taskRef."
    }
}
elseif ($verdict -eq "FAIL") {
    & $postMessage -RoomDir $RoomDir -From "qa" -To "manager" `
                   -Type "fail" -Ref $taskRef -Body $output
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level INFO -Message "FAILED $taskRef."
    }
}
elseif ($verdict -eq "ESCALATE") {
    & $postMessage -RoomDir $RoomDir -From "qa" -To "manager" `
                   -Type "escalate" -Ref $taskRef -Body $output
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level WARN -Message "ESCALATED $taskRef — design/scope issue."
    }
}
else {
    & $postMessage -RoomDir $RoomDir -From "qa" -To "manager" `
                   -Type "error" -Ref $taskRef `
                   -Body "Could not parse QA verdict. Full output: $output"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level WARN -Message "Could not parse verdict for $taskRef — posting as error."
    }
}

# --- Clean up PID file (after channel message is posted) ---
$qaPidFile = Join-Path $RoomDir "pids" "qa.pid"
Remove-Item $qaPidFile -Force -ErrorAction SilentlyContinue

# --- Update per-role config status ---
if (Test-Path $qaRoleConfigFile) {
    $qaFinalConfig = Get-Content $qaRoleConfigFile -Raw | ConvertFrom-Json
    $qaFinalConfig.status = if ($verdict -eq "PASS") { "completed" } else { "failed" }
    $qaFinalConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $qaRoleConfigFile -Encoding utf8
}

exit $result.ExitCode

