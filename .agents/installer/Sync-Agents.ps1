# ──────────────────────────────────────────────────────────────────────────────
# Sync-Agents.ps1 — Sync roles to OpenCode agents directory
#
# Copies ROLE.md from each role directory to the OpenCode agents folder
# so the OpenCode CLI can discover and invoke them as named agents.
#
# Provides: Sync-OpenCodeAgents
#
# Requires: Lib.ps1, globals: $script:InstallDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_SyncAgentsPs1Loaded) { return }
$script:_SyncAgentsPs1Loaded = $true

function Sync-OpenCodeAgents {
    [CmdletBinding()]
    param()

    $opencodeHome = if ($env:XDG_CONFIG_HOME) {
        Join-Path $env:XDG_CONFIG_HOME "opencode"
    }
    elseif ($env:USERPROFILE) {
        Join-Path $env:USERPROFILE ".config\opencode"
    }
    else {
        Join-Path $HOME ".config\opencode"
    }
    $agentsDir = Join-Path $opencodeHome "agents"

    $rolesDirs = @(
        (Join-Path $script:InstallDir ".agents\roles"),
        (Join-Path $script:InstallDir "contributes\roles")
    )

    Write-Step "Syncing agent definitions to $agentsDir..."
    if (-not (Test-Path $agentsDir)) {
        New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
    }

    $synced = 0
    $skipped = 0

    foreach ($rolesDir in $rolesDirs) {
        if (-not (Test-Path $rolesDir)) { continue }

        Get-ChildItem -Path $rolesDir -Directory | ForEach-Object {
            $roleName = $_.Name

            # Skip _base (infrastructure scripts, not a role)
            if ($roleName -eq "_base") { return }

            # Must have role.json to be a valid role
            $roleJson = Join-Path $_.FullName "role.json"
            if (-not (Test-Path $roleJson)) {
                $skipped++
                return
            }

            # Copy ROLE.md as <role-name>.md
            $roleMd = Join-Path $_.FullName "ROLE.md"
            if (Test-Path $roleMd) {
                Copy-Item -Path $roleMd -Destination (Join-Path $agentsDir "${roleName}.md") -Force
                $synced++
            }
            else {
                $skipped++
            }
        }
    }

    Write-Ok "$synced agent(s) synced to $agentsDir ($skipped skipped — no ROLE.md)"
}
