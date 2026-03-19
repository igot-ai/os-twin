<#
.SYNOPSIS
    Generates a planning-DAG.json from a plan markdown using AI analysis.

.DESCRIPTION
    Reads a plan markdown file and uses an AI architect (via Invoke-Agent.ps1)
    to analyze epics and determine the optimal role assignments, candidate roles,
    and dependency relationships. Outputs a planning-DAG.json that serves as an
    advisory draft DAG before war-rooms are created.

    The planning-DAG informs Start-Plan.ps1 role provisioning.
    The solid DAG.json is built later from actual room configs by Build-DependencyGraph.ps1.

    Follows the same pattern as Expand-Plan.ps1.

.PARAMETER PlanFile
    Path to the plan markdown file.
.PARAMETER OutFile
    Path to write the planning-DAG JSON. Defaults to .planning-DAG.json alongside the plan.
.PARAMETER DryRun
    Show what would be generated without calling the AI.
.PARAMETER AgentCmd
    Optional: custom agent runner (for testing with mock AI).
.PARAMETER RoomDir
    Optional: existing room directory for AI context. Default uses a temp room.

.EXAMPLE
    ./Build-PlanningDAG.ps1 -PlanFile "./plans/my-plan.md"
    ./Build-PlanningDAG.ps1 -PlanFile "./plans/my-plan.md" -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$PlanFile,

    [string]$OutFile = '',

    [switch]$DryRun,

    [string]$AgentCmd = '',

    [string]$RoomDir = ''
)

# --- Resolve paths ---
$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$invokeAgent = Join-Path $agentsDir "roles" "_base" "Invoke-Agent.ps1"
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"

if (Test-Path $logModule) { Import-Module $logModule -Force }
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

# --- Validate plan file ---
if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$planContent = Get-Content $PlanFile -Raw
$planDir = Split-Path $PlanFile
if (-not $OutFile) {
    $OutFile = Join-Path $planDir ".planning-DAG.json"
}

# --- Quick-parse epics for reference ---
$epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–]\s*(.+)$'
$epicMatches = [regex]::Matches($planContent, $epicPattern)
if ($epicMatches.Count -eq 0) {
    Write-Host "[PLANNING-DAG] No epics found in $PlanFile" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "=== Ostwin Planning DAG Builder ===" -ForegroundColor Cyan
Write-Host "  Plan: $PlanFile"
Write-Host "  Epics found: $($epicMatches.Count)"
Write-Host "  Output: $OutFile"
Write-Host ""

# --- Collect available roles for the prompt ---
$rolesDir = Join-Path $agentsDir "roles"
$availableRoles = @()
if (Test-Path $rolesDir) {
    $availableRoles = Get-ChildItem -Path $rolesDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '_base' -and $_.Name -ne '__pycache__' } |
        ForEach-Object { $_.Name }
}
$rolesListStr = if ($availableRoles.Count -gt 0) {
    "Available roles in this system: $($availableRoles -join ', ')"
} else {
    "Common roles: engineer, qa, architect, reporter, manager"
}

if ($DryRun) {
    Write-Host "[DRY RUN] Would analyze $($epicMatches.Count) epics and generate planning-DAG.json" -ForegroundColor Yellow
    foreach ($em in $epicMatches) {
        Write-Host "  $($em.Groups[1].Value) — $($em.Groups[2].Value.Trim())" -ForegroundColor White
    }
    Write-Host ""
    exit 0
}

# --- Create temp room for AI context ---
$ownsTempRoom = $false
$planningRoom = if ($RoomDir) { $RoomDir } else {
    $warRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { Join-Path (Split-Path $agentsDir) ".war-rooms" }
    $pr = Join-Path $warRoomsDir "room-planning-dag"
    if (-not (Test-Path $pr)) {
        New-Item -ItemType Directory -Path $pr -Force | Out-Null
    }
    $ownsTempRoom = $true
    $pr
}

# --- Build AI prompt ---
$prompt = @"
You are a Senior Software Architect. Your task is to analyze a project plan and produce a planning dependency graph (DAG) as JSON.

## Plan Content
$planContent

## $rolesListStr

## Instructions
Analyze each EPIC in the plan above and determine:

1. **Role Assignment**: Which role is the best fit for each epic? Consider:
   - The epic title and description (e.g., "Report Spec Template (Reporter)" suggests the `reporter` role)
   - The tasks table if present (role column hints)
   - The nature of the work (code → engineer, reports → reporter, testing → qa, design → architect)

2. **Candidate Roles**: An ORDERED array of roles that could work on this epic. Primary role first.
   - This MUST always be a JSON array, even if only one role.

3. **Dependencies**: Real dependencies between epics based on data/output flow.
   - Only add a dependency if one epic genuinely needs output from another.
   - Do NOT assume sequential dependencies — prefer parallel execution.

4. **Rationale**: Brief explanation of your role and dependency choices.

## Output Format
Return ONLY valid JSON matching this exact schema. No preamble, no markdown fences, no explanation outside the JSON:

{
  "nodes": [
    {
      "task_ref": "EPIC-1",
      "title": "...",
      "role": "engineer",
      "candidate_roles": ["engineer"],
      "depends_on": [],
      "rationale": "..."
    }
  ],
  "topological_order": ["EPIC-1", "EPIC-2"]
}

RULES:
- "candidate_roles" MUST be a JSON array, never a bare string
- "depends_on" MUST be a JSON array, never a bare string
- "topological_order" lists epics in dependency order (dependencies before dependents)
- Use exact EPIC-N references from the plan
- Do NOT include PLAN-REVIEW (that is injected automatically)
"@

Write-Host "[PLANNING-DAG] Analyzing plan with manager profile..." -NoNewline

$result = if ($AgentCmd) {
    # AgentCmd can be a script path or a multi-word command string
    $output = if (Test-Path $AgentCmd) {
        & $AgentCmd $prompt | Out-String
    } else {
        Invoke-Expression "$AgentCmd '$($prompt -replace "'", "''")'"
    }
    $code = if ($?) { 0 } else { 1 }
    [PSCustomObject]@{ ExitCode = $code; Output = $output }
} else {
    & $invokeAgent -RoomDir $planningRoom -RoleName "manager" `
                     -Prompt $prompt -TimeoutSeconds 300
}

if ($result.ExitCode -ne 0) {
    Write-Host " [FAILED]" -ForegroundColor Red
    Write-Warning "AI analysis failed: $($result.Output)"
    # Clean up temp room
    if ($ownsTempRoom -and (Test-Path $planningRoom)) {
        Remove-Item $planningRoom -Recurse -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

Write-Host " [DONE]" -ForegroundColor Green

# --- Parse and validate AI output ---
$rawOutput = $result.Output.Trim()

# Strip markdown code fences if the AI wrapped it
$rawOutput = $rawOutput -replace '(?s)^```(?:json)?\s*', '' -replace '(?s)\s*```$', ''

try {
    $dagData = $rawOutput | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Warning "Failed to parse AI output as JSON: $_"
    Write-Host "Raw output:" -ForegroundColor Gray
    Write-Host $rawOutput
    if ($ownsTempRoom) { Remove-Item $planningRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 1
}

# --- Validate and normalize the structure ---
if (-not $dagData.nodes) {
    Write-Warning "AI output missing 'nodes' array."
    if ($ownsTempRoom) { Remove-Item $planningRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 1
}

# Force all candidate_roles and depends_on to be arrays
foreach ($node in $dagData.nodes) {
    if ($node.candidate_roles -and $node.candidate_roles -isnot [array]) {
        $node.candidate_roles = @($node.candidate_roles)
    }
    if (-not $node.candidate_roles) {
        $node.candidate_roles = @(if ($node.role) { $node.role } else { "engineer" })
    }
    if ($node.depends_on -and $node.depends_on -isnot [array]) {
        $node.depends_on = @($node.depends_on)
    }
    if (-not $node.depends_on) {
        $node.depends_on = @()
    }
}

# --- Enrich with metadata ---
$planningDag = [ordered]@{
    generated_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    source            = (Split-Path $PlanFile -Leaf)
    stage             = "planning"
    total_nodes       = $dagData.nodes.Count
    nodes             = $dagData.nodes
    topological_order = if ($dagData.topological_order) { @($dagData.topological_order) } else { @($dagData.nodes | ForEach-Object { $_.task_ref }) }
}

# --- Write output ---
$planningDag | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutFile -Encoding utf8
Write-Host ""
Write-Host "[PLANNING-DAG] Written to $OutFile ($($dagData.nodes.Count) nodes)" -ForegroundColor Cyan

# --- Display summary ---
foreach ($node in $dagData.nodes) {
    $depsStr = if ($node.depends_on -and $node.depends_on.Count -gt 0) { " [depends_on: $($node.depends_on -join ', ')]" } else { "" }
    Write-Host "  $($node.task_ref) → $($node.role) (candidates: $($node.candidate_roles -join ', '))$depsStr" -ForegroundColor White
}
Write-Host ""

# --- Clean up temp room ---
if ($ownsTempRoom -and (Test-Path $planningRoom)) {
    Remove-Item $planningRoom -Recurse -Force -ErrorAction SilentlyContinue
}
