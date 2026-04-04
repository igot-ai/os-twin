<#
.SYNOPSIS
    Resolves a set of skills for a specific role following a hierarchical resolution strategy.

.DESCRIPTION
    Always loads role.json from HOME ~/.ostwin/roles/{RoleName}/role.json (authoritative source).
    Searches both 'capabilities' and 'skill_refs' fields from the role definition.

    Resolution strategy (for each ref):
    1. Registry lookup: from ~/.ostwin/roles/registry.json
    2. Local skills fallback: from skills/<ref>/SKILL.md
    3. Backend skills: fetched from dashboard API when not found locally

    Deduplication is performed based on skill directory name (identifier).

.PARAMETER RoleName
    Name of the role (e.g., engineer, architect).
.PARAMETER RolePath
    Legacy parameter — no longer used for role.json loading.
    Role.json is always loaded from ~/.ostwin/roles/{RoleName}/.
.PARAMETER SkillsBaseDir
    Optional. Override for the base skills directory (defaults to ../../skills).
.PARAMETER DashboardUrl
    Optional. Dashboard API base URL (default: http://localhost:9000).
.PARAMETER ApiKey
    Optional. API key for dashboard authentication (default: $env:OSTWIN_API_KEY).

.OUTPUTS
    [PSCustomObject[]] Collection of objects with Name, Path (to SKILL.md), and Tier.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$RoleName,

    [Parameter(Mandatory=$true)]
    [string]$RolePath,

    [string]$SkillsBaseDir = '',

    [string]$DashboardUrl = '',

    [string]$ApiKey = ''
)

# --- Initialize base paths ---
if (-not $SkillsBaseDir) {
    # Default to .agents/skills relative to this script's location
    $SkillsBaseDir = Resolve-Path (Join-Path $PSScriptRoot ".." ".." "skills")
}

if (-not (Test-Path $SkillsBaseDir)) {
    Write-Warning "Skills base directory not found: $SkillsBaseDir"
    return @()
}

# --- Initialize dashboard settings ---
if (-not $DashboardUrl) {
    $DashboardUrl = if ($env:DASHBOARD_URL) { $env:DASHBOARD_URL } else { "http://localhost:9000" }
}
if (-not $ApiKey) {
    $ApiKey = $env:OSTWIN_API_KEY
}

$resolvedSkills = @{} # Using hashtable for deduplication by Name

# Platform gate: returns $true if the skill's SKILL.md declares a platform list that
# includes the current OS, or if no platform field is present (cross-platform).
function Test-SkillPlatform {
    param([string]$SkillMdPath)
    if (-not (Test-Path $SkillMdPath)) { return $true }
    $content = Get-Content $SkillMdPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $true }
    if ($content -match '(?m)^platform:\s*\[([^\]]+)\]') {
        $platforms = $Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") }
        $currentOS = if ($IsWindows) { 'windows' } elseif ($IsMacOS) { 'macos' } else { 'linux' }
        return ($platforms -contains $currentOS)
    }
    return $true   # No platform field = cross-platform
}

# --- Load role.json from HOME ~/.ostwin/roles/{RoleName}/ (authoritative source) ---
$ostwinHome = Join-Path $env:HOME ".ostwin"
$homeRolePath = Join-Path $ostwinHome "roles" $RoleName
$jsonFile = Join-Path $homeRolePath "role.json"

Write-Verbose "Loading role.json from HOME: $jsonFile"

if (Test-Path $jsonFile) {
    try {
        $roleData = Get-Content $jsonFile -Raw | ConvertFrom-Json

        # Collect refs from both capabilities and skill_refs
        $allRefs = @()
        if ($roleData.skill_refs) {
            $allRefs += @($roleData.skill_refs)
        }
        if ($roleData.capabilities) {
            $allRefs += @($roleData.capabilities)
        }
        # Deduplicate
        $allRefs = $allRefs | Select-Object -Unique

        if ($allRefs.Count -gt 0) {
            # Registry always from HOME ~/.ostwin/roles/registry.json
            $registryFile = Join-Path $ostwinHome "roles" "registry.json"
            $registry = if (Test-Path $registryFile) { Get-Content $registryFile -Raw | ConvertFrom-Json } else { $null }

            foreach ($ref in $allRefs) {
                # Look for ref in registry first
                $skillFromRegistry = if ($registry) { $registry.skills.available | Where-Object { $_.name -eq $ref } } else { $null }
                $registryPath = $null
                
                if ($skillFromRegistry) {
                    $registryPath = Join-Path (Split-Path $registryFile -Parent) ".." $skillFromRegistry.path
                    if (Test-Path $registryPath) {
                        if (-not (Test-SkillPlatform -SkillMdPath $registryPath)) {
                            Write-Verbose "Skipping platform-incompatible skill '$ref' (registry)"
                            continue
                        }
                        $resolvedSkills[$ref] = [PSCustomObject]@{
                            Name = $ref
                            Path = $registryPath
                            Tier = "Explicit"
                        }
                        continue
                    }
                }

                # Check if already resolved
                if ($resolvedSkills.ContainsKey($ref)) {
                    continue
                }

                # Fallback to skills/<ref>/SKILL.md
                $fallbackPath = Join-Path $SkillsBaseDir $ref "SKILL.md"

                if (Test-Path $fallbackPath) {
                    if (-not (Test-SkillPlatform -SkillMdPath $fallbackPath)) {
                        Write-Verbose "Skipping platform-incompatible skill '$ref' (fallback)"
                        continue
                    }
                    $resolvedSkills[$ref] = [PSCustomObject]@{
                        Name = $ref
                        Path = $fallbackPath
                        Tier = "Explicit"
                    }
                }
                else {
                    # --- 4. Backend Fallback: search dashboard API ---
                    $fetched = $false
                    if ($ApiKey) {
                        try {
                            $headers = @{ "X-API-Key" = $ApiKey }
                            $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($ref))&role=$([uri]::EscapeDataString($RoleName))"
                            $response = Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop

                            # Find matching skill from search results
                            $matchedSkill = $null
                            if ($response -is [array] -and $response.Count -gt 0) {
                                # Prefer exact name match, then first result
                                $matchedSkill = $response | Where-Object { $_.name -eq $ref } | Select-Object -First 1
                                if (-not $matchedSkill) {
                                    $matchedSkill = $response[0]
                                }
                            }

                            if ($matchedSkill -and $matchedSkill.relative_path -and $matchedSkill.content -and (Test-SkillPlatform -SkillMdPath (Join-Path $SkillsBaseDir ($matchedSkill.relative_path -replace '^skills/', '') "SKILL.md"))) {
                                # Determine local destination using relative_path
                                # relative_path is like "skills/roles/engineer/write-tests"
                                $relPath = $matchedSkill.relative_path
                                # Strip leading "skills/" prefix to get path relative to SkillsBaseDir
                                $subPath = $relPath -replace '^skills/', ''
                                $localSkillDir = Join-Path $SkillsBaseDir $subPath
                                $localSkillMd = Join-Path $localSkillDir "SKILL.md"

                                # Create directory and write SKILL.md
                                if (-not (Test-Path $localSkillDir)) {
                                    New-Item -ItemType Directory -Path $localSkillDir -Force | Out-Null
                                }

                                # Reconstruct full SKILL.md with frontmatter
                                $frontmatter = @"
---
name: $($matchedSkill.name)
description: "$($matchedSkill.description)"
tags: [$($matchedSkill.tags -join ', ')]
trust_level: $($matchedSkill.trust_level)
---
"@
                                $fullContent = "$frontmatter`n`n$($matchedSkill.content)"
                                $fullContent | Out-File -FilePath $localSkillMd -Encoding utf8 -Force

                                $resolvedSkills[$ref] = [PSCustomObject]@{
                                    Name = $matchedSkill.name
                                    Path = $localSkillMd
                                    Tier = "Backend"
                                }
                                Write-Verbose "Fetched skill '$ref' from backend → $localSkillMd"
                                $fetched = $true
                            }
                        }
                        catch {
                            Write-Verbose "Backend skill search failed for '$ref': $_"
                        }
                    }

                    if (-not $fetched) {
                        $errorMsg = "Skill Not Found: Explicitly referenced skill '$ref' not found."
                        if ($registryPath) {
                            $errorMsg += " Registry path tried: $registryPath."
                        }
                        $errorMsg += " Fallback path tried: $fallbackPath."
                        if ($ApiKey) {
                            $errorMsg += " Backend search also failed."
                        }
                        throw $errorMsg
                    }
                }
            }
        }
    }
    catch {
        if ($_.ToString() -match "Skill Not Found") {
            throw $_
        }
        Write-Warning "Failed to parse role.json for skills: $_"
    }
}

return $resolvedSkills.Values | Sort-Object Tier, Name
