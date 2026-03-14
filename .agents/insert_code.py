import sys

file_path = "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/Start-Plan.ps1"

with open(file_path, "r") as f:
    content = f.read()

start_marker = "# --- Plan Expansion (Manager Loop Startup Integration) ---"
end_marker = "# --- Extract plan_id from embedded config ---"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found")
    sys.exit(1)

new_code = """# --- Plan Expansion (Manager Loop Startup Integration) ---
$config = Get-OstwinConfig

$planContentForCheck = Get-Content $PlanFile -Raw
$hasUnderspecified = $false

$epicPatternCheck = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'
$dodPatternCheck = '(?s)#### Definition of Done\s*\\n(.*?)(?=####|###|---|\\z)'
$acPatternCheck = '(?s)#### Acceptance Criteria\s*\\n(.*?)(?=####|###|---|\\z)'
$descPatternCheck = '(?m)^(?s)(?:## Epic:\s+|###\s+)EPIC-\d+\s*[—–-]\s*.+?\\n(.*?)(?=####|\\z)'

$epicMatchesCheck = [regex]::Matches($planContentForCheck, $epicPatternCheck)
foreach ($em in $epicMatchesCheck) {
    $epicStart = $em.Index
    $nextMatch = $epicMatchesCheck | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextMatch) { $nextMatch.Index } else { $planContentForCheck.Length }
    $epicSection = $planContentForCheck.Substring($epicStart, $epicEnd - $epicStart)

    $descBody = ""
    if ($epicSection -match $descPatternCheck) { $descBody = $Matches[1].Trim() }
    
    $dodCount = 0
    if ($epicSection -match $dodPatternCheck) {
        $dodCount = ([regex]::Matches($Matches[1], '- \[[ x]\]\s*(.+)')).Count
    }
    
    $acCount = 0
    if ($epicSection -match $acPatternCheck) {
        $acCount = ([regex]::Matches($Matches[1], '- \[[ x]\]\s*(.+)')).Count
    }

    $bulletCount = 0
    if ($descBody) {
        $bulletCount = ([regex]::Matches($descBody, '(?m)^[-*]\s+')).Count
    }

    if ($dodCount -lt 1 -or $acCount -lt 1 -or $bulletCount -lt 2) {
        $hasUnderspecified = $true
        break
    }
}

$shouldExpand = $Expand -or ($config.manager -and $config.manager.auto_expand_plan -eq $true) -or $hasUnderspecified

if ($shouldExpand -and ($PlanFile -notmatch '\.refined\.md$')) {
    $expandScript = Join-Path $agentsDir "plan" "Expand-Plan.ps1"
    if (Test-Path $expandScript) {
        if ($hasUnderspecified) {
            Write-Host ""
            Write-Host "=== Plan Refinement Required ===" -ForegroundColor Yellow
            Write-Host "Detected underspecified epics. Auto-triggering plan refinement..." -ForegroundColor Yellow
            $Review = $true
        } else {
            Write-Log -Message "Auto-expanding plan: $PlanFile" -Level "INFO" -Source "manager"
        }
        
        $refinedFile = $PlanFile -replace "(?i)\.md`$", ".refined.md"
        if ($refinedFile -eq $PlanFile) { $refinedFile = $PlanFile + ".refined.md" }

        $expandArgs = @{
            PlanFile = $PlanFile
            OutFile = $refinedFile
        }
        if ($DryRun) { $expandArgs.Add("DryRun", $true) }

        & $expandScript @expandArgs

        if ($LASTEXITCODE -ne 0 -and $?) {
            Write-Error "Failed to expand plan."
            exit 1
        }
        
        if (-not $DryRun -and (Test-Path $refinedFile)) {
            $diffSummary = git diff --no-index --stat $PlanFile $refinedFile | Out-String
            if (-not $diffSummary) { $diffSummary = "No changes or git not available" }
            Write-Log -Message "Plan expansion diff:\\n$diffSummary" -Level "INFO" -Source "manager"
            
            $PlanFile = $refinedFile
            
            if ($Review) {
                Write-Host ""
                Write-Host "Plan expanded to: $PlanFile" -ForegroundColor Green
                Write-Host "Please review the expanded plan." -ForegroundColor Green
                Read-Host -Prompt "Press [Enter] to approve and continue, or Ctrl+C to abort..."
            }
        }
    } else {
        Write-Warning "Expand-Plan.ps1 not found at $expandScript, skipping expansion."
    }
}

$planContent = Get-Content $PlanFile -Raw

# --- Parse plan: extract epics and tasks ---
$parsed = [System.Collections.Generic.List[PSObject]]::new()
$roomIndex = 1

# Pattern: ### EPIC-NNN or ### TASK-NNN sections
$epicPattern = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'
$taskPattern = '- \[[ x]\]\s+(TASK-\d+)\s*[—–-]\s*(.+)'
$dodPattern = '(?s)#### Definition of Done\s*\\n(.*?)(?=####|###|---|\\z)'
$acPattern = '(?s)#### Acceptance Criteria\s*\\n(.*?)(?=####|###|---|\\z)'
$depsPattern = '(?m)^\s*depends_on:\s*\[([^\]]*)\]\s*$'

# Extract epics
$epicMatches = [regex]::Matches($planContent, $epicPattern)

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[2].Value
    $epicDesc = $em.Groups[3].Value.Trim()

    # Find the epic section content
    $epicStart = $em.Index
    $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextEpicMatch) { $nextEpicMatch.Index } else { $planContent.Length }
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # Extract description body
    $descBody = ""
    $descPattern = '(?m)^(?s)(?:## Epic:\s+|###\s+)EPIC-\d+\s*[—–-]\s*.+?\\n(.*?)(?=####|\\z)'
    if ($epicSection -match $descPattern) {
        $descBody = $Matches[1].Trim()
    }

    # Extract DoD
    $dod = @()
    if ($epicSection -match $dodPattern) {
        $dodBlock = $Matches[1]
        $dod = [regex]::Matches($dodBlock, '- \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
    }

    # Extract AC
    $ac = @()
    if ($epicSection -match $acPattern) {
        $acBlock = $Matches[1]
        $ac = [regex]::Matches($acBlock, '- \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
    }

    # Extract depends_on
    $depsOn = @()
    if ($epicSection -match $depsPattern) {
        $rawDeps = $Matches[1]
        if ($rawDeps.Trim()) {
            $depsOn = ($rawDeps -split ',') | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ }
        }
    }

    $parsed.Add([PSCustomObject]@{
        RoomId      = "room-$('{0:D3}' -f $roomIndex)"
        TaskRef     = $epicRef
        Description = $epicDesc
        DescBody    = $descBody
        DoD         = $dod
        AC          = $ac
        DependsOn   = $depsOn
        Type        = 'epic'
    })
    $roomIndex++
}

# If no epics found, try parsing standalone tasks
if ($parsed.Count -eq 0) {
    $taskMatches = [regex]::Matches($planContent, $taskPattern)
    foreach ($tm in $taskMatches) {
        $parsed.Add([PSCustomObject]@{
            RoomId      = "room-$('{0:D3}' -f $roomIndex)"
            TaskRef     = $tm.Groups[1].Value
            Description = $tm.Groups[2].Value.Trim()
            DescBody    = ""
            DoD         = @()
            AC          = @()
            DependsOn   = @()
            Type        = 'task'
        })
        $roomIndex++
    }
}

if ($parsed.Count -eq 0) {
    Write-Error "No epics or tasks found in plan file: $PlanFile"
    exit 1
}

"""

new_file_content = content[:start_idx] + new_code + content[end_idx:]

with open(file_path, "w") as f:
    f.write(new_file_content)

print("Done")
