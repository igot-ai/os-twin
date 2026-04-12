<#
.SYNOPSIS
    Materializes contributed roles into runtime-expected locations before plan execution.

.DESCRIPTION
    Reads a plan .md file (or explicit role list) and for each contributed role found
    in contributes/roles/<role>/, copies role artifacts into the locations that the
    existing core runtime reads from — without modifying any core scripts.

    Runtime surfaces served:
      1. Room overrides   → $RoomDir/overrides/<role>/   (Start-DynamicRole.ps1:90)
      2. HOME .agents     → ~/.ostwin/.agents/roles/<role>/  (Invoke-Agent.ps1:262)
      3. HOME roles       → ~/.ostwin/roles/<role>/          (Resolve-RoleSkills.ps1:98)
      4. OpenCode agents  → ~/.config/opencode/agents/<role>.md  (opencode --agent)
      5. plan.roles.json  → ~/.ostwin/.agents/plans/<plan_id>.roles.json  (Invoke-Agent.ps1:110)

    This script is idempotent — safe to run multiple times.

.PARAMETER PlanFile
    Path to the plan .md file. Roles are extracted from "Roles:" lines.
.PARAMETER Roles
    Explicit list of role names to materialize. Overrides PlanFile parsing.
.PARAMETER ProjectDir
    Project root containing contributes/roles/. Defaults to cwd.
.PARAMETER WarRoomsDir
    War-rooms directory. If provided, room overrides are also materialized.
.PARAMETER PlanId
    Plan ID for plan.roles.json. Auto-derived from PlanFile if not specified.
.PARAMETER DryRun
    Show what would be done without writing anything.

.EXAMPLE
    ./Materialize-PlanRoles.ps1 -PlanFile ".agents/plans/test-dynamic-roles.md"
    ./Materialize-PlanRoles.ps1 -Roles @("qa-test-planner","test-engineer") -PlanId "my-plan"
#>
[CmdletBinding()]
param(
    [string]$PlanFile = '',
    [string[]]$Roles = @(),
    [string]$ProjectDir = '',
    [string]$WarRoomsDir = '',
    [string]$PlanId = '',
    [switch]$DryRun
)

# --- Resolve project root ---
if (-not $ProjectDir) { $ProjectDir = (Get-Location).Path }
$contributesDir = Join-Path $ProjectDir "contributes" "roles"

if (-not (Test-Path $contributesDir)) {
    Write-Error "contributes/roles/ not found at: $contributesDir"
    exit 1
}

# --- Resolve HOME paths ---
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $env:HOME ".ostwin" }
$homeAgentsRoles = Join-Path $OstwinHome ".agents" "roles"
$homeRoles = Join-Path $OstwinHome "roles"
$xdgConfig = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $env:HOME ".config" }
$opencodeAgentsDir = Join-Path $xdgConfig "opencode" "agents"
$homePlansDir = Join-Path $OstwinHome ".agents" "plans"

# --- Parse roles from plan file ---
if ($Roles.Count -eq 0 -and $PlanFile) {
    if (-not (Test-Path $PlanFile)) {
        Write-Error "Plan file not found: $PlanFile"
        exit 1
    }
    $planContent = Get-Content $PlanFile -Raw
    $allRoles = @()
    foreach ($line in ($planContent -split "`n")) {
        if ($line -match '^\s*Roles?\s*:\s*(.+)$') {
            $lineRoles = $Matches[1] -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
            $allRoles += $lineRoles
        }
    }
    $Roles = $allRoles | Select-Object -Unique
}

if ($Roles.Count -eq 0) {
    Write-Warning "No roles to materialize."
    exit 0
}

# --- Derive PlanId ---
if (-not $PlanId -and $PlanFile) {
    $PlanId = [System.IO.Path]::GetFileNameWithoutExtension($PlanFile)
}

# --- Filter to contributed roles only (skip builtins) ---
$agentsRolesDir = Join-Path $ProjectDir ".agents" "roles"
$contributedRoles = @()
$skippedBuiltins = @()

foreach ($role in $Roles) {
    $contribPath = Join-Path $contributesDir $role
    if (Test-Path $contribPath) {
        $contributedRoles += $role
    } else {
        $skippedBuiltins += $role
    }
}

if ($skippedBuiltins.Count -gt 0) {
    Write-Host "[INFO] Skipping builtin roles (no materialization needed): $($skippedBuiltins -join ', ')"
}

if ($contributedRoles.Count -eq 0) {
    Write-Host "[INFO] No contributed roles to materialize."
    exit 0
}

Write-Host "[MATERIALIZE] Materializing $($contributedRoles.Count) contributed role(s): $($contributedRoles -join ', ')"
if ($DryRun) { Write-Host "[DRY-RUN] No files will be written." }

# --- Helper: copy file if source exists ---
function Copy-RoleArtifact {
    param([string]$Source, [string]$Dest, [string]$Label)
    if (-not (Test-Path $Source)) { return $false }
    if ($DryRun) {
        Write-Host "  [DRY-RUN] Would copy: $Label -> $Dest"
        return $true
    }
    $destDir = Split-Path $Dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Copy-Item -Path $Source -Destination $Dest -Force
    return $true
}

# --- Materialize each contributed role ---
$planRolesConfig = @{}
$materialized = 0

foreach ($role in $contributedRoles) {
    $srcDir = Join-Path $contributesDir $role
    $srcRoleJson = Join-Path $srcDir "role.json"
    $srcRoleMd = Join-Path $srcDir "ROLE.md"

    if (-not (Test-Path $srcRoleJson)) {
        Write-Warning "[$role] Missing role.json in $srcDir — skipping"
        continue
    }

    Write-Host "  [$role] Materializing..."

    # 1. HOME .agents/roles/<role>/ — Invoke-Agent.ps1:262 reads role.json from here
    #    Copy ALL artifacts (role.json, ROLE.md, subcommands.json, etc.)
    $homeAgentDest = Join-Path $homeAgentsRoles $role
    if (-not $DryRun) {
        if (-not (Test-Path $homeAgentDest)) { New-Item -ItemType Directory -Path $homeAgentDest -Force | Out-Null }
        Copy-Item -Path (Join-Path $srcDir "*") -Destination $homeAgentDest -Recurse -Force
    } else {
        $artifacts = Get-ChildItem -Path $srcDir -Name
        Write-Host "  [DRY-RUN] Would copy all artifacts ($($artifacts -join ', ')) -> ~/.ostwin/.agents/roles/$role/"
    }

    # 2. HOME roles/<role>/ — Resolve-RoleSkills.ps1:98 reads role.json from here
    $homeRoleDest = Join-Path $homeRoles $role
    Copy-RoleArtifact -Source $srcRoleJson -Dest (Join-Path $homeRoleDest "role.json") -Label "role.json -> ~/.ostwin/roles/$role/"

    # 3. OpenCode agent definition — opencode CLI reads <role>.md from here
    if (Test-Path $srcRoleMd) {
        Copy-RoleArtifact -Source $srcRoleMd -Dest (Join-Path $opencodeAgentsDir "$role.md") -Label "ROLE.md -> ~/.config/opencode/agents/$role.md"
    }

    # 4. Collect plan.roles.json config from role.json
    $roleData = Get-Content $srcRoleJson -Raw | ConvertFrom-Json
    $roleConfig = @{}
    if ($roleData.model) { $roleConfig['default_model'] = $roleData.model }
    if ($roleData.timeout) { $roleConfig['timeout_seconds'] = $roleData.timeout }
    if ($roleData.skill_refs) { $roleConfig['skill_refs'] = @($roleData.skill_refs) }
    if ($roleConfig.Count -gt 0) {
        $planRolesConfig[$role] = $roleConfig
    }

    $materialized++
}

# 5. Write/merge plan.roles.json
if ($PlanId -and $planRolesConfig.Count -gt 0) {
    $planRolesFile = Join-Path $homePlansDir "$PlanId.roles.json"

    if (-not $DryRun) {
        if (-not (Test-Path $homePlansDir)) { New-Item -ItemType Directory -Path $homePlansDir -Force | Out-Null }

        $existing = @{}
        if (Test-Path $planRolesFile) {
            try {
                $existingRaw = Get-Content $planRolesFile -Raw | ConvertFrom-Json
                foreach ($prop in $existingRaw.PSObject.Properties) {
                    $existing[$prop.Name] = $prop.Value
                }
            } catch { }
        }

        # Merge: contributed roles override existing entries for the same key
        foreach ($key in $planRolesConfig.Keys) {
            $existing[$key] = [PSCustomObject]$planRolesConfig[$key]
        }

        $existing | ConvertTo-Json -Depth 5 | Out-File -FilePath $planRolesFile -Encoding utf8 -Force
        Write-Host "  [plan.roles.json] Written/merged: $planRolesFile ($($planRolesConfig.Count) role(s))"
    } else {
        Write-Host "  [DRY-RUN] Would write plan.roles.json: $planRolesFile"
        foreach ($key in $planRolesConfig.Keys) {
            Write-Host "    $key = $($planRolesConfig[$key] | ConvertTo-Json -Compress)"
        }
    }
}

# 6. Room overrides (if WarRoomsDir provided)
if ($WarRoomsDir -and (Test-Path $WarRoomsDir)) {
    Write-Host "  [room-overrides] Materializing room overrides..."
    $roomDirs = Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue

    foreach ($roomDir in $roomDirs) {
        # Read lifecycle.json to find which contributed roles this room uses
        $lifecycleFile = Join-Path $roomDir.FullName "lifecycle.json"
        if (-not (Test-Path $lifecycleFile)) { continue }

        $lifecycle = Get-Content $lifecycleFile -Raw | ConvertFrom-Json
        $roomRoles = @()
        foreach ($stateName in $lifecycle.states.PSObject.Properties.Name) {
            $stateRole = $lifecycle.states.$stateName.role
            if ($stateRole -and $stateRole -in $contributedRoles) {
                $roomRoles += $stateRole
            }
        }
        $roomRoles = $roomRoles | Select-Object -Unique

        foreach ($role in $roomRoles) {
            $srcDir = Join-Path $contributesDir $role
            $overrideDir = Join-Path $roomDir.FullName "overrides" $role

            if (-not $DryRun) {
                if (-not (Test-Path $overrideDir)) { New-Item -ItemType Directory -Path $overrideDir -Force | Out-Null }
                Copy-Item -Path (Join-Path $srcDir "role.json") -Destination (Join-Path $overrideDir "role.json") -Force
                $roleMd = Join-Path $srcDir "ROLE.md"
                if (Test-Path $roleMd) {
                    Copy-Item -Path $roleMd -Destination (Join-Path $overrideDir "ROLE.md") -Force
                }
            }
            Write-Host "    [$($roomDir.Name)] $role -> overrides/$role/"
        }
    }
}

Write-Host ""
Write-Host "[MATERIALIZE] Done. $materialized role(s) materialized."
if ($DryRun) { Write-Host "[DRY-RUN] No files were written. Remove -DryRun to apply." }

# --- Output summary for scripting ---
Write-Output ([PSCustomObject]@{
    MaterializedRoles = $contributedRoles
    SkippedBuiltins   = $skippedBuiltins
    PlanId            = $PlanId
    PlanRolesFile     = if ($PlanId) { Join-Path $homePlansDir "$PlanId.roles.json" } else { $null }
    ArtifactPaths     = @{
        HomeAgentsRoles = $homeAgentsRoles
        HomeRoles       = $homeRoles
        OpenCodeAgents  = $opencodeAgentsDir
    }
})
