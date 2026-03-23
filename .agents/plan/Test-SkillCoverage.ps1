<#
.SYNOPSIS
    Performs pre-flight skill coverage check for a project plan.
    Auto-scaffolds missing dynamic roles so they can run via Start-DynamicRole.ps1.
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
$scaffoldedRoles = [System.Collections.Generic.List[string]]::new()
$rolesDir = Join-Path $agentsDir "roles"

# Resolve the Ostwin installation directory (where _base scripts live)
$installDir = $null
if ($env:OSTWIN_HOME -and (Test-Path $env:OSTWIN_HOME)) {
    $installDir = $env:OSTWIN_HOME
} elseif (Test-Path (Join-Path $agentsDir "roles" "_base" "Start-DynamicRole.ps1")) {
    $installDir = $agentsDir
} else {
    # Fall back to ~/.ostwin
    $fallback = Join-Path ([Environment]::GetFolderPath('UserProfile')) ".ostwin"
    if (Test-Path $fallback) { $installDir = $fallback }
}

foreach ($entry in $PlanParsed) {
    $entryRoles = @($entry.Roles)
    if ($entryRoles.Count -eq 0) { $entryRoles = @("engineer") }

    foreach ($currentRole in $entryRoles) {
        # Check if role exists
        $rolePath = Join-Path $rolesDir $currentRole
        if (-not (Test-Path $rolePath)) {
            # --- Auto-scaffold dynamic role ---
            # Create a minimal role folder so Start-DynamicRole.ps1 can handle it.
            # This enables plans to reference any role name and have it work at runtime.
            $scaffolded = $false
            if ($installDir) {
                $dynamicRunner = Join-Path $installDir "roles" "_base" "Start-DynamicRole.ps1"
                if (Test-Path $dynamicRunner) {
                    New-Item -ItemType Directory -Path $rolePath -Force | Out-Null

                    # Extract description from the plan entry
                    $roleDesc = if ($entry.Objective) { $entry.Objective }
                                elseif ($entry.Description) { $entry.Description }
                                else { "$currentRole specialist agent" }

                    # Create role.json
                    $roleData = @{
                        name          = $currentRole
                        description   = $roleDesc
                        capabilities  = @()
                        prompt_file   = "ROLE.md"
                        quality_gates = @()
                        skills        = @("global", "roles")
                        cli           = "agent"
                        model         = "gemini-3-flash-preview"
                        timeout       = 600
                    }
                    $roleData | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $rolePath "role.json") -Encoding utf8

                    # Create a minimal ROLE.md
                    @"
# $currentRole

You are a **$currentRole** specialist agent.

## Description

$roleDesc

## Guidelines

1. Follow the task brief carefully
2. Write clean, tested code
3. Document your work
4. Report progress and blockers
"@ | Out-File -FilePath (Join-Path $rolePath "ROLE.md") -Encoding utf8

                    # Register in registry.json if not already there
                    $registryPath = Join-Path $rolesDir "registry.json"
                    if (Test-Path $registryPath) {
                        $registry = Get-Content $registryPath -Raw | ConvertFrom-Json
                        $alreadyRegistered = $registry.roles | Where-Object { $_.name -eq $currentRole }
                        if (-not $alreadyRegistered) {
                            $newEntry = [PSCustomObject]@{
                                name               = $currentRole
                                description         = $roleDesc
                                runner             = "roles/_base/Start-DynamicRole.ps1"
                                definition         = "roles/$currentRole/role.json"
                                prompt             = "roles/$currentRole/ROLE.md"
                                default_assignment = $false
                                capabilities       = @()
                            }
                            $registry.roles += $newEntry
                            $registry | ConvertTo-Json -Depth 10 | Out-File -FilePath $registryPath -Encoding utf8
                        }
                    }

                    if ($scaffoldedRoles -notcontains $currentRole) {
                        $scaffoldedRoles.Add($currentRole)
                    }
                    $scaffolded = $true
                    Write-Host "[PRE-FLIGHT] Auto-scaffolded dynamic role '$currentRole' for $($entry.TaskRef)" -ForegroundColor Yellow
                }
            }

            if (-not $scaffolded) {
                # Don't spam duplicates if multiple epics miss the same role
                $msg = "Role '$currentRole' not found for $($entry.TaskRef)"
                if ($missingSkills -notcontains $msg) {
                    $missingSkills.Add($msg)
                }
            }
            continue
        }

        # Check if role has required skills (simplified check for now)
        $roleJson = Join-Path $rolePath "role.json"
        if (Test-Path $roleJson) {
            $roleData = Get-Content $roleJson -Raw | ConvertFrom-Json
            if ($roleData.skill_refs) {
                foreach ($skill in $roleData.skill_refs) {
                    # Search hierarchically: skills/<name>, skills/global/<name>, skills/roles/*/<name>
                    $found = $false
                    $searchPaths = @(
                        (Join-Path $agentsDir "skills" $skill),
                        (Join-Path $agentsDir "skills" "global" $skill)
                    )
                    # Search all role skill directories
                    $rolesSkillDir = Join-Path $agentsDir "skills" "roles"
                    if (Test-Path $rolesSkillDir) {
                        Get-ChildItem -Path $rolesSkillDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                            $searchPaths += Join-Path $_.FullName $skill
                        }
                    }
                    foreach ($sp in $searchPaths) {
                        if (Test-Path $sp) { $found = $true; break }
                    }
                    if (-not $found) {
                        $msg = "Skill '$skill' required by role '$currentRole' not found (used in $($entry.TaskRef))"
                        if ($missingSkills -notcontains $msg) {
                            $missingSkills.Add($msg)
                        }
                    }
                }
            }
        }
    }
}

if ($scaffoldedRoles.Count -gt 0) {
    Write-Host "[PRE-FLIGHT] Scaffolded $($scaffoldedRoles.Count) dynamic role(s): $($scaffoldedRoles -join ', ')" -ForegroundColor Green
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
