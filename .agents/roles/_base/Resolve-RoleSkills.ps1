<#
.SYNOPSIS
    Resolves a set of skills for a specific role following a hierarchical resolution strategy.

.DESCRIPTION
    Skill refs are collected from multiple sources in priority order:
      1. Plan-level override: ~/.ostwin/.agents/plans/{plan_id}.roles.json → {role}.skill_refs
      2. War-room config:    {RoomDir}/config.json → skill_refs
      3. Global role.json:   ~/.ostwin/roles/{RoleName}/role.json → skill_refs + capabilities
      4. Brief-based match:  {RoomDir}/brief.md keywords matched against available skill names/tags

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
.PARAMETER RoomDir
    Optional. War-room directory path — used to read config.json (for plan_id
    and room-level skill_refs) and brief.md (for keyword-based skill matching).
.PARAMETER PlanId
    Optional. Explicit plan ID. If omitted, derived from {RoomDir}/config.json.
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

    [string]$RoomDir = '',

    [string]$PlanId = '',

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

# Enabled gate: returns $false if the skill's SKILL.md explicitly declares enabled: false
function Test-SkillEnabled {
    param([string]$SkillMdPath)
    if (-not (Test-Path $SkillMdPath)) { return $true }
    $content = Get-Content $SkillMdPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $true }
    # Match enabled: false or enabled: 0 (case-insensitive)
    if ($content -match '(?m)^enabled:\s*(false|0)') {
        return $false
    }
    return $true
}

# --- Resolve OSTWIN_HOME ---
$ostwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $env:HOME ".ostwin" }

# --- Derive PlanId from room config if not provided ---
$roomCfg = $null
if ($RoomDir -and (Test-Path (Join-Path $RoomDir "config.json"))) {
    try {
        $roomCfg = Get-Content (Join-Path $RoomDir "config.json") -Raw | ConvertFrom-Json
        if (-not $PlanId -and $roomCfg.plan_id) {
            $PlanId = $roomCfg.plan_id
            Write-Verbose "Derived PlanId='$PlanId' from room config.json"
        }
    } catch { Write-Verbose "Failed to parse room config.json: $_" }
}

# --- Collect skill refs from all sources (priority order) ---
$allRefs = @()

# Priority 1: Plan-level role override — ~/.ostwin/.agents/plans/{plan_id}.roles.json
if ($PlanId) {
    $planRolesFile = Join-Path $ostwinHome ".agents" "plans" "$PlanId.roles.json"
    if (Test-Path $planRolesFile) {
        try {
            $planRoles = Get-Content $planRolesFile -Raw | ConvertFrom-Json
            if ($planRoles.$RoleName -and $planRoles.$RoleName.skill_refs) {
                $allRefs += @($planRoles.$RoleName.skill_refs)
                Write-Verbose "Plan-level skill_refs for '$RoleName': $($planRoles.$RoleName.skill_refs -join ', ')"
            }
        } catch { Write-Verbose "Failed to parse plan roles file: $_" }
    }
}

# Priority 2: War-room config.json skill_refs (set by manager during assignment)
if ($roomCfg -and $roomCfg.skill_refs) {
    $allRefs += @($roomCfg.skill_refs)
    Write-Verbose "Room config skill_refs: $($roomCfg.skill_refs -join ', ')"
}

# Priority 3: Global role.json — ~/.ostwin/roles/{RoleName}/role.json (base definition)
$homeRolePath = Join-Path $ostwinHome "roles" $RoleName
$jsonFile = Join-Path $homeRolePath "role.json"
$roleData = $null

Write-Verbose "Loading role.json from HOME: $jsonFile"

if (Test-Path $jsonFile) {
    try {
        $roleData = Get-Content $jsonFile -Raw | ConvertFrom-Json

        if ($roleData.skill_refs) {
            $allRefs += @($roleData.skill_refs)
        }
        if ($roleData.capabilities) {
            $allRefs += @($roleData.capabilities)
        }
    }
    catch {
        Write-Warning "Failed to parse role.json: $_"
    }
}

# Deduplicate across all sources
$allRefs = @($allRefs | Select-Object -Unique)
Write-Verbose "Combined skill refs ($($allRefs.Count)): $($allRefs -join ', ')"

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
                if (-not (Test-SkillEnabled -SkillMdPath $registryPath)) {
                    Write-Verbose "Skipping disabled skill '$ref' (registry)"
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
        if ($resolvedSkills.ContainsKey($ref)) { continue }

        # Fallback: hierarchical search matching Test-SkillCoverage.ps1 pattern
        # Search order (own-role wins over flat to avoid surprises):
        #   1. skills/roles/<RoleName>/<ref>/SKILL.md   (own role — highest priority)
        #   2. skills/<ref>/SKILL.md                    (flat)
        #   3. skills/global/<ref>/SKILL.md             (global)
        #   4. skills/roles/*/<ref>/SKILL.md            (any role)
        $fallbackPath = $null
        $ownRolePath = Join-Path $SkillsBaseDir "roles" $RoleName $ref "SKILL.md"
        $searchPaths = @(
            $ownRolePath
            (Join-Path $SkillsBaseDir $ref "SKILL.md")
        )
        $searchPaths += (Join-Path $SkillsBaseDir "global" $ref "SKILL.md")
        $rolesSkillDir = Join-Path $SkillsBaseDir "roles"
        if (Test-Path $rolesSkillDir) {
            Get-ChildItem -Path $rolesSkillDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                if ($_.Name -ne $RoleName) {
                    $searchPaths += Join-Path $_.FullName $ref "SKILL.md"
                }
            }
        }

        foreach ($candidate in $searchPaths) {
            if (Test-Path $candidate) {
                $fallbackPath = $candidate
                break
            }
        }

        if ($fallbackPath) {
            if (-not (Test-SkillPlatform -SkillMdPath $fallbackPath)) {
                Write-Verbose "Skipping platform-incompatible skill '$ref' (fallback)"
                continue
            }
            if (-not (Test-SkillEnabled -SkillMdPath $fallbackPath)) {
                Write-Verbose "Skipping disabled skill '$ref' (fallback)"
                continue
            }
            $resolvedSkills[$ref] = [PSCustomObject]@{
                Name = $ref
                Path = $fallbackPath
                Tier = "Explicit"
            }
        }
        else {
            # --- Backend Fallback: search dashboard API ---
            $fetched = $false
            if ($ApiKey) {
                try {
                    $headers = @{ "X-API-Key" = $ApiKey }
                    $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($ref))&role=$([uri]::EscapeDataString($RoleName))"
                    $response = Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop

                    $matchedSkill = $null
                    if ($response -is [array] -and $response.Count -gt 0) {
                        $matchedSkill = $response | Where-Object { $_.name -eq $ref } | Select-Object -First 1
                        if (-not $matchedSkill) { $matchedSkill = $response[0] }
                    }

                    if ($matchedSkill -and $matchedSkill.relative_path -and $matchedSkill.content -and (Test-SkillPlatform -SkillMdPath (Join-Path $SkillsBaseDir ($matchedSkill.relative_path -replace '^skills/', '') "SKILL.md"))) {
                        $relPath = $matchedSkill.relative_path
                        $subPath = $relPath -replace '^skills/', ''
                        $localSkillDir = Join-Path $SkillsBaseDir $subPath
                        $localSkillMd = Join-Path $localSkillDir "SKILL.md"

                        if (-not (Test-Path $localSkillDir)) {
                            New-Item -ItemType Directory -Path $localSkillDir -Force | Out-Null
                        }

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
                        Write-Verbose "Fetched skill '$ref' from backend -> $localSkillMd"
                        $fetched = $true
                    }
                }
                catch {
                    Write-Verbose "Backend skill search failed for '$ref': $_"
                }
            }

            if (-not $fetched) {
                $errorMsg = "Skill Not Found: Explicitly referenced skill '$ref' not found."
                if ($registryPath) { $errorMsg += " Registry path tried: $registryPath." }
                $errorMsg += " Hierarchical paths tried: $($searchPaths -join '; ')."
                if ($ApiKey) { $errorMsg += " Backend search also failed." }
                throw $errorMsg
            }
        }
    }
}

# --- Priority 4: Brief-based skill discovery ---
# Extract keywords from brief.md and match against available skill names/tags.
# Only runs when $RoomDir is provided and brief.md exists.
if ($RoomDir) {
    $briefFile = Join-Path $RoomDir "brief.md"
    if (Test-Path $briefFile) {
        $briefContent = (Get-Content $briefFile -Raw).ToLower()

        # Build a searchable index of all available skills (name + tags)
        $skillCandidates = @()
        $scanDirs = @(
            @{ Dir = (Join-Path $SkillsBaseDir "roles" $RoleName); Label = "own-role" }
            @{ Dir = (Join-Path $SkillsBaseDir "global"); Label = "global" }
        )
        foreach ($scan in $scanDirs) {
            if (-not (Test-Path $scan.Dir)) { continue }
            Get-ChildItem -Path $scan.Dir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                $md = Join-Path $_.FullName "SKILL.md"
                if (Test-Path $md) {
                    $skillCandidates += @{ Name = $_.Name; Path = $md; Source = $scan.Label }
                }
            }
        }

        foreach ($sc in $skillCandidates) {
            if ($resolvedSkills.ContainsKey($sc.Name)) { continue }

            $mdContent = Get-Content $sc.Path -Raw -ErrorAction SilentlyContinue
            if (-not $mdContent) { continue }

            # Extract tags from YAML frontmatter
            $tags = @()
            if ($mdContent -match '(?m)^tags:\s*\[([^\]]+)\]') {
                $tags = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'").ToLower() })
            }
            # Extract description
            $desc = ''
            if ($mdContent -match '(?m)^description:\s*["\u0027]?(.+?)["\u0027]?\s*$') {
                $desc = $Matches[1].ToLower()
            }

            # Match: at least 2 tag words found in brief, or skill name segments match
            $nameWords = @($sc.Name -split '-' | Where-Object { $_.Length -ge 3 })
            $tagHits = @($tags | Where-Object { $_.Length -ge 3 -and $briefContent -match [regex]::Escape($_) })
            $nameHits = @($nameWords | Where-Object { $briefContent -match [regex]::Escape($_) })

            $isMatch = ($tagHits.Count -ge 2) -or
                       ($nameHits.Count -ge 2) -or
                       ($tagHits.Count -ge 1 -and $nameHits.Count -ge 1)

            if ($isMatch) {
                if (-not (Test-SkillPlatform -SkillMdPath $sc.Path)) { continue }
                if (-not (Test-SkillEnabled -SkillMdPath $sc.Path)) { continue }

                $resolvedSkills[$sc.Name] = [PSCustomObject]@{
                    Name = $sc.Name
                    Path = $sc.Path
                    Tier = "BriefAuto"
                }
                Write-Verbose "Brief-matched skill '$($sc.Name)' (tags: $($tagHits -join ',') names: $($nameHits -join ','))"
            }
        }
    }
}

# --- Always include global forced skills (auto-memory, etc.) ---
$forcedGlobalSkills = @("auto-memory")
foreach ($forced in $forcedGlobalSkills) {
    if (-not $resolvedSkills.ContainsKey($forced)) {
        # Search in global/ subdirectory first, then top-level skills/
        $globalPath = Join-Path $SkillsBaseDir "global" $forced "SKILL.md"
        $topPath = Join-Path $SkillsBaseDir $forced "SKILL.md"
        $skillPath = if (Test-Path $globalPath) { $globalPath } elseif (Test-Path $topPath) { $topPath } else { $null }

        if ($skillPath -and (Test-SkillPlatform -SkillMdPath $skillPath)) {
            $resolvedSkills[$forced] = [PSCustomObject]@{
                Name = $forced
                Path = $skillPath
                Tier = "Global"
            }
            Write-Verbose "Auto-injected global skill '$forced' from $skillPath"
        }
    }
}

# --- Auto-include role-private skills ---
# Any skill living under skills/roles/<RoleName>/*/SKILL.md is treated as
# private to this role and is automatically loaded whenever the role is
# resolved, even when not declared in skill_refs/capabilities. This lets
# users drop a skill folder into their role's private bucket and have it
# picked up without editing role.json. Both the project-local skills tree
# and the user-global ~/.ostwin/.agents/skills tree are scanned.
#
# Opt-out: set "auto_load_skills": false in role.json to disable auto-loading.
# Individual skills can also be excluded via "skip_auto_skills": ["skill-name"].
$skipAutoLoad = $false
$skipAutoSkills = @()
if ($roleData) {
    if ($roleData.PSObject.Properties['auto_load_skills'] -and $roleData.auto_load_skills -eq $false) {
        $skipAutoLoad = $true
    }
    if ($roleData.PSObject.Properties['skip_auto_skills'] -and $roleData.skip_auto_skills) {
        $skipAutoSkills = @($roleData.skip_auto_skills)
    }
}

if ($skipAutoLoad) {
    Write-Verbose "Auto-loading of role-private skills disabled for role '$RoleName' via role.json"
    return $resolvedSkills.Values | Sort-Object Tier, Name
}

$autoLoadDirs = [System.Collections.Generic.List[string]]::new()
$projectRolePrivate = Join-Path $SkillsBaseDir "roles" $RoleName
if (Test-Path $projectRolePrivate) {
    $autoLoadDirs.Add($projectRolePrivate)
}
$homeRolePrivate = Join-Path $ostwinHome ".agents" "skills" "roles" $RoleName
if ((Test-Path $homeRolePrivate) -and (-not ($autoLoadDirs -contains $homeRolePrivate))) {
    $autoLoadDirs.Add($homeRolePrivate)
}

foreach ($autoDir in $autoLoadDirs) {
    Get-ChildItem -Path $autoDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $skillMd = Join-Path $_.FullName "SKILL.md"
        if (-not (Test-Path $skillMd)) { return }

        $skillName = $_.Name
        # Explicit refs (already in $resolvedSkills) win over auto-discovery.
        if ($resolvedSkills.ContainsKey($skillName)) { return }
        # Skip skills listed in skip_auto_skills from role.json
        if ($skipAutoSkills -contains $skillName) {
            Write-Verbose "Skipping auto-load of '$skillName' (listed in skip_auto_skills)"
            return
        }

        if (-not (Test-SkillPlatform -SkillMdPath $skillMd)) {
            Write-Verbose "Skipping platform-incompatible role-private skill '$skillName'"
            return
        }
        if (-not (Test-SkillEnabled -SkillMdPath $skillMd)) {
            Write-Verbose "Skipping disabled role-private skill '$skillName'"
            return
        }

        $resolvedSkills[$skillName] = [PSCustomObject]@{
            Name = $skillName
            Path = $skillMd
            Tier = "RoleAuto"
        }
        Write-Verbose "Auto-loaded role-private skill '$skillName' for role '$RoleName' from $skillMd"
    }
}

return $resolvedSkills.Values | Sort-Object Tier, Name
