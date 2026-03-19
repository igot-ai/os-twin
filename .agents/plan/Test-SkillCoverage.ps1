<#
.SYNOPSIS
    Performs pre-flight skill coverage check for a project plan.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    $PlanParsed,
    
    [string]$ProjectDir = (Get-Location).Path,

    [string]$RoomDir = ""
)

$agentsDir = Join-Path $ProjectDir ".agents"
$config = Get-OstwinConfig
$mode = "warn"
if ($config.manager.preflight_skill_check) {
    $mode = $config.manager.preflight_skill_check
}

if ($mode -eq "off") { return $true }

Write-Host "[PRE-FLIGHT] Checking skill coverage..." -ForegroundColor Cyan

$missingSkills = [System.Collections.Generic.List[string]]::new()
$rolesDir = Join-Path $agentsDir "roles"

foreach ($entry in $PlanParsed) {
    $entryRoles = @($entry.Roles)
    $primaryRole = if ($entryRoles.Count -gt 0) { $entryRoles[0] } else { "engineer" }
    
    # Check if role exists
    $rolePath = Join-Path $rolesDir $primaryRole
    if (-not (Test-Path $rolePath)) {
        $missingSkills.Add("Role '$primaryRole' not found for $($entry.TaskRef)")
        continue
    }
    
    # Check if role has required skills (simplified check for now)
    $roleJson = Join-Path $rolePath "role.json"
    if (Test-Path $roleJson) {
        $roleData = Get-Content $roleJson -Raw | ConvertFrom-Json
        if ($roleData.skill_refs) {
            foreach ($skill in $roleData.skill_refs) {
                $skillPath = Join-Path $agentsDir "skills" $skill
                if (-not (Test-Path $skillPath)) {
                    $missingSkills.Add("Skill '$skill' required by role '$primaryRole' not found (used in $($entry.TaskRef))")
                }
            }
        }
    }
}

if ($missingSkills.Count -gt 0) {
    $report = "### Skill Coverage Gap Report`n`n"
    foreach ($ms in $missingSkills) {
        Write-Warning "[PRE-FLIGHT] $ms"
        $report += "- [ ] $ms`n"
    }
    
    # Post to channel if Post-Message and RoomDir are available
    $postMessage = Join-Path $agentsDir "channel" "Post-Message.ps1"
    if ($RoomDir -and (Test-Path $postMessage)) {
        & $postMessage -RoomDir $RoomDir -From "manager" -To "architect" -Type "error" -Ref "PRE-FLIGHT" -Body $report | Out-Null
    }
    
    if ($mode -eq "halt") {
        Write-Error "Pre-flight skill check failed. Halting execution."
        exit 1
    }
} else {
    Write-Host "[PRE-FLIGHT] All required skills and roles verified." -ForegroundColor Green
}

return $true
