<#
.SYNOPSIS
    Engineer role runner — reads task from war-room and executes via deepagents.

.DESCRIPTION
    Reads the task brief and latest instruction from the war-room channel,
    builds a role-specific prompt, runs the agent via Invoke-Agent.ps1,
    and posts the result (done/error) back to the channel.

    Replaces: roles/engineer/run.sh

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER TimeoutSeconds
    Override timeout. Default: from config.

.EXAMPLE
    ./Start-Engineer.ps1 -RoomDir "./war-rooms/room-001"
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

$config = $null
$maxPromptBytes = 102400
$InstanceId = ""
$instanceWorkingDir = ""
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if ($TimeoutSeconds -eq 0) {
        $TimeoutSeconds = $config.engineer.timeout_seconds
    }
    if ($config.engineer.max_prompt_bytes) {
        $maxPromptBytes = $config.engineer.max_prompt_bytes
    }
}
if ($TimeoutSeconds -eq 0) { $TimeoutSeconds = 600 }

# --- Parse instance from war-room config ---
$roomConfigFile = Join-Path $RoomDir "config.json"
if (Test-Path $roomConfigFile) {
    $roomConfig = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
    $assignedRole = $roomConfig.assignment.assigned_role
    if ($assignedRole -match '^engineer:(.+)$') {
        $InstanceId = $Matches[1]
    }
}

# --- Resolve instance-specific working directory ---
if ($InstanceId -and $config -and $config.engineer.instances.$InstanceId) {
    $instanceConfig = $config.engineer.instances.$InstanceId
    if ($instanceConfig.working_dir) {
        $instanceWorkingDir = $instanceConfig.working_dir
    }
    if ($instanceConfig.timeout_seconds -and $TimeoutSeconds -eq $config.engineer.timeout_seconds) {
        $TimeoutSeconds = $instanceConfig.timeout_seconds
    }
}

# --- Write per-role context.md ---
$contextsDir = Join-Path $RoomDir "contexts"
if (-not (Test-Path $contextsDir)) {
    New-Item -ItemType Directory -Path $contextsDir -Force | Out-Null
}
$contextFileName = if ($InstanceId) { "engineer-$InstanceId.md" } else { "engineer.md" }
$contextFile = Join-Path $contextsDir $contextFileName
$instanceDisplayName = if ($InstanceId -and $config.engineer.instances.$InstanceId.display_name) {
    $config.engineer.instances.$InstanceId.display_name
} else { "Engineer" }
$contextContent = @"
# $instanceDisplayName Context

## Assignment
- Task: $taskRef (resolving below)
- Instance: $(if ($InstanceId) { $InstanceId } else { 'default' })
- Working Directory: $(if ($instanceWorkingDir) { $instanceWorkingDir } else { 'project root' })
- Started: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))
"@

# --- Read task ref ---
$taskRef = if (Test-Path (Join-Path $RoomDir "task-ref")) {
    (Get-Content (Join-Path $RoomDir "task-ref") -Raw).Trim()
} else { "UNKNOWN" }

# --- Finalize context.md with task ref ---
$contextContent = $contextContent -replace '\$taskRef \(resolving below\)', $taskRef
$contextContent | Out-File -FilePath $contextFile -Encoding utf8 -Force

# --- Detect Epic vs Task ---
$isEpic = $taskRef -match '^EPIC-'

# --- Read latest task or fix message ---
$latestBody = ""
try {
    $msgs = & $readMessages -RoomDir $RoomDir -Last 1 -AsObject
    if ($msgs) {
        foreach ($m in ($msgs | Sort-Object { $_.ts } -Descending)) {
            if ($m.type -in @('task', 'fix')) {
                $latestBody = $m.body
                break
            }
        }
    }
}
catch { }

# --- Read full task description ---
$taskDesc = if (Test-Path (Join-Path $RoomDir "brief.md")) {
    Get-Content (Join-Path $RoomDir "brief.md") -Raw
} else { "No task description found." }

# --- Parse working directory from brief.md ---
$workingDir = Get-Location
$briefContent = $taskDesc
if ($briefContent -match 'working_dir:\s*(.+)') {
    $workingDir = $Matches[1].Trim()
}
elseif ($briefContent -match '## Working Directory\s*\n(.+)') {
    $workingDir = $Matches[1].Trim()
}

# --- Read role prompt ---
$rolePrompt = if (Test-Path (Join-Path $scriptDir "ROLE.md")) {
    Get-Content (Join-Path $scriptDir "ROLE.md") -Raw
} else { "" }

# --- Build instructions based on Epic vs Task ---
$roomName = Split-Path $RoomDir -Leaf

if ($isEpic) {
    $instructions = @"
You are working on an EPIC — a high-level feature that you must plan and implement yourself.

### Phase 1 — Planning
1. Analyze the brief above and break it into concrete sub-tasks
2. Create a file called TASKS.md at: $RoomDir/TASKS.md
   - Use markdown checkboxes: - [ ] TASK-001 — Description
   - Each sub-task should be independently testable
   - Include acceptance criteria for each sub-task
3. Save TASKS.md before proceeding to implementation

### Phase 2 — Implementation
1. Work through each sub-task in TASKS.md sequentially
2. After completing each sub-task, check it off: - [x] TASK-001 — Description
3. Write tests as you go — each sub-task should be verified before moving on

### Phase 3 — Reporting
1. Ensure all checkboxes in TASKS.md are checked
2. Summarize your changes with:
   - Epic overview: what was delivered
   - Sub-tasks completed (include the final TASKS.md checklist)
   - Files modified/created
   - How to test the full epic
"@
}
else {
    $instructions = @"
1. Implement the task described above
2. When done, summarize your changes clearly
3. Format your summary with: Changes Made, Files Modified, How to Test
"@
}

# --- Build the full prompt ---
$prompt = @"
$rolePrompt

---

## Your Task

$taskDesc

## Latest Instruction

$latestBody

## War-Room

Room: $roomName
Task Ref: $taskRef
Working Directory: $workingDir

## Instructions

$instructions
"@

# --- Prompt size guard ---
if ($prompt.Length -gt $maxPromptBytes) {
    $originalSize = $prompt.Length
    $prompt = $prompt.Substring(0, $maxPromptBytes) + @"

[TRUNCATED: prompt was $originalSize bytes, max is $maxPromptBytes. Full task description in: $RoomDir/brief.md]
"@
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level WARN -Message "Prompt truncated from $originalSize to $maxPromptBytes bytes for $taskRef"
    }
}

# --- Log start ---
if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
    Write-OstwinLog -Level INFO -Message "Starting work on $taskRef in $roomName"
}
else {
    Write-Host "[ENGINEER] Starting work on $taskRef in $roomName"
}

# --- Run the agent ---
$result = & $invokeAgent -RoomDir $RoomDir -RoleName "engineer" `
                         -InstanceId $InstanceId `
                         -WorkingDir $instanceWorkingDir `
                         -Prompt $prompt -TimeoutSeconds $TimeoutSeconds

# --- Post result to channel ---
if ($result.ExitCode -eq 0) {
    & $postMessage -RoomDir $RoomDir -From "engineer" -To "manager" `
                   -Type "done" -Ref $taskRef -Body $result.Output
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level INFO -Message "Completed $taskRef successfully."
    }
}
elseif ($result.TimedOut) {
    & $postMessage -RoomDir $RoomDir -From "engineer" -To "manager" `
                   -Type "error" -Ref $taskRef -Body "Engineer timed out after ${TimeoutSeconds}s"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level ERROR -Message "Timed out on $taskRef after ${TimeoutSeconds}s."
    }
}
else {
    & $postMessage -RoomDir $RoomDir -From "engineer" -To "manager" `
                   -Type "error" -Ref $taskRef `
                   -Body "Engineer exited with code $($result.ExitCode): $($result.Output)"
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level ERROR -Message "Failed on $taskRef with exit code $($result.ExitCode)."
    }
}

exit $result.ExitCode
