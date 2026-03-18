<#
.SYNOPSIS
    Creates a new war-room with config.json goal contract.

.DESCRIPTION
    Sets up a war-room directory structure with channel, status tracking, PID management,
    and a config.json containing assignment details and goal definitions.

    Replaces: war-rooms/create.sh
    Enhanced: adds config.json with goals (definition_of_done, acceptance_criteria)

.PARAMETER RoomId
    Unique room identifier (e.g. room-001).
.PARAMETER TaskRef
    Task or Epic reference (e.g. TASK-001, EPIC-001).
.PARAMETER TaskDescription
    Full task/epic description.
.PARAMETER WorkingDir
    Project working directory. Default: current directory.
.PARAMETER DefinitionOfDone
    Array of goal strings for the definition of done.
.PARAMETER AcceptanceCriteria
    Array of acceptance criteria strings.
.PARAMETER PlanId
    Optional plan identifier this room belongs to.
.PARAMETER WarRoomsDir
    Base directory for war-rooms. Default: WARROOMS_DIR env var or script directory.
.PARAMETER MaxRetries
    Maximum retries for this room. Default: 3.
.PARAMETER TimeoutSeconds
    Timeout per state in seconds. Default: 900.

.EXAMPLE
    ./New-WarRoom.ps1 -RoomId "room-001" -TaskRef "EPIC-001" `
                      -TaskDescription "Implement user auth" -WorkingDir "/project" `
                      -DefinitionOfDone @("JWT working", "Tests pass") `
                      -AcceptanceCriteria @("POST /login returns 200")
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomId,

    [Parameter(Mandatory)]
    [string]$TaskRef,

    [Parameter(Mandatory)]
    [string]$TaskDescription,

    [string]$WorkingDir = '.',

    [string[]]$DefinitionOfDone = @(),

    [string[]]$AcceptanceCriteria = @(),

    [string]$PlanId = '',

    [string[]]$DependsOn = @(),

    [string]$WarRoomsDir = '',

    [string]$AssignedRole = 'engineer',

    [string[]]$CandidateRoles = @(),

    [int]$MaxRetries = 3,

    [int]$TimeoutSeconds = 900
)

# --- Resolve war-rooms directory ---
if (-not $WarRoomsDir) {
    $WarRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { $PSScriptRoot }
}

$roomDir = Join-Path $WarRoomsDir $RoomId

# --- Prevent overwriting existing room ---
if (Test-Path $roomDir) {
    Write-Error "War-room '$RoomId' already exists at $roomDir"
    exit 1
}

# --- Create room directory structure ---
New-Item -ItemType Directory -Path $roomDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $roomDir "pids") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $roomDir "artifacts") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $roomDir "contexts") -Force | Out-Null

# --- Initialize channel ---
New-Item -ItemType File -Path (Join-Path $roomDir "channel.jsonl") -Force | Out-Null

# --- Detect Epic vs Task ---
$assignmentType = if ($TaskRef -match '^EPIC-') { 'epic' } else { 'task' }

# --- Write config.json (Goal Contract) ---
$ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

$config = [ordered]@{
    room_id    = $RoomId
    task_ref   = $TaskRef
    plan_id    = $PlanId
    depends_on = $DependsOn
    created_at = $ts
    working_dir = (Resolve-Path $WorkingDir -ErrorAction SilentlyContinue).Path

    assignment = [ordered]@{
        title           = ($TaskDescription -split "`n")[0].Trim()
        description     = $TaskDescription
        assigned_role   = $AssignedRole
        candidate_roles = if ($CandidateRoles.Count -gt 0) { $CandidateRoles } else { @($AssignedRole) }
        type            = $assignmentType
    }

    goals = [ordered]@{
        definition_of_done  = $DefinitionOfDone
        acceptance_criteria = $AcceptanceCriteria
        quality_requirements = [ordered]@{
            test_coverage_min = 80
            lint_clean        = $true
            security_scan_pass = $true
        }
    }

    constraints = [ordered]@{
        max_retries       = $MaxRetries
        timeout_seconds   = $TimeoutSeconds
        budget_tokens_max = 500000
    }

    status = [ordered]@{
        current           = "pending"
        retries           = 0
        started_at        = $null
        last_state_change = $ts
    }
}

$config | ConvertTo-Json -Depth 10 | Out-File -FilePath (Join-Path $roomDir "config.json") -Encoding utf8

# --- Write per-role config file ({role}_{id}.json) ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$configPath = Join-Path $agentsDir "config.json"
$globalConfig = $null
if (Test-Path $configPath) {
    $globalConfig = Get-Content $configPath -Raw | ConvertFrom-Json
}

# Parse base role name (strip instance suffix like "engineer:fe" → "engineer")
$baseRole = $AssignedRole -replace ':.*$', ''
$instanceSuffix = if ($AssignedRole -match ':(.+)$') { $Matches[1] } else { '' }

# Resolve model for this role: instance → global config → role.json → default
$roleModel = "gemini-3-flash-preview"
if ($globalConfig) {
    if ($instanceSuffix -and $globalConfig.$baseRole.instances.$instanceSuffix.default_model) {
        $roleModel = $globalConfig.$baseRole.instances.$instanceSuffix.default_model
    }
    elseif ($globalConfig.$baseRole.default_model) {
        $roleModel = $globalConfig.$baseRole.default_model
    }
}
# Fallback: try role.json
if ($roleModel -eq "gemini-3-flash-preview") {
    $roleJsonPath = Join-Path $agentsDir "roles" $baseRole "role.json"
    if (Test-Path $roleJsonPath) {
        $roleJson = Get-Content $roleJsonPath -Raw | ConvertFrom-Json
        if ($roleJson.model) { $roleModel = $roleJson.model }
    }
}

# Determine instance ID (sequential counter for this role in this room)
$existingRoleConfigs = Get-ChildItem -Path $roomDir -Filter "${baseRole}_*.json" -ErrorAction SilentlyContinue
$instanceNum = ($existingRoleConfigs | Measure-Object).Count + 1
$instanceId = $instanceNum.ToString("000")

$roleConfig = [ordered]@{
    role          = $baseRole
    instance_id   = $instanceId
    instance_type = $instanceSuffix
    display_name  = if ($instanceSuffix) { "$baseRole`:$instanceSuffix #$instanceId" } else { "$baseRole #$instanceId" }
    model         = $roleModel
    assigned_at   = $ts
    status        = "pending"
    config_override = [ordered]@{}
}

$roleConfigFile = Join-Path $roomDir "${baseRole}_${instanceId}.json"
$roleConfig | ConvertTo-Json -Depth 5 | Out-File -FilePath $roleConfigFile -Encoding utf8

# --- Write assignment brief (includes DoD + AC for full context) ---
$dodSection = ""
if ($DefinitionOfDone -and $DefinitionOfDone.Count -gt 0) {
    $dodLines = ($DefinitionOfDone | ForEach-Object { "- [ ] $_" }) -join "`n"
    $dodSection = @"

## Definition of Done

$dodLines
"@
}

$acSection = ""
if ($AcceptanceCriteria -and $AcceptanceCriteria.Count -gt 0) {
    $acLines = ($AcceptanceCriteria | ForEach-Object { "- [ ] $_" }) -join "`n"
    $acSection = @"

## Acceptance Criteria

$acLines
"@
}

$briefContent = @"
# $TaskRef

$TaskDescription
$dodSection
$acSection

## Working Directory
$($config.working_dir)

## Created
$ts
"@
$briefContent | Out-File -FilePath (Join-Path $roomDir "brief.md") -Encoding utf8

# --- Initialize status ---
"pending" | Out-File -FilePath (Join-Path $roomDir "status") -Encoding utf8 -NoNewline

# --- Initialize retry counter ---
"0" | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline

# --- Store task ref for quick lookup ---
$TaskRef | Out-File -FilePath (Join-Path $roomDir "task-ref") -Encoding utf8 -NoNewline

# --- Post initial task message to channel ---
$PostMessage = Join-Path $PSScriptRoot ".." "channel" "Post-Message.ps1"
if (Test-Path $PostMessage) {
    & $PostMessage -RoomDir $roomDir -From "manager" -To $baseRole `
                   -Type "task" -Ref $TaskRef -Body $TaskDescription
}

# --- Output ---
Write-Output "[CREATED] War-room '$RoomId' for $TaskRef"
Write-Output "  Path: $roomDir"
Write-Output "  Status: pending"
Write-Output "  Role: $AssignedRole → ${baseRole}_${instanceId}.json (model: $roleModel)"
Write-Output "  Goals: $($DefinitionOfDone.Count) definition(s) of done, $($AcceptanceCriteria.Count) acceptance criteria"

