<#
.SYNOPSIS
    Reviews and approves inter-EPIC dependency changes after war-rooms are created.

.DESCRIPTION
    Parses EPIC sections directly from the plan .md file, extracts each EPIC's
    description/goal (excluding Tasks, DoD, AC checklists), and sends all EPICs
    plus the plan header context to an AI architect for dependency analysis.

    The AI returns a simple map: {"EPIC-NNN": {"depends_on": ["EPIC-MMM"]}}
    which is compared against current depends_on from war-room configs.
    Changes are displayed as a colored diff and the user is prompted for approval.

    This script is called AFTER war-rooms are created and BEFORE the manager loop.

    If approved, updates:
    - depends_on in each war-room's config.json
    - depends_on lines in the plan .md file
    - Rebuilds DAG.json via Build-DependencyGraph.ps1
    - Writes .planning-DAG.json for backward compat

.PARAMETER WarRoomsDir
    Path to the war-rooms directory (contains room-001, room-002, etc.).
.PARAMETER PlanFile
    Path to the plan markdown file (source of truth for EPIC content).
.PARAMETER AutoApprove
    Skip the interactive approval prompt and auto-accept changes.
.PARAMETER DryRun
    Show what would change without modifying anything.
.PARAMETER AgentCmd
    Optional mock agent runner for testing.

.EXAMPLE
    ./Review-Dependencies.ps1 -WarRoomsDir ".war-rooms" -PlanFile "./plans/plan.md"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$WarRoomsDir,

    [Parameter(Mandatory)]
    [string]$PlanFile,

    [switch]$AutoApprove,

    [switch]$DryRun,

    [string]$AgentCmd = '',

    [string]$RoomDir = ''
)

# --- Resolve paths ---
$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$invokeAgent = Join-Path $agentsDir "roles" "_base" "Invoke-Agent.ps1"
$buildDag = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"

if (Test-Path $logModule) { Import-Module $logModule -Force }
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

# --- Validate inputs ---
if (-not (Test-Path $WarRoomsDir)) {
    throw "War-rooms directory not found: $WarRoomsDir"
}
if (-not (Test-Path $PlanFile)) {
    throw "Plan file not found: $PlanFile"
}

# --- Parse plan .md: extract header + EPIC sections ---
$planContent = Get-Content $PlanFile -Raw
$epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–?]\s*(.+)$'
$epicMatches = [regex]::Matches($planContent, $epicPattern)

if ($epicMatches.Count -lt 2) {
    Write-Host "[DEP-REVIEW] Fewer than 2 EPICs in plan — no dependency analysis needed." -ForegroundColor DarkGray
    exit 0
}

Write-Host ""
Write-Host "=== Dependency Review ===" -ForegroundColor Cyan
Write-Host "  EPICs: $($epicMatches.Count)"
Write-Host ""

# --- Extract plan header (everything before first EPIC) ---
# Contains dependency diagrams, data assets, role tables, architecture context.
$planHeader = $planContent.Substring(0, $epicMatches[0].Index).Trim()
if ($planHeader.Length -gt 3000) {
    $planHeader = $planHeader.Substring(0, 3000) + "`n[TRUNCATED]"
}

# --- Extract each EPIC's description (exclude Tasks, DoD, AC) ---
$epicContexts = @()
$epicRefs = @()
# Cut patterns: any ### or ## heading that is Tasks, Definition of Done, Acceptance Criteria,
# or metadata like Working Directory, Created. Everything from there down is noise.
$cutPattern = '(?m)^#{2,3}\s+(Tasks|Definition of Done|Acceptance Criteria|Working Directory|Created)\b'

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[1].Value
    $epicTitle = $em.Groups[2].Value.Trim()
    $epicRefs += $epicRef

    # Find section boundaries
    $epicStart = $em.Index
    $nextEpic = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextEpic) { $nextEpic.Index } else { $planContent.Length }
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # Cut at Tasks/DoD/AC/metadata — keep only description/goal
    $cutMatch = [regex]::Match($epicSection, $cutPattern)
    $descOnly = if ($cutMatch.Success) {
        $epicSection.Substring(0, $cutMatch.Index).Trim()
    } else {
        $epicSection.Trim()
    }
    # Also strip trailing --- separators
    $descOnly = $descOnly -replace '(?m)\n---\s*$', ''
    # Truncate if still too long
    if ($descOnly.Length -gt 1000) {
        $descOnly = $descOnly.Substring(0, 1000) + "`n[TRUNCATED]"
    }

    $epicContexts += $descOnly
}

# --- Read current depends_on from war-room configs ---
$currentDeps = @{}
$rooms = Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" |
    Where-Object { $_.Name -ne "room-000" } |
    Sort-Object Name

foreach ($room in $rooms) {
    $configFile = Join-Path $room.FullName "config.json"
    if (-not (Test-Path $configFile)) { continue }

    $config = Get-Content $configFile -Raw | ConvertFrom-Json
    $taskRef = if ($config.task_ref) { $config.task_ref }
               elseif (Test-Path (Join-Path $room.FullName "task-ref")) {
                   (Get-Content (Join-Path $room.FullName "task-ref") -Raw).Trim()
               } else { continue }

    if ($taskRef -notmatch '^EPIC-') { continue }

    $deps = @()
    if ($config.depends_on) {
        $deps = @($config.depends_on) | Where-Object { $_ -and $_ -ne 'PLAN-REVIEW' }
    }
    $currentDeps[$taskRef] = $deps
}
# Ensure all plan EPICs have an entry even if no room exists yet
foreach ($ref in $epicRefs) {
    if (-not $currentDeps.ContainsKey($ref)) { $currentDeps[$ref] = @() }
}

$allEpicContext = $epicContexts -join "`n`n---`n`n"

# --- Build the plan context block ---
$planContextBlock = ""
if ($planHeader) {
    $planContextBlock = @"

## Plan Context (architecture, data assets, dependency hints)

$planHeader
"@
}

# --- Build EPIC ref list for output format ---
$epicRefList = ($epicRefs | ForEach-Object { """$_""" }) -join ', '

# --- AI dependency analysis prompt ---
Write-Host "[DEP-REVIEW] Analyzing dependencies across $($epicMatches.Count) EPICs from plan..." -NoNewline

$depPrompt = @"
You are a Dependency Analyst for a software project. Analyze the EPICs below and determine the MINIMUM dependency graph that allows MAXIMUM parallelism.
$planContextBlock

## EPICs (description and goal only — Tasks, DoD, AC excluded)

$allEpicContext

## Rules
- Only add a dependency edge if EPIC-B genuinely CANNOT START until EPIC-A COMPLETES
- Look at what each EPIC produces: if EPIC-A produces data/APIs/schemas that EPIC-B consumes, that's a real dependency
- Infrastructure/environment EPICs (Docker, CI/CD, data pipelines) are typically prerequisites for downstream work
- Do NOT assume sequential order — parallel execution is strongly preferred
- Do NOT include PLAN-REVIEW (that is injected automatically)
- If the Plan Context above includes a dependency diagram, use it as a starting point but validate it against the actual EPIC descriptions

## Output Format
Return ONLY valid JSON, no markdown fences, no preamble. One key per EPIC with its depends_on array:
{
  $($epicRefs | ForEach-Object { """$_"": {""depends_on"": []}" } | Select-Object -First 1),
  ...
}

Example for a 3-EPIC plan where EPIC-002 needs EPIC-001:
{
  "EPIC-001": {"depends_on": []},
  "EPIC-002": {"depends_on": ["EPIC-001"]},
  "EPIC-003": {"depends_on": []}
}

You MUST include ALL EPICs: $epicRefList
"@

# --- Create temp room for AI if needed ---
$ownsTempRoom = $false
$expansionRoom = if ($RoomDir) { $RoomDir } else {
    $er = Join-Path $WarRoomsDir "room-dep-review"
    if (-not (Test-Path $er)) {
        New-Item -ItemType Directory -Path $er -Force | Out-Null
    }
    $ownsTempRoom = $true
    $er
}

$depResult = if ($AgentCmd) {
    $depOutput = & $AgentCmd $depPrompt | Out-String
    $depCode = if ($?) { 0 } else { 1 }
    [PSCustomObject]@{ ExitCode = $depCode; Output = $depOutput }
} else {
    try {
        & $invokeAgent -RoomDir $expansionRoom -RoleName "architect" `
                         -Prompt $depPrompt -TimeoutSeconds 300 -ErrorAction Stop
    } catch {
        Write-Warning "Agent invocation failed for dependency review: $($_.Exception.Message)"
        [PSCustomObject]@{ ExitCode = 1; Output = $_.Exception.Message }
    }
}

if ($depResult.ExitCode -ne 0) {
    Write-Host " [FAILED]" -ForegroundColor Red
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    throw "Dependency analysis failed: $($depResult.Output)"
}

# --- Write raw AI output to artifact for inspection ---
$planDir = Split-Path $PlanFile
$rawOutputFile = Join-Path $planDir ".dep-review-raw.txt"
$depResult.Output | Out-File -FilePath $rawOutputFile -Encoding utf8
Write-Host " [RAW → $rawOutputFile]" -ForegroundColor DarkGray -NoNewline

# --- Parse AI output ---
# The raw output may contain wrapper noise (PID lines, tool logs, preamble text).
# Extract the first valid JSON object { ... } from anywhere in the output.
$rawDepOutput = $depResult.Output.Trim()
# Strip markdown fences
$rawDepOutput = $rawDepOutput -replace '(?s)```(?:json)?\s*', '' -replace '(?s)\s*```', ''

# Extract the outermost { ... } JSON block (greedy match for nested braces)
$jsonMatch = [regex]::Match($rawDepOutput, '(?s)\{.+\}')
if (-not $jsonMatch.Success) {
    Write-Host " [FAILED]" -ForegroundColor Red
    Write-Warning "No JSON object found in AI output. See raw: $rawOutputFile"
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 1
}
$jsonStr = $jsonMatch.Value

# Write extracted JSON to a separate artifact for easy diffing
$extractedJsonFile = Join-Path $planDir ".dep-review-parsed.json"
$jsonStr | Out-File -FilePath $extractedJsonFile -Encoding utf8

try {
    $depData = $jsonStr | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Host " [FAILED]" -ForegroundColor Red
    Write-Warning "JSON parse failed. See extracted: $extractedJsonFile"
    Write-Warning "Error: $($_.Exception.Message)"
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 1
}

Write-Host " [DONE]" -ForegroundColor Green

# --- Build proposed dependency map from AI response ---
# Format: {"EPIC-001": {"depends_on": []}, "EPIC-002": {"depends_on": ["EPIC-001"]}}
$proposedDeps = @{}
foreach ($ref in $epicRefs) {
    $epicEntry = $depData.$ref
    if ($epicEntry -and $epicEntry.depends_on) {
        $proposedDeps[$ref] = @($epicEntry.depends_on) | Where-Object { $_ -and $_ -ne 'PLAN-REVIEW' }
    } else {
        $proposedDeps[$ref] = @()
    }
}

# --- Compute diff ---
$hasChanges = $false
$changes = @()
foreach ($ref in $epicRefs) {
    $current = @($currentDeps[$ref]) | Where-Object { $_ } | Sort-Object
    $proposed = @($proposedDeps[$ref]) | Where-Object { $_ } | Sort-Object
    $currentStr = ($current -join ',')
    $proposedStr = ($proposed -join ',')

    if ($currentStr -ne $proposedStr) {
        $hasChanges = $true
        $added = $proposed | Where-Object { $_ -notin $current }
        $removed = $current | Where-Object { $_ -notin $proposed }
        $changes += [PSCustomObject]@{
            Ref      = $ref
            Current  = $current
            Proposed = $proposed
            Added    = $added
            Removed  = $removed
        }
    }
}

if (-not $hasChanges) {
    Write-Host ""
    Write-Host "[DEP-REVIEW] No dependency changes detected. Current graph is optimal." -ForegroundColor Green
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}

# --- Display diff ---
Write-Host ""
Write-Host "  Proposed Dependency Changes:" -ForegroundColor Yellow
Write-Host "  ────────────────────────────" -ForegroundColor DarkGray
foreach ($c in $changes) {
    $currentStr = if ($c.Current.Count -gt 0) { $c.Current -join ', ' } else { "(none)" }
    $proposedStr = if ($c.Proposed.Count -gt 0) { $c.Proposed -join ', ' } else { "(none)" }
    Write-Host "  $($c.Ref):" -ForegroundColor White
    Write-Host "    current:  [$currentStr]" -ForegroundColor DarkGray
    Write-Host "    proposed: [$proposedStr]" -ForegroundColor Cyan
    foreach ($a in $c.Added) {
        Write-Host "    + depends_on $a" -ForegroundColor Green
    }
    foreach ($r in $c.Removed) {
        Write-Host "    - depends_on $r" -ForegroundColor Red
    }
}
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] No changes applied." -ForegroundColor Yellow
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}

# --- Prompt for approval ---
$approved = $false
if ($AutoApprove) {
    $approved = $true
    Write-Host "[DEP-REVIEW] Auto-approved." -ForegroundColor Green
} else {
    $response = Read-Host "  Accept dependency changes? [Y/n]"
    $approved = (-not $response) -or ($response -match '^[Yy]')
}

if (-not $approved) {
    Write-Host "[DEP-REVIEW] Rejected — keeping original dependencies." -ForegroundColor Yellow
    if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}

# --- Apply changes ---
Write-Host "[DEP-REVIEW] Applying dependency changes..." -ForegroundColor Cyan

# 1. Update each war-room config.json
foreach ($c in $changes) {
    $matchedRoom = $rooms | Where-Object {
        $cf = Join-Path $_.FullName "config.json"
        if (Test-Path $cf) {
            $cfg = Get-Content $cf -Raw | ConvertFrom-Json
            $tr = if ($cfg.task_ref) { $cfg.task_ref }
                  elseif (Test-Path (Join-Path $_.FullName "task-ref")) {
                      (Get-Content (Join-Path $_.FullName "task-ref") -Raw).Trim()
                  } else { "" }
            $tr -eq $c.Ref
        }
    }
    if ($matchedRoom) {
        $cfgPath = Join-Path $matchedRoom.FullName "config.json"
        $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
        # Always keep PLAN-REVIEW + new deps
        $newDeps = @("PLAN-REVIEW") + @($c.Proposed)
        $cfg.depends_on = $newDeps | Select-Object -Unique
        $cfg | ConvertTo-Json -Depth 10 | Out-File -FilePath $cfgPath -Encoding utf8
        Write-Host "  Updated $($matchedRoom.Name)/config.json" -ForegroundColor DarkGray
    }
}

# 2. Update depends_on lines in the plan .md file
$planContent = Get-Content $PlanFile -Raw
$epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–?]\s*(.+)$'
$updatedPlan = $planContent

foreach ($c in $changes) {
    $epicRef = $c.Ref
    $depsStr = if ($c.Proposed.Count -gt 0) {
        ($c.Proposed | ForEach-Object { """$_""" }) -join ', '
    } else { "" }
    $newDepsLine = "depends_on: [$depsStr]"

    # Find the EPIC section and replace/append depends_on line
    $epicHeaderMatch = [regex]::Match($updatedPlan, "(?m)^#{2,3}\s+${epicRef}\s*[-—–?]\s*.+$")
    if ($epicHeaderMatch.Success) {
        $secStart = $epicHeaderMatch.Index
        $afterHeader = $updatedPlan.Substring($secStart)
        $nextEpicMatch = [regex]::Match($afterHeader.Substring($epicHeaderMatch.Length), '(?m)^#{2,3}\s+EPIC-')
        $secEnd = if ($nextEpicMatch.Success) { $secStart + $epicHeaderMatch.Length + $nextEpicMatch.Index } else { $updatedPlan.Length }
        $section = $updatedPlan.Substring($secStart, $secEnd - $secStart)

        $existingDepsMatch = [regex]::Match($section, '(?m)^\s*depends_on:\s*\[.*\]\s*$')
        if ($existingDepsMatch.Success) {
            $newSection = $section.Remove($existingDepsMatch.Index, $existingDepsMatch.Length).Insert($existingDepsMatch.Index, $newDepsLine)
        } else {
            $newSection = $section.TrimEnd() + "`n`n$newDepsLine`n"
        }
        $updatedPlan = $updatedPlan.Remove($secStart, $secEnd - $secStart).Insert($secStart, $newSection)
    }
}

$updatedPlan | Out-File -FilePath $PlanFile -Encoding utf8
Write-Host "  Updated plan file: $PlanFile" -ForegroundColor DarkGray

# 3. Write .planning-DAG.json for backward compat
$planDir = Split-Path $PlanFile
$planningDagOut = Join-Path $planDir ".planning-DAG.json"
$expandedEpicMatches = [regex]::Matches($updatedPlan, $epicPattern)
$dagNodes = @()
foreach ($exm in $expandedEpicMatches) {
    $ref = $exm.Groups[1].Value
    $deps = if ($proposedDeps.ContainsKey($ref)) { @($proposedDeps[$ref]) } else { @() }
    # Find role from room config
    $role = "engineer"
    $matchedRoom = $rooms | Where-Object {
        $cf = Join-Path $_.FullName "config.json"
        if (Test-Path $cf) {
            $cfg = Get-Content $cf -Raw | ConvertFrom-Json
            $tr = if ($cfg.task_ref) { $cfg.task_ref } else { "" }
            $tr -eq $ref
        }
    }
    if ($matchedRoom) {
        $rmCfg = Get-Content (Join-Path $matchedRoom.FullName "config.json") -Raw | ConvertFrom-Json
        if ($rmCfg.assignment -and $rmCfg.assignment.assigned_role) { $role = $rmCfg.assignment.assigned_role }
    }
    $dagNodes += [ordered]@{
        task_ref        = $ref
        title           = $exm.Groups[2].Value.Trim()
        role            = $role
        candidate_roles = @($role)
        depends_on      = $deps
    }
}
$planningDag = [ordered]@{
    generated_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    source            = (Split-Path $PlanFile -Leaf)
    stage             = "review"
    total_nodes       = $dagNodes.Count
    nodes             = $dagNodes
    topological_order = @($dagNodes | ForEach-Object { $_.task_ref })
}
$planningDag | ConvertTo-Json -Depth 10 | Out-File -FilePath $planningDagOut -Encoding utf8
Write-Host "  Written: $planningDagOut" -ForegroundColor DarkGray

# 4. Rebuild DAG.json from updated room configs
if (Test-Path $buildDag) {
    $null = & $buildDag -WarRoomsDir $WarRoomsDir
    Write-Host "  Rebuilt: DAG.json" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[DEP-REVIEW] Dependencies updated and approved." -ForegroundColor Green

# Clean up temp room
if ($ownsTempRoom) { Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue }
