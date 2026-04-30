<#
.SYNOPSIS
    Resolves a set of skills for a specific role via Dashboard API search.

.DESCRIPTION
    Skills are discovered exclusively through the Dashboard API:
      - Searches /api/skills/search with brief.md content → top 5 matches

    No fallback sources are used (no role.json skill_refs, no room config
    skill_refs, no plan-level overrides, no role-private auto-loading).
    This ensures only contextually relevant skills are loaded.

    Resolution strategy (for each API-returned ref):
      1. Registry lookup: from ~/.ostwin/roles/registry.json
      2. Local skills: hierarchical search in skills/ tree
      3. Backend fetch: downloaded from dashboard API when not found locally

    Unresolvable refs are skipped gracefully (best-effort).
    Deduplication is performed based on skill directory name (identifier).

.PARAMETER RoleName
    Name of the role (e.g., engineer, architect).
.PARAMETER RolePath
    Legacy parameter — kept for backward compatibility. Not used.
.PARAMETER RoomDir
    Optional. War-room directory path — used to read brief.md for the
    API skill search query.
.PARAMETER PlanId
    Optional. Not used (kept for backward compatibility).
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

# --- Collect skill refs from Dashboard API search (sole source) ---
$allRefs = @()

if ($RoomDir) {
    $briefFile = Join-Path $RoomDir "brief.md"
    if (Test-Path $briefFile) {
        $briefContent = Get-Content $briefFile -Raw -ErrorAction SilentlyContinue
        if ($briefContent) {
            try {
                $headers = @{}
                if ($ApiKey) { $headers["X-API-Key"] = $ApiKey }
                # Truncate brief to avoid URL length issues (safe GET limit ~2000 chars)
                $queryText = if ($briefContent.Length -gt 500) { $briefContent.Substring(0, 500) } else { $briefContent }
                $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($queryText))"
                $response = @(Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop)

                if ($response.Count -gt 0 -and $null -ne $response[0]) {
                    $apiNames = @($response | Select-Object -First 5 | ForEach-Object { $_.name })
                    $allRefs += $apiNames
                    Write-Verbose "Dashboard API search matched ($($apiNames.Count)): $($apiNames -join ', ')"
                }
            }
            catch {
                Write-Verbose "Dashboard API search failed (non-fatal): $_"
            }
        }
    }
}

# Deduplicate
$allRefs = @($allRefs | Select-Object -Unique)
Write-Verbose "Skill refs from API ($($allRefs.Count)): $($allRefs -join ', ')"

if ($allRefs.Count -eq 0) {
    return @()
}

# --- Resolve each API-returned ref to a local SKILL.md path ---

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

    # Check if already resolved (duplicate from API)
    if ($resolvedSkills.ContainsKey($ref)) { continue }

    # Strategy 2: Local hierarchical search
    # Search order (own-role wins over flat to avoid surprises):
    #   1. skills/roles/<RoleName>/<ref>/SKILL.md   (own role — highest priority)
    #   2. skills/<ref>/SKILL.md                    (flat)
    #   3. skills/global/<ref>/SKILL.md             (global)
    #   4. skills/roles/*/<ref>/SKILL.md            (any role)
    $localPath = $null
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
                $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($ref))&role=$([uri]::EscapeDataString($RoleName))"
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

                    $frontmatter = @"
---
name: $($matchedSkill.name)
description: $($matchedSkill.description)
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
            # All API-discovered refs are best-effort — skip gracefully
            Write-Verbose "Skill '$ref' not resolvable locally or via backend — skipping"
        }
    }
}

return $resolvedSkills.Values | Sort-Object Tier, Name
