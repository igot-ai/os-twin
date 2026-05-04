<#
.SYNOPSIS
    Resolves a set of skills for a specific role via plan-roles config + task-aware discovery.

.DESCRIPTION
    Phase 1 — CONFIG-DRIVEN skill_refs (what the role always needs):
      1. Plan-roles config:  ~/.ostwin/.agents/plans/{plan_id}.roles.json → $role.skill_refs
      2. HOME role.json:     ~/.ostwin/roles/{RoleName}/role.json → skill_refs
      3. Local role.json:    roles/{RoleName}/role.json → skill_refs
      First non-empty wins (no merging across sources).

    Phase 2 — TASK-AWARE API SEARCH (discover extra skills for this task):
      Reads brief.md + TASKS.md from RoomDir, searches the Dashboard API,
      and merges up to 5 additional skill refs not already in Phase 1.
      Runs only when ApiKey is available and task content is meaningful.

    Phase 3 — LOCAL RESOLUTION (stage each ref to disk):
      1. Registry lookup: from ~/.ostwin/roles/registry.json
      2. Local skills: hierarchical search in skills/ tree
      3. Backend fetch: downloaded from dashboard API when not found locally

    Unresolvable refs are skipped gracefully (best-effort).
    Deduplication is performed based on skill directory name (identifier).

.PARAMETER RoleName
    Name of the role (e.g., engineer, architect). Supports instance suffix (engineer:fe).
.PARAMETER RolePath
    Path to the role directory (unused — kept for backward compat).
.PARAMETER RoomDir
    Optional. War-room directory path — used to read plan_id from config.json,
    and brief.md + TASKS.md for task-aware API search.
.PARAMETER PlanId
    Optional. Explicit plan ID override. When omitted, read from room config.json.
.PARAMETER SkillsBaseDir
    Optional. Override for the base skills directory (defaults to ../../skills).
.PARAMETER DashboardUrl
    Optional. Dashboard API base URL (default: http://localhost:3366).
.PARAMETER ApiKey
    Optional. API key for dashboard authentication (default: $env:OSTWIN_API_KEY).

.OUTPUTS
    [PSCustomObject[]] Collection of objects with Name, Path (to SKILL.md), and Tier.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RoleName,

    [Parameter(Mandatory = $true)]
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
    $DashboardUrl = if ($env:DASHBOARD_URL) { $env:DASHBOARD_URL } else { "http://localhost:3366" }
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
$_homeDir = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
$ostwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $_homeDir ".ostwin" }

# --- Strip instance suffix (engineer:fe → engineer) ---
$baseRole = $RoleName -replace ':.*$', ''

# =======================================================================
# PHASE 1: CONFIG-DRIVEN SKILL REFS
# =======================================================================
$allRefs = @()

# Source 1: Plan-roles config (~/.ostwin/.agents/plans/{plan_id}.roles.json → $role.skill_refs)
if ($allRefs.Count -eq 0) {
    # Resolve plan_id: explicit parameter > room config.json
    $effectivePlanId = $PlanId
    if (-not $effectivePlanId -and $RoomDir -and (Test-Path $RoomDir)) {
        $roomConfigFile = Join-Path $RoomDir "config.json"
        if (Test-Path $roomConfigFile) {
            try {
                $roomCfg = Get-Content $roomConfigFile -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($roomCfg.plan_id) {
                    $effectivePlanId = $roomCfg.plan_id
                }
            } catch { }
        }
    }

    if ($effectivePlanId) {
        $planRolesFile = Join-Path $ostwinHome ".agents" "plans" "$effectivePlanId.roles.json"
        if (Test-Path $planRolesFile) {
            try {
                $planRolesData = Get-Content $planRolesFile -Raw | ConvertFrom-Json
                if ($planRolesData.$baseRole -and $planRolesData.$baseRole.skill_refs -and $planRolesData.$baseRole.skill_refs.Count -gt 0) {
                    $allRefs = @($planRolesData.$baseRole.skill_refs)
                    Write-Verbose "Skill refs from plan-roles ($effectivePlanId): $($allRefs -join ', ')"
                }
            } catch { }
        }
    }
}

# Source 2: HOME role.json (~/.ostwin/roles/{RoleName}/role.json → skill_refs)
if ($allRefs.Count -eq 0) {
    $homeRoleJson = Join-Path $ostwinHome "roles" $baseRole "role.json"
    if (Test-Path $homeRoleJson) {
        try {
            $homeRoleData = Get-Content $homeRoleJson -Raw | ConvertFrom-Json
            if ($homeRoleData.skill_refs -and $homeRoleData.skill_refs.Count -gt 0) {
                $allRefs = @($homeRoleData.skill_refs)
                Write-Verbose "Skill refs from HOME role.json: $($allRefs -join ', ')"
            }
        } catch { }
    }
}

# Source 3: Local role.json (roles/{RoleName}/role.json → skill_refs)
if ($allRefs.Count -eq 0) {
    $localRoleJson = Join-Path $PSScriptRoot ".." $baseRole "role.json"
    if (Test-Path $localRoleJson) {
        try {
            $localRoleData = Get-Content $localRoleJson -Raw | ConvertFrom-Json
            if ($localRoleData.skill_refs -and $localRoleData.skill_refs.Count -gt 0) {
                $allRefs = @($localRoleData.skill_refs)
                Write-Verbose "Skill refs from local role.json: $($allRefs -join ', ')"
            }
        } catch { }
    }
}

# =======================================================================
# PHASE 2: TASK-AWARE API SEARCH (additive — supplements Phase 1 refs)
# =======================================================================
if ($RoomDir -and (Test-Path $RoomDir) -and $ApiKey) {
    $taskContext = ""
    $briefFile = Join-Path $RoomDir "brief.md"
    $tasksFile = Join-Path $RoomDir "TASKS.md"

    if (Test-Path $briefFile) {
        $taskContext += (Get-Content $briefFile -Raw -ErrorAction SilentlyContinue)
    }
    if (Test-Path $tasksFile) {
        $taskContext += "`n" + (Get-Content $tasksFile -Raw -ErrorAction SilentlyContinue)
    }

    # Only search with meaningful content (>50 chars avoids noise from empty briefs)
    if ($taskContext.Length -gt 50) {
        try {
            $query = $taskContext.Substring(0, [Math]::Min($taskContext.Length, 500))
            $headers = @{ "X-API-Key" = $ApiKey }
            $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($query))&role=$([uri]::EscapeDataString($baseRole))"
            $searchResults = @(Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop)

            if ($searchResults.Count -gt 0 -and $null -ne $searchResults[0]) {
                $existingNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
                foreach ($r in $allRefs) { $existingNames.Add($r) | Out-Null }

                $addedCount = 0
                foreach ($result in $searchResults) {
                    if ($addedCount -ge 5) { break }
                    if ($result.name -and -not $existingNames.Contains($result.name)) {
                        $allRefs += $result.name
                        $existingNames.Add($result.name) | Out-Null
                        $addedCount++
                        Write-Verbose "Phase 2 discovered skill: $($result.name)"
                    }
                }
            }
        }
        catch {
            Write-Verbose "Task-aware skill search failed (non-fatal): $_"
        }
    }
}

# =======================================================================
# PHASE 3: LOCAL RESOLUTION (stage each ref to disk)
# =======================================================================

# Deduplicate
$allRefs = @($allRefs | Select-Object -Unique)
Write-Verbose "Skill refs to resolve ($($allRefs.Count)): $($allRefs -join ', ')"

if ($allRefs.Count -eq 0) {
    return @()
}

# Registry always from HOME ~/.ostwin/roles/registry.json
$registryFile = Join-Path $ostwinHome "roles" "registry.json"
$registry = if (Test-Path $registryFile) { Get-Content $registryFile -Raw | ConvertFrom-Json } else { $null }

foreach ($ref in $allRefs) {
    # Strategy 1: Registry lookup
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

    # Check if already resolved (duplicate)
    if ($resolvedSkills.ContainsKey($ref)) { continue }

    # Strategy 2: Local hierarchical search
    # Search order (own-role wins over flat to avoid surprises):
    #   1. skills/roles/<RoleName>/<ref>/SKILL.md   (own role — highest priority)
    #   2. skills/<ref>/SKILL.md                    (flat)
    #   3. skills/global/<ref>/SKILL.md             (global)
    #   4. skills/roles/*/<ref>/SKILL.md            (any role)
    $localPath = $null
    $ownRolePath = Join-Path $SkillsBaseDir "roles" $baseRole $ref "SKILL.md"
    $searchPaths = @(
        $ownRolePath
        (Join-Path $SkillsBaseDir $ref "SKILL.md")
    )
    $searchPaths += (Join-Path $SkillsBaseDir "global" $ref "SKILL.md")
    $rolesSkillDir = Join-Path $SkillsBaseDir "roles"
    if (Test-Path $rolesSkillDir) {
        Get-ChildItem -Path $rolesSkillDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.Name -ne $baseRole) {
                $searchPaths += Join-Path $_.FullName $ref "SKILL.md"
            }
        }
    }

    foreach ($candidate in $searchPaths) {
        if (Test-Path $candidate) {
            $localPath = $candidate
            break
        }
    }

    if ($localPath) {
        if (-not (Test-SkillPlatform -SkillMdPath $localPath)) {
            Write-Verbose "Skipping platform-incompatible skill '$ref'"
            continue
        }
        if (-not (Test-SkillEnabled -SkillMdPath $localPath)) {
            Write-Verbose "Skipping disabled skill '$ref'"
            continue
        }
        $resolvedSkills[$ref] = [PSCustomObject]@{
            Name = $ref
            Path = $localPath
            Tier = "Explicit"
        }
    }
    else {
        # Strategy 3: Backend fetch — download skill content from dashboard API
        $fetched = $false
        if ($ApiKey) {
            try {
                $headers = @{ "X-API-Key" = $ApiKey }
                $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($ref))&role=$([uri]::EscapeDataString($baseRole))"
                $response = @(Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop)

                $matchedSkill = $null
                if ($response.Count -gt 0 -and $null -ne $response[0]) {
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

                    # Truncate description to 1,021 chars to comply with Gemini protocol limits
                    # (prevents GENERIC_STRING_INVALID_TOO_LONG on function_declarations[N].description)
                    $rawDesc = [string]$matchedSkill.description
                    $safeDesc = if ($rawDesc.Length -gt 1021) { $rawDesc.Substring(0, 1021) + '...' } else { $rawDesc }

                    $frontmatter = @"
---
name: $($matchedSkill.name)
description: $safeDesc
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
                Write-Verbose "Backend skill fetch failed for '$ref': $_"
            }
        }

        if (-not $fetched) {
            # Unresolvable — skip gracefully
            Write-Verbose "Skill '$ref' not resolvable locally or via backend — skipping"
        }
    }
}

return $resolvedSkills.Values | Sort-Object Tier, Name
