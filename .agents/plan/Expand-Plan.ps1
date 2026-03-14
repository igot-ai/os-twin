<#
.SYNOPSIS
    Expands underspecified epics in a plan file using AI.

.DESCRIPTION
    Takes a raw PLAN.md as input and produces a PLAN.refined.md with maximized detail:
    expanded descriptions, DoD checklists, Acceptance Criteria, dependency declarations,
    and complexity estimates for every Epic.

.PARAMETER PlanFile
    Path to the input plan file.
.PARAMETER OutFile
    Path to write the expanded plan. Defaults to <PlanFile>.refined.md
.PARAMETER DryRun
    Parse and show what would be expanded, without modifying or writing any files.

.EXAMPLE
    ./Expand-Plan.ps1 -PlanFile ./PLAN.md
    ./Expand-Plan.ps1 -PlanFile ./PLAN.md -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$PlanFile,

    [string]$OutFile,

    [switch]$DryRun,
    
    [string]$AgentCmd = 'deepagents'
)

if (-not $OutFile) {
    $OutFile = $PlanFile -replace "(?i)\.md$", ".refined.md"
    if ($OutFile -eq $PlanFile) {
        $OutFile = $PlanFile + ".refined.md"
    }
}

if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$planContent = Get-Content $PlanFile -Raw
$newPlanContent = $planContent

# Regex to find Epics
$epicPattern = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'

$epicMatches = [regex]::Matches($planContent, $epicPattern)

if ($epicMatches.Count -eq 0) {
    Write-Host "No Epics found in $PlanFile to expand."
    exit 0
}

# AI agent configuration
$model = "gemini-3.1-pro-preview"
$systemPrompt = @"
You are an expert product manager and technical planner.
Your job is to expand underspecified epics into highly detailed plan sections.
The output MUST adhere to the following format exactly:

## Epic: [EPIC-ID] — [Title]

[3-5 paragraphs of detailed description, context, and requirements.]

depends_on: [array of dependencies if any, e.g., [EPIC-001, EPIC-002]]
complexity: [S/M/L/XL]

#### Definition of Done
- [ ] [Requirement 1]
- [ ] [Requirement 2]
- [ ] [Requirement 3]
- [ ] [Requirement 4]
- [ ] [Requirement 5]

#### Acceptance Criteria
- [ ] [Testable criteria 1]
- [ ] [Testable criteria 2]
- [ ] [Testable criteria 3]
- [ ] [Testable criteria 4]
- [ ] [Testable criteria 5]

Do not include any conversational filler. Only output the expanded epic text.
"@

# Process from bottom to top to preserve indexes when replacing
for ($i = $epicMatches.Count - 1; $i -ge 0; $i--) {
    $match = $epicMatches[$i]
    $epicPrefix = $match.Groups[1].Value.Trim()
    $epicId = $match.Groups[2].Value
    $epicTitle = $match.Groups[3].Value
    
    $startIdx = $match.Index
    $headerLength = $match.Length
    
    # Stop at any header level equal to or higher than the current epic
    if ($epicPrefix -match '^###') {
        $nextSectionPattern = '(?m)^#{1,3}\s+|^---$'
    } else {
        $nextSectionPattern = '(?m)^#{1,2}\s+|^---$'
    }
    
    $nextMatch = [regex]::Match($planContent.Substring($startIdx + $headerLength), $nextSectionPattern)
    
    if ($nextMatch.Success) {
        $endIdx = $startIdx + $headerLength + $nextMatch.Index
    } else {
        $endIdx = $planContent.Length
    }
    $epicText = $planContent.Substring($startIdx, $endIdx - $startIdx)
    
    # Check if underspecified: < 5 bullets in DoD or AC
    $dodMatch = [regex]::Match($epicText, '(?is)#### Definition of Done(.*?)(?=####|\z)')
    $acMatch = [regex]::Match($epicText, '(?is)#### Acceptance Criteria(.*?)(?=####|\z)')
    
    $dodCount = 0
    if ($dodMatch.Success) {
        $dodCount = ([regex]::Matches($dodMatch.Value, '(?im)^-\s+\[[ x]\]')).Count
    }
    
    $acCount = 0
    if ($acMatch.Success) {
        $acCount = ([regex]::Matches($acMatch.Value, '(?im)^-\s+\[[ x]\]')).Count
    }
    
    if ($dodCount -lt 5 -or $acCount -lt 5) {
        Write-Host "Expanding $epicId — $epicTitle..."
        
        if ($DryRun) {
            Write-Host "  [DryRun] Would expand $epicId" -ForegroundColor Yellow
            continue
        }
        
        $promptContent = $systemPrompt + "`n`n" + $epicText
        
        # Call deepagents
        $outputFile = [System.IO.Path]::GetTempFileName()
        & $AgentCmd -n $promptContent --model $model -q --auto-approve > $outputFile
        
        if ($LASTEXITCODE -eq 0) {
            $expandedText = Get-Content $outputFile -Raw
            $expandedText = $expandedText -replace '^```[a-zA-Z]*\n', '' -replace '\n```\s*$', ''
            # Replace in original plan (using substring replacement)
            $newPlanContent = $newPlanContent.Remove($startIdx, $endIdx - $startIdx).Insert($startIdx, $expandedText.Trim() + "`n`n")
            Write-Host "  Success: $epicId expanded." -ForegroundColor Green
        } else {
            Write-Error "Failed to expand $epicId"
        }
        
        Remove-Item $outputFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "$epicId is already well-specified. Skipping."
    }
}

if (-not $DryRun) {
    $newPlanContent | Out-File $OutFile -Encoding UTF8
    Write-Host "Refined plan written to $OutFile" -ForegroundColor Green
}
exit 0
