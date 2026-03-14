<#
.SYNOPSIS
    Expands an underspecified plan file via AI refinement.

.DESCRIPTION
    Reads a raw PLAN.md file and uses the deepagents CLI to expand
    the epic descriptions, Definition of Done, and Acceptance Criteria.
    Writes the refined content to PLAN.refined.md.

.PARAMETER PlanFile
    Path to the original plan markdown file.
.PARAMETER ProjectDir
    Project root. Default: current directory.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$PlanFile,

    [string]$ProjectDir = (Get-Location).Path
)

# --- Resolve paths ---
$agentsDir = Join-Path $ProjectDir ".agents"
if (-not (Test-Path $agentsDir)) {
    $agentsDir = $PSScriptRoot | Split-Path
}

$invokeAgent = Join-Path $agentsDir "roles" "_base" "Invoke-Agent.ps1"

if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$planContent = Get-Content $PlanFile -Raw

$refinedFile = $PlanFile -replace '\.md$', '.refined.md'
if ($refinedFile -eq $PlanFile) {
    $refinedFile = "$PlanFile.refined.md"
}

# Provide prompt for AI refinement
$prompt = @"
You are a senior technical program manager and architect. 
Your task is to refine the following project plan. The plan is underspecified.
For each EPIC, you must:
1. Expand the description to be detailed and comprehensive (at least 2 paragraphs or bullet points).
2. Generate a robust "Definition of Done" (at least 3 actionable items as markdown checkboxes).
3. Generate comprehensive "Acceptance Criteria" (at least 3 testable items as markdown checkboxes).

PRESERVE the exact structure of the original file including headings (e.g. `### EPIC-NNN — Title`), config blocks, and `depends_on:` declarations.
DO NOT remove any existing epics, tasks, or configuration. 
Only expand the content of the epics to be more detailed and actionable.

Return ONLY the refined markdown content, no extra commentary.

<original_plan>
$planContent
</original_plan>
"@

Write-Host "Invoking AI plan refinement..." -ForegroundColor Cyan

# Use the universal Invoke-Agent script with a dummy room directory.
# We just need it to run deepagents with the prompt.
$tempRoomDir = Join-Path $agentsDir ".war-rooms" "plan-refinement-temp"
if (-not (Test-Path $tempRoomDir)) {
    New-Item -ItemType Directory -Path $tempRoomDir -Force | Out-Null
}

$result = & $invokeAgent -RoomDir $tempRoomDir -RoleName "architect" -Prompt $prompt -TimeoutSeconds 120

if ($result.ExitCode -ne 0) {
    Write-Error "AI Refinement failed."
    exit 1
}

$refinedContent = $result.Output

# Clean up any potential markdown code blocks returned by AI
if ($refinedContent -match '(?s)^```markdown\s*\n(.*)\n```\s*$') {
    $refinedContent = $Matches[1]
} elseif ($refinedContent -match '(?s)^```\s*\n(.*)\n```\s*$') {
    $refinedContent = $Matches[1]
}

# Write back to PLAN.refined.md
$refinedContent | Out-File -FilePath $refinedFile -Encoding utf8 -NoNewline
Write-Host "Refined plan written to: $refinedFile" -ForegroundColor Green

# Cleanup
if (Test-Path $result.PidFile) {
    Remove-Item $result.PidFile -Force -ErrorAction SilentlyContinue
}
Remove-Item $tempRoomDir -Recurse -Force -ErrorAction SilentlyContinue

exit 0
