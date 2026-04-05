<#
.SYNOPSIS
    Resolves a set of skills for a specific role following a hierarchical resolution strategy.

.DESCRIPTION
    Loads role.json from HOME ~/.ostwin/roles/{RoleName}/role.json when available,
    and falls back to / merges with the provided RolePath role.json.
    Resolves global skills, role-specific skills, and explicit skill_refs.
    Capabilities are treated as soft hints rather than mandatory skill refs.

    Resolution strategy (for each ref):
    1. Registry lookup: from ~/.ostwin/roles/registry.json
    2. Local skills fallback: from skills/<ref>/SKILL.md
    3. Backend skills: fetched from dashboard API when not found locally

    Deduplication is performed based on skill directory name (identifier).

.PARAMETER RoleName
    Name of the role (e.g., engineer, architect).
.PARAMETER RolePath
    Local role directory or role.json path used as fallback / overlay metadata.
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
$baseRole = $RoleName -replace ':.*$', ''

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

function Add-ResolvedSkill {
    param(
        [string]$Name,
        [string]$Path,
        [string]$Tier
    )

    if (-not $Name -or -not $Path) { return }
    if (-not (Test-Path $Path)) { return }
    if (-not (Test-SkillPlatform -SkillMdPath $Path)) { return }

    $resolvedSkills[$Name] = [PSCustomObject]@{
        Name = $Name
        Path = $Path
        Tier = $Tier
    }
}

function Get-HomeBase {
    if ($env:HOME) { return $env:HOME }
    if ($HOME) { return "$HOME" }
    if ($env:USERPROFILE) { return $env:USERPROFILE }
    return $null
}

function Get-RoleJsonCandidates {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $homeBase = Get-HomeBase

    if ($homeBase) {
        $homeRoleRoot = Join-Path (Join-Path $homeBase ".ostwin") "roles"
        $homeRoleJson = Join-Path (Join-Path $homeRoleRoot $baseRole) "role.json"
        if (Test-Path $homeRoleJson) { $candidates.Add($homeRoleJson) }
    }

    if ($RolePath) {
        $localRoleJson = if ((Test-Path $RolePath) -and (Get-Item $RolePath).PSIsContainer) {
            Join-Path $RolePath "role.json"
        } else {
            $RolePath
        }
        if ($localRoleJson -and (Test-Path $localRoleJson) -and -not $candidates.Contains($localRoleJson)) {
            $candidates.Add($localRoleJson)
        }
    }

    return $candidates
}

function Get-RegistryCandidates {
    $registryCandidates = [System.Collections.Generic.List[string]]::new()
    $homeBase = Get-HomeBase

    if ($homeBase) {
        $homeRegistry = Join-Path (Join-Path (Join-Path $homeBase ".ostwin") "roles") "registry.json"
        if (Test-Path $homeRegistry) { $registryCandidates.Add($homeRegistry) }
    }

    $localRegistry = Join-Path (Join-Path (Split-Path $SkillsBaseDir -Parent) "roles") "registry.json"
    if ((Test-Path $localRegistry) -and -not $registryCandidates.Contains($localRegistry)) {
        $registryCandidates.Add($localRegistry)
    }

    return $registryCandidates
}

function Resolve-SkillRef {
    param(
        [string]$Ref,
        [bool]$Strict = $true,
        [bool]$Force = $false
    )

    if (-not $Ref) { return $false }
    if ($resolvedSkills.ContainsKey($Ref) -and -not $Force) { return $true }

    $registryPath = $null
    foreach ($registryFile in (Get-RegistryCandidates)) {
        try {
            $registry = Get-Content $registryFile -Raw | ConvertFrom-Json
            $skillFromRegistry = $registry.skills.available | Where-Object { $_.name -eq $Ref } | Select-Object -First 1
            if ($skillFromRegistry -and $skillFromRegistry.path) {
                $candidatePath = Join-Path (Split-Path $registryFile -Parent) ".." $skillFromRegistry.path
                if (Test-Path $candidatePath) {
                    Add-ResolvedSkill -Name $Ref -Path $candidatePath -Tier "Explicit"
                    return $true
                }
                $registryPath = $candidatePath
            }
        } catch {
            Write-Verbose "Failed to inspect registry '$registryFile' for '$Ref': $_"
        }
    }

    $fallbackPaths = @(
        (Join-Path $SkillsBaseDir $Ref "SKILL.md"),
        (Join-Path $SkillsBaseDir "global" $Ref "SKILL.md"),
        (Join-Path $SkillsBaseDir "roles" $baseRole $Ref "SKILL.md")
    ) | Select-Object -Unique

    foreach ($fallbackPath in $fallbackPaths) {
        if (Test-Path $fallbackPath) {
            Add-ResolvedSkill -Name $Ref -Path $fallbackPath -Tier "Explicit"
            return $true
        }
    }

    if ($ApiKey) {
        try {
            $headers = @{ "X-API-Key" = $ApiKey }
            $searchUrl = "$DashboardUrl/api/skills/search?q=$([uri]::EscapeDataString($Ref))&role=$([uri]::EscapeDataString($baseRole))"
            $response = Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get -TimeoutSec 10 -ErrorAction Stop

            $matchedSkill = $null
            if ($response -is [array] -and $response.Count -gt 0) {
                $matchedSkill = $response | Where-Object { $_.name -eq $Ref } | Select-Object -First 1
                if (-not $matchedSkill) { $matchedSkill = $response[0] }
            }

            if ($matchedSkill -and $matchedSkill.relative_path -and $matchedSkill.content) {
                $subPath = $matchedSkill.relative_path -replace '^skills/', ''
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

                Add-ResolvedSkill -Name $matchedSkill.name -Path $localSkillMd -Tier "Backend"
                return $true
            }
        }
        catch {
            Write-Verbose "Backend skill search failed for '$Ref': $_"
        }
    }

    if ($Strict) {
        $errorMsg = "Skill Not Found: Explicitly referenced skill '$Ref' not found."
        if ($registryPath) {
            $errorMsg += " Registry path tried: $registryPath."
        }
        $errorMsg += " Fallback paths tried: $($fallbackPaths -join ', ')."
        if ($ApiKey) {
            $errorMsg += " Backend search also failed."
        }
        throw $errorMsg
    }

    return $false
}

# Baseline: all global skills are available to every role.
$globalSkillsDir = Join-Path $SkillsBaseDir "global"
if (Test-Path $globalSkillsDir) {
    Get-ChildItem -Path $globalSkillsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $skillMd = Join-Path $_.FullName "SKILL.md"
        Add-ResolvedSkill -Name $_.Name -Path $skillMd -Tier "Global"
    }
}

# Role-local skills are available to matching roles and override globals by name.
$roleSkillsDir = Join-Path $SkillsBaseDir "roles" $baseRole
if (Test-Path $roleSkillsDir) {
    Get-ChildItem -Path $roleSkillsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $skillMd = Join-Path $_.FullName "SKILL.md"
        Add-ResolvedSkill -Name $_.Name -Path $skillMd -Tier "Role"
    }
}

$explicitRefs = @()
$capabilityRefs = @()
foreach ($jsonFile in (Get-RoleJsonCandidates)) {
    Write-Verbose "Loading role.json for skills: $jsonFile"
    try {
        $roleData = Get-Content $jsonFile -Raw | ConvertFrom-Json
        if ($roleData.skill_refs) {
            $explicitRefs += @($roleData.skill_refs)
        }
        if ($roleData.capabilities) {
            $capabilityRefs += @($roleData.capabilities)
        }
    }
    catch {
        Write-Warning "Failed to parse role.json for skills: $_"
    }
}

$explicitRefs = @($explicitRefs | Where-Object { $_ } | Select-Object -Unique)
$capabilityRefs = @($capabilityRefs | Where-Object { $_ } | Select-Object -Unique)

foreach ($capabilityRef in $capabilityRefs) {
    Resolve-SkillRef -Ref $capabilityRef -Strict $false -Force $false | Out-Null
}

foreach ($explicitRef in $explicitRefs) {
    Resolve-SkillRef -Ref $explicitRef -Strict $true -Force $true | Out-Null
}

return $resolvedSkills.Values | Sort-Object Tier, Name
