<#
.SYNOPSIS
    JIT Agent Factory runner — synthesizes an ephemeral persona and executes the task.

.DESCRIPTION
    Reads the task from the war-room, asks the Manager LLM to synthesize an
    ideal specific agent persona with necessary skills, then launches that agent.
    Bypasses static role definitions.

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER TimeoutSeconds
    Override timeout.
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

if ($TimeoutSeconds -eq 0) { $TimeoutSeconds = 600 }

function Write-Log {
    param([string]$Level, [string]$Message)
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level $Level -Message $Message
    }
    else {
        Write-Host "[$Level] $Message"
    }
}

# --- Process Tracking (PID) ---
$pidDir = Join-Path $RoomDir "pids"
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Path $pidDir -Force | Out-Null }
$pidFile = Join-Path $pidDir "engineer.pid" # Keeps compatibility with manager loop checking engineer.pid
$PID | Out-File -FilePath $pidFile -Encoding utf8 -NoNewline

function Cleanup-And-Exit {
    param([int]$ExitCode, [string]$ErrorMsg = "")
    if ($ErrorMsg) {
        Write-Log "ERROR" "Agent Error: $ErrorMsg"
        & $postMessage -RoomDir $RoomDir -From "engineer" -To "manager" -Type "error" -Ref $TaskRef -Body $ErrorMsg
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit $ExitCode
}

# --- Load Config ---
$roomConfigFile = Join-Path $RoomDir "config.json"
if (-not (Test-Path $roomConfigFile)) {
    Cleanup-And-Exit 1 "config.json not found in war room."
}
$roomConfig = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
$TaskRef = $roomConfig.task_ref
$TaskTitle = $roomConfig.assignment.title
$TaskDesc = $roomConfig.assignment.description
$WorkingDir = $roomConfig.working_dir

# Get the latest instruction from channel
$latestFix = ""
$fixMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fix" -AsObject
if ($fixMsgs -and $fixMsgs.Count -gt 0) {
    $latestFix = $fixMsgs[-1].body
}

# --- PHASE 1: JIT Agent Synthesis (The Manager's Brain) ---
$AgentSpecFile = Join-Path $RoomDir "artifacts" "agent-spec.json"
$AgentSpec = $null

if (-not (Test-Path $AgentSpecFile) -or $latestFix) {
    # If no spec exists OR there is new feedback from Manager/QA, regenerate the spec
    Write-Log "INFO" "Synthesizing dynamic ephemeral agent for $TaskRef..."
    
    $SynthesisPrompt = @"
You are an expert Engineering Manager and System Architect.
Your task is to analyze the following work objective and synthesize an ephemeral AI agent perfectly suited to complete it.

Objective Title: $TaskTitle
Objective Description: $TaskDesc
$($latestFix ? "`nLatest Feedback/Fix Instruction:`n$latestFix" : "")

Respond ONLY with a JSON object matching this schema. NO markdown backticks, NO extra text.
{
  "role_id": "short-descriptive-role-name",
  "purpose": "A clear, specific sentence describing the agent's exact purpose.",
  "required_capabilities": ["list", "of", "capabilities"],
  "required_skills": ["list", "of", "skill-folder-names"]
}

Available Skills in .agents/skills/:
$(Get-ChildItem -Path (Join-Path $agentsDir "skills") -Directory | Select-Object -ExpandProperty Name | Join-String -Separator ', ')
"@
    
    # Run a quick synthesis LLM call
    $SyncResult = & $invokeAgent -RoomDir $RoomDir -RoleName "manager" -Prompt $SynthesisPrompt -Model "gemini-3.1-pro-preview" -TimeoutSeconds 120 -InstanceId "synth"
    
    if ($SyncResult.ExitCode -ne 0) {
        Cleanup-And-Exit 1 "Agent synthesis failed. See output: $($SyncResult.Output)"
    }
    
    $RawOutput = $SyncResult.Output
    # Extract JSON robustly, ignoring any CLI prefixes/logs
    if ($RawOutput -match '(?s)(\{.*?\})') {
        $RawOutput = $Matches[1]
    }
    
    try {
        $AgentSpec = $RawOutput | ConvertFrom-Json
        $AgentSpec | ConvertTo-Json -Depth 5 | Out-File -FilePath $AgentSpecFile -Encoding utf8
        Write-Log "INFO" "Synthesized Role: $($AgentSpec.role_id) equipped with: $($AgentSpec.required_skills -join ', ')"
    } catch {
        Cleanup-And-Exit 1 "Failed to parse synthesized agent JSON: $RawOutput"
    }
} else {
    $AgentSpec = Get-Content $AgentSpecFile -Raw | ConvertFrom-Json
    Write-Log "INFO" "Loaded cached agent role: $($AgentSpec.role_id)"
}

# --- PHASE 2: Execution (The Specialized Agent) ---

$AgentPrompt = @"
You are a highly specialized, ephemeral AI agent.
Role ID: $($AgentSpec.role_id)
Purpose: $($AgentSpec.purpose)

You must operate entirely within the workspace: $WorkingDir

=== YOUR OBJECTIVE ===
Title: $TaskTitle
$TaskDesc

$($latestFix ? "`n=== URGENT FIX / FEEDBACK ===`n$latestFix`n" : "")

CRITICAL RULES:
1. Complete the objective thoroughly using your tools.
2. If tests exist, run them. If tests fail, fix your code.
3. When the objective is complete, DO NOT ask for permission to stop.
4. Output a brief, concise summary of exactly what you accomplished.
"@

# Inject Skills dynamically
$SkillsDir = Join-Path $agentsDir "skills"
$InjectedSkills = @()

if ($AgentSpec.required_skills) {
    $AgentPrompt += "`n`n=== EQUIPPED SKILLS ===`n"
    foreach ($skill in $AgentSpec.required_skills) {
        $SkillPath = Join-Path $SkillsDir $skill "SKILL.md"
        if (Test-Path $SkillPath) {
            $SkillContent = Get-Content $SkillPath -Raw
            $AgentPrompt += "`n--- Skill: $skill ---`n$SkillContent`n"
            $InjectedSkills += $skill
        } else {
            Write-Log "WARN" "Requested skill '$skill' not found. Skipping."
        }
    }
}

Write-Log "INFO" "Executing ephemeral agent task..."

# Pass directly to base execution engine
$ExecutionResult = & $invokeAgent -RoomDir $RoomDir `
    -RoleName "engineer" `
    -Prompt $AgentPrompt `
    -Model "gemini-3.1-pro-preview" `
    -TimeoutSeconds $TimeoutSeconds `
    -WorkingDir $WorkingDir `
    -InstanceId "ephemeral"

if ($ExecutionResult.ExitCode -ne 0) {
    Cleanup-And-Exit 1 "Task failed: $($ExecutionResult.Output)"
}

# Output success
$Summary = $ExecutionResult.Output
if (-not $Summary) { $Summary = "Task completed successfully by $($AgentSpec.role_id)." }

& $postMessage -RoomDir $RoomDir -From "engineer" -To "manager" -Type "done" -Ref $TaskRef -Body $Summary
Cleanup-And-Exit 0
