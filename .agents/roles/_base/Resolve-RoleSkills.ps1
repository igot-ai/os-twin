<#
.SYNOPSIS
    Resolves a set of skills for a specific role following a hierarchical resolution strategy.

.DESCRIPTION
    Tiers of resolution (highest priority/latest wins for deduplication):
    1. Global skills: from skills/global/
    2. Role-specific skills: from skills/roles/<role_name>/
    3. Explicitly referenced skills: from skill_refs in role.json (relative to skills/)

    Deduplication is performed based on skill directory name (identifier).

.PARAMETER RoleName
    Name of the role (e.g., engineer, architect).
.PARAMETER RolePath
    Absolute path to the role directory containing role.json.
.PARAMETER SkillsBaseDir
    Optional. Override for the base skills directory (defaults to ../../skills).

.OUTPUTS
    [PSCustomObject[]] Collection of objects with Name, Path (to SKILL.md), and Tier.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$RoleName,

    [Parameter(Mandatory=$true)]
    [string]$RolePath,

    [string]$SkillsBaseDir = ''
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

$resolvedSkills = @{} # Using hashtable for deduplication by Name

# --- 1. Global Skills ---
$globalDir = Join-Path $SkillsBaseDir "global"
if (Test-Path $globalDir) {
    Get-ChildItem $globalDir -Directory | ForEach-Object {
        $skillMd = Join-Path $_.FullName "SKILL.md"
        if (Test-Path $skillMd) {
            $resolvedSkills[$_.Name] = [PSCustomObject]@{
                Name = $_.Name
                Path = $skillMd
                Tier = "Global"
            }
        }
    }
}

# --- 2. Role-Specific Skills ---
$roleDir = Join-Path $SkillsBaseDir "roles" $RoleName
if (Test-Path $roleDir) {
    Get-ChildItem $roleDir -Directory | ForEach-Object {
        $skillMd = Join-Path $_.FullName "SKILL.md"
        if (Test-Path $skillMd) {
            $resolvedSkills[$_.Name] = [PSCustomObject]@{
                Name = $_.Name
                Path = $skillMd
                Tier = "Role"
            }
        }
    }
}

# --- 3. Explicit skill_refs from role.json ---
$jsonFile = Join-Path $RolePath "role.json"
if (Test-Path $jsonFile) {
    try {
        $roleData = Get-Content $jsonFile -Raw | ConvertFrom-Json
        if ($roleData.skill_refs) {
            $registryFile = Join-Path (Split-Path $RolePath) "registry.json"
            $registry = if (Test-Path $registryFile) { Get-Content $registryFile -Raw | ConvertFrom-Json } else { $null }

            foreach ($ref in $roleData.skill_refs) {
                # Look for ref in registry first
                $skillFromRegistry = if ($registry) { $registry.skills.available | Where-Object { $_.name -eq $ref } } else { $null }
                $registryPath = $null
                
                if ($skillFromRegistry) {
                    $registryPath = Join-Path (Split-Path $registryFile -Parent) ".." $skillFromRegistry.path
                    if (Test-Path $registryPath) {
                        $resolvedSkills[$ref] = [PSCustomObject]@{
                            Name = $ref
                            Path = $registryPath
                            Tier = "Explicit"
                        }
                        continue
                    }
                }

                # Check if already resolved via role-specific (Tier: Role) or Global
                if ($resolvedSkills.ContainsKey($ref)) {
                    if ($resolvedSkills[$ref].Tier -eq "Role" -or $resolvedSkills[$ref].Tier -eq "Global") {
                        # Upgrade tier to Explicit for direct visibility
                        $resolvedSkills[$ref].Tier = "Explicit"
                    }
                    continue
                }

                # Fallback to skills/<ref>/SKILL.md
                $fallbackPath = Join-Path $SkillsBaseDir $ref "SKILL.md"

                if (Test-Path $fallbackPath) {
                    $resolvedSkills[$ref] = [PSCustomObject]@{
                        Name = $ref
                        Path = $fallbackPath
                        Tier = "Explicit"
                    }
                }
                else {
                    $errorMsg = "Skill Not Found: Explicitly referenced skill '$ref' not found."
                    if ($registryPath) {
                        $errorMsg += " Registry path tried: $registryPath."
                    }
                    $errorMsg += " Fallback path tried: $fallbackPath."
                    throw $errorMsg
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
