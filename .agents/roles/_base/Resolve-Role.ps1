<#
.SYNOPSIS
    Resolves a role name (or capability list) to a runner script path and metadata.
 
.PARAMETER RoleName
    The role to resolve. Can include instance suffix (e.g., "engineer:fe").
.PARAMETER RequiredCapabilities
    Optional. Array of capabilities needed. Used for capability-based matching
    when RoleName is empty or not found.
.PARAMETER AgentsDir
    Path to the .agents directory.
.PARAMETER WarRoomsDir
    Path to the war-rooms directory (for project-level role discovery).
 
.OUTPUTS
    PSCustomObject with: Name, BaseRole, Runner, Model, Timeout, Capabilities, Source
    Source is one of: "registry", "discovered", "capability-match", "ephemeral"
#>
[CmdletBinding()]
param(
    [string]$RoleName = '',
    [string[]]$RequiredCapabilities = @(),
    [Parameter(Mandatory)]
    [string]$AgentsDir,
    [string]$WarRoomsDir = '',
    [array]$AvailableRoles = $null
)
 
$baseRole = $RoleName -replace ':.*$', ''
$instanceSuffix = if ($RoleName -match ':(.+)$') { $Matches[1] } else { '' }
 
$result = [PSCustomObject]@{
    Name         = $RoleName
    BaseRole     = $baseRole
    Runner       = $null
    Model        = 'gemini-3-flash-preview'
    Timeout      = 600
    Capabilities = @()
    Source       = 'ephemeral'
}
 
# --- Tier 1 & 2 Fast Path: Use AvailableRoles cache if provided ---
if ($AvailableRoles) {
    $matched = $AvailableRoles | Where-Object { $_.Name -eq $baseRole } | Select-Object -First 1
    if ($matched -and $matched.Runner) {
        $result.Runner = $matched.Runner
        $result.Source = $matched.Source
        if ($matched.Capabilities) { $result.Capabilities = @($matched.Capabilities) }
        if ($matched.Model) { $result.Model = $matched.Model }
        if ($matched.Timeout) { $result.Timeout = $matched.Timeout }
    }
}

if (-not $result.Runner) {
    # --- Tier 1: Static registry match ---
    $registryPath = Join-Path $AgentsDir "roles" "registry.json"
    if ($baseRole -and (Test-Path $registryPath)) {
        $registry = Get-Content $registryPath -Raw | ConvertFrom-Json
        $matchedRole = $registry.roles | Where-Object { $_.name -eq $baseRole }
        if ($matchedRole -and $matchedRole.runner) {
            $runnerRel = $matchedRole.runner -replace '/', [System.IO.Path]::DirectorySeparatorChar
            $runnerPath = Join-Path $AgentsDir $runnerRel
            if (Test-Path $runnerPath) {
                $result.Runner = $runnerPath
                $result.Source = 'registry'
                $result.Capabilities = if ($matchedRole.capabilities) { @($matchedRole.capabilities) } else { @() }
                if ($matchedRole.default_model) { $result.Model = $matchedRole.default_model }
            }
        }
    }
     
    # --- Tier 2: Dynamic directory discovery ---
    if (-not $result.Runner -and $baseRole) {
        $searchDirs = @()
        if ($WarRoomsDir) {
            $searchDirs += Join-Path $WarRoomsDir ".." "roles" $baseRole
        }
        $searchDirs += Join-Path $AgentsDir "roles" $baseRole
     
        foreach ($dir in $searchDirs) {
            if (Test-Path (Join-Path $dir "role.json")) {
                $roleJson = Get-Content (Join-Path $dir "role.json") -Raw | ConvertFrom-Json
                $result.Capabilities = if ($roleJson.capabilities) { @($roleJson.capabilities) } else { @() }
                if ($roleJson.model) { $result.Model = $roleJson.model }
                if ($roleJson.timeout_seconds) { $result.Timeout = $roleJson.timeout_seconds }
     
                # Check for custom runner script
                $customRunner = Join-Path $dir "Start-$baseRole.ps1"
                if (Test-Path $customRunner) {
                    $result.Runner = $customRunner
                } else {
                    # Use universal dynamic runner as fallback for discovered roles
                    $result.Runner = Join-Path $AgentsDir "roles" "_base" "Start-DynamicRole.ps1"
                }
                $result.Source = 'discovered'
                break
            }
        }
    }
}
 
# --- Tier 3: Capability-based matching ---
if (-not $result.Runner -and $RequiredCapabilities.Count -gt 0) {
    $allRoles = if ($AvailableRoles) {
        $AvailableRoles
    } else {
        $getAvailable = Join-Path $AgentsDir "roles" "_base" "Get-AvailableRoles.ps1"
        if (Test-Path $getAvailable) {
            & $getAvailable -AgentsDir $AgentsDir -WarRoomsDir $WarRoomsDir
        } else { @() }
    }
    
    if ($allRoles) {
        $bestScore = 0
        $bestMatch = $null
        foreach ($candidate in $allRoles) {
            if (-not $candidate.Capabilities) { continue }
            $overlap = ($RequiredCapabilities | Where-Object { $candidate.Capabilities -contains $_ }).Count
            if ($overlap -gt $bestScore) {
                $bestScore = $overlap
                $bestMatch = $candidate
            }
        }
        if ($bestMatch -and $bestScore -gt 0) {
            $result.Runner = $bestMatch.Runner
            if ($bestMatch.Capabilities) { $result.Capabilities = @($bestMatch.Capabilities) }
            if ($bestMatch.Model) { $result.Model = $bestMatch.Model }
            $result.BaseRole = $bestMatch.Name
            $result.Source = 'capability-match'
        }
    }
}
 
# --- Tier 4: Ephemeral agent fallback ---
if (-not $result.Runner) {
    $result.Runner = Join-Path $AgentsDir "roles" "_base" "Start-EphemeralAgent.ps1"
    $result.Source = 'ephemeral'
}
 
Write-Output $result