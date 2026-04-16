<#
.SYNOPSIS
    ostwin CLI — unified entry point for Agent OS (Windows PowerShell port)

.DESCRIPTION
    Multi-Agent War-Room Orchestrator.
    Full parity with the bash ostwin CLI, ported to native PowerShell.
    No dual-dispatch / ps_dispatch() pattern — commands invoke .ps1 scripts directly.

.EXAMPLE
    ostwin.ps1 run plans/my-feature.md
    ostwin.ps1 status --watch
    ostwin.ps1 plan create "My Plan"
    ostwin.ps1 skills install https://github.com/user/repo
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# ──────────────────────────────────────────────────────────────────────────────
# 1. Activate the Ostwin venv — makes `python` resolve to the managed interpreter
# ──────────────────────────────────────────────────────────────────────────────
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path ($env:USERPROFILE ?? $HOME) ".ostwin" }

$venvActivate = Join-Path $OstwinHome ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

# ──────────────────────────────────────────────────────────────────────────────
# 2. Load global .env (from ~/.ostwin/.env)
# ──────────────────────────────────────────────────────────────────────────────
function Import-EnvFile {
    [CmdletBinding()]
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -notmatch '=') { continue }
        $eqIdx = $trimmed.IndexOf('=')
        $key = $trimmed.Substring(0, $eqIdx).Trim()
        $val = $trimmed.Substring($eqIdx + 1).Trim()
        # Strip surrounding quotes
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
            ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        # Only set if not already defined
        if ($key -and -not [System.Environment]::GetEnvironmentVariable($key, 'Process')) {
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}

$globalEnv = Join-Path $OstwinHome ".env"
Import-EnvFile -Path $globalEnv

# ──────────────────────────────────────────────────────────────────────────────
# 3. Resolve AGENTS_DIR — search from cwd upward for .agents/
# ──────────────────────────────────────────────────────────────────────────────
$AgentsDir = ""

$cwd = (Get-Location).Path
if ((Test-Path (Join-Path $cwd ".agents\config.json"))) {
    # Running from project root
    $AgentsDir = (Resolve-Path (Join-Path $cwd ".agents")).Path
}
elseif ((Test-Path (Join-Path $cwd "config.json")) -and (Test-Path (Join-Path $cwd "bin"))) {
    # Running from inside .agents itself
    $AgentsDir = $cwd
}
else {
    # Walk up to find .agents
    $searchDir = $cwd
    while ($searchDir -and $searchDir -ne [System.IO.Path]::GetPathRoot($searchDir)) {
        if ((Test-Path (Join-Path $searchDir "config.json")) -and (Test-Path (Join-Path $searchDir "bin"))) {
            $AgentsDir = $searchDir
            break
        }
        $agentsCandidate = Join-Path $searchDir ".agents"
        if ((Test-Path (Join-Path $agentsCandidate "config.json"))) {
            $AgentsDir = (Resolve-Path $agentsCandidate).Path
            break
        }
        $searchDir = Split-Path $searchDir -Parent
    }
}

# Final fallback: script-relative
if (-not $AgentsDir) {
    $scriptDir = Split-Path $PSCommandPath -Parent
    $AgentsDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

# After venv activation, resolve python
$PythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" }
             elseif (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" }
             else { "python" }

# ──────────────────────────────────────────────────────────────────────────────
# 4. Load project .env (from AGENTS_DIR/.env)
# ──────────────────────────────────────────────────────────────────────────────
Import-EnvFile -Path (Join-Path (Split-Path $AgentsDir -Parent) ".env")  # project root .env
Import-EnvFile -Path (Join-Path $AgentsDir ".env")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Global variables
# ──────────────────────────────────────────────────────────────────────────────
# Version from config.json
$Version = "unknown"
try {
    $configPath = Join-Path $AgentsDir "config.json"
    if (Test-Path $configPath) {
        $configData = Get-Content $configPath -Raw | ConvertFrom-Json
        $Version = $configData.version
    }
}
catch { }

# Build hash
$BuildHash = ""
foreach ($hashFile in @((Join-Path $OstwinHome ".build-hash"), (Join-Path $AgentsDir ".build-hash"))) {
    if (Test-Path $hashFile) {
        $BuildHash = (Get-Content $hashFile -Raw).Trim()
        break
    }
}

# Dashboard URL
if (-not $env:DASHBOARD_URL) {
    $env:DASHBOARD_URL = "http://localhost:9000"
}
$DashboardUrl = $env:DASHBOARD_URL

# API key for auth headers
$OstwinApiKey = $env:OSTWIN_API_KEY
$AuthHeaders = @{}
if ($OstwinApiKey) {
    $AuthHeaders["X-API-Key"] = $OstwinApiKey
}

# Default WARROOMS_DIR
if (-not $env:WARROOMS_DIR) {
    $env:WARROOMS_DIR = Join-Path $cwd ".war-rooms"
}

# ──────────────────────────────────────────────────────────────────────────────
# 6. Helper functions
# ──────────────────────────────────────────────────────────────────────────────

function Test-DashboardReachable {
    [CmdletBinding()]
    param([string]$Url = $DashboardUrl)
    try {
        $null = Invoke-RestMethod -Uri "$Url/api/status" -Headers $AuthHeaders -TimeoutSec 3 -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Invoke-DashboardApi {
    <#
    .SYNOPSIS
        Calls a dashboard API endpoint with auth headers.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Endpoint,
        [string]$Method = "GET",
        [object]$Body,
        [switch]$Raw
    )
    $uri = "$DashboardUrl$Endpoint"
    $params = @{
        Uri         = $uri
        Method      = $Method
        Headers     = $AuthHeaders
        TimeoutSec  = 30
        ErrorAction = "Stop"
    }
    if ($Body) {
        $params["ContentType"] = "application/json"
        if ($Body -is [string]) {
            $params["Body"] = $Body
        }
        else {
            $params["Body"] = ($Body | ConvertTo-Json -Depth 10 -Compress)
        }
    }
    if ($Raw) {
        return Invoke-WebRequest @params
    }
    return Invoke-RestMethod @params
}

function Resolve-PlanId {
    <#
    .SYNOPSIS
        Resolves a plan_id (hex) or file path to a plan file path and working_dir.
    .OUTPUTS
        Returns a PSObject with PlanFile and WorkingDir properties, or $null on failure.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Arg)

    # If it's an existing file, use directly
    if (Test-Path $Arg -PathType Leaf) {
        $content = Get-Content $Arg -Raw
        $workingDir = ""
        if ($content -match '(?m)^\s*working_dir:\s*(.+)$') {
            $workingDir = $Matches[1].Trim()
        }
        if (-not $workingDir -and ($content -match '(?m)^>\s*Project:\s*(.+)$')) {
            $workingDir = $Matches[1].Trim()
        }
        return [PSCustomObject]@{ PlanFile = (Resolve-Path $Arg).Path; WorkingDir = $workingDir }
    }

    # If it looks like a hex plan_id (8-64 hex chars, no slashes/dots)
    if ($Arg -match '^[0-9a-fA-F]{8,64}$') {
        if (Test-DashboardReachable) {
            try {
                $apiResponse = Invoke-DashboardApi -Endpoint "/api/plans/$Arg"
                $plan = $apiResponse.plan
                $filename = $plan.filename
                $workingDir = if ($plan.working_dir) { $plan.working_dir }
                              elseif ($plan.meta.working_dir) { $plan.meta.working_dir }
                              else { "" }

                $planFile = ""
                if ($filename) {
                    $candidates = @(
                        (Join-Path $AgentsDir "plans" $filename),
                        (Join-Path $OstwinHome ".agents\plans" $filename)
                    )
                    foreach ($c in $candidates) {
                        if (Test-Path $c) {
                            $planFile = $c
                            break
                        }
                    }
                    if (-not $planFile) {
                        $planFile = $candidates[0]  # For error reporting
                    }
                }

                if ($planFile -and (Test-Path $planFile)) {
                    Write-Host ([char]0x2713 + " Resolved plan_id '$Arg' -> $planFile")
                    if ($workingDir) {
                        Write-Host "  Working dir: $workingDir"
                    }
                    return [PSCustomObject]@{ PlanFile = $planFile; WorkingDir = $workingDir }
                }
                else {
                    Write-Error ([char]0x2717 + " Plan file not found for plan_id '$Arg'")
                    Write-Error "  Searched: $AgentsDir\plans\ and ~\.ostwin\.agents\plans\"
                    return $null
                }
            }
            catch {
                Write-Error ([char]0x2717 + " Plan '$Arg' not found via API")
                return $null
            }
        }
        else {
            Write-Warning "Dashboard not reachable at $DashboardUrl"
            Write-Warning "Cannot resolve plan_id. Start dashboard or pass a file path."
            return $null
        }
    }

    # Not a file and not hex — pass through
    return [PSCustomObject]@{ PlanFile = $Arg; WorkingDir = "" }
}

# ──────────────────────────────────────────────────────────────────────────────
# 7. Help text
# ──────────────────────────────────────────────────────────────────────────────
function Show-OstwinHelp {
    $hashSuffix = if ($BuildHash) { " ($BuildHash)" } else { "" }
    Write-Host @"
ostwin v${Version}${hashSuffix} -- Multi-Agent War-Room Orchestrator

Usage:
  ostwin <command> [options]

Commands:
  agent [args...]    Run the Agent OS agent (opencode run wrapper)
  run <plan_id|file> Execute a plan by ID or file path
                     Options: --dry-run, --resume, --expand, --working-dir PATH
  plan <sub>        Plan management (AI-assisted)
                     Subcommands: create [Title|file.md] [--file FILE], start, list
  init [directory]  Scaffold Agent OS into a project
  sync [directory]  Sync framework updates to an initialized project
  status            Show war-room dashboard
                     Options: --json, --watch
  logs [room-id]    View channel logs
                     Options: --follow, --type TYPE, --last N
  stop              Graceful shutdown of running manager
                     Options: --force
  dashboard         Launch web dashboard
                     Options: --port PORT, --project-dir PATH
  channel <sub>     Manage communication channels (telegram, discord, slack)
                     Subcommands: start, stop, status, logs, deploy,
                                  list, connect, disconnect, test, pair
  clone-role <role> Clone a role to project-local for override
                     Options: --project-dir PATH
  config            View or update configuration
                     Options: --get KEY, --set KEY VALUE
  mac <script> <cmd>  macOS desktop automation (shorthand for role dispatch)
                      Scripts: app, window, click, type, capture, system,
                               finder, axbridge, devtools
                      Run 'ostwin mac <script> help' for per-script usage
  role <name> [sub]  Run a role's subcommand
                       Options: ostwin role (list roles)
                                ostwin role <name> (show subcommands)
                                ostwin role <name> <sub> [args...]
  health            Check system health
  skills <sub>      Manage skills installation and sync
                     Subcommands: sync, install [<slug>|--from DIR], list,
                                  search <query>, update [--all|<slug>], remove <slug>
  mcp               Manage MCP extensions
                     Subcommands: install, list, catalog, remove, sync
  reload-env        Reload ~/.ostwin/.env into MCP config env blocks
  test              Run test suites
                     Options: --suite NAME, --verbose
  version           Show version

Examples:
  ostwin run plans/my-feature.md
  ostwin run plans/my-feature.md --dry-run
  ostwin run plans/my-feature.md --resume --expand
  ostwin status --watch
  ostwin logs room-001 --follow
  ostwin stop

Environment:
  ENGINEER_CMD        Override engineer CLI
  QA_CMD              Override QA CLI
  MOCK_SIGNOFF        Set to "true" for auto-signoff (testing)
  AGENT_OS_LOG_LEVEL  Log level: DEBUG, INFO, WARN, ERROR (default: INFO)
  WARROOMS_DIR        Override war-rooms data directory
                      (default: <project>\.war-rooms)
"@
}

# ──────────────────────────────────────────────────────────────────────────────
# 8. Command dispatch
# ──────────────────────────────────────────────────────────────────────────────
switch ($Command) {

    # ── agent ────────────────────────────────────────────────────────────────
    "agent" {
        # Prefer local repo's agent script, fallback to OSTWIN_HOME copy
        $scriptDir = Split-Path $PSCommandPath -Parent
        $localAgent = Join-Path $scriptDir "agent"
        $localAgentPs1 = Join-Path $scriptDir "agent.ps1"

        if (Test-Path $localAgentPs1) {
            & pwsh -NoProfile -File $localAgentPs1 @Arguments
        }
        elseif (Test-Path $localAgent) {
            # Unix agent script — try via bash if available
            if (Get-Command bash -ErrorAction SilentlyContinue) {
                & bash $localAgent @Arguments
            }
            else {
                $fallbackAgent = Join-Path $OstwinHome ".agents\bin\agent"
                if (Test-Path $fallbackAgent) {
                    & bash $fallbackAgent @Arguments
                }
                else {
                    Write-Error "[ERROR] No agent script found and bash not available."
                    exit 1
                }
            }
        }
        else {
            $homeAgent = Join-Path $OstwinHome ".agents\bin\agent"
            if (Test-Path $homeAgent) {
                & bash $homeAgent @Arguments
            }
            else {
                Write-Error "[ERROR] Agent script not found."
                exit 1
            }
        }
    }

    # ── run ──────────────────────────────────────────────────────────────────
    "run" {
        $runArgs = [System.Collections.ArrayList]::new()
        $planArgResolved = $false
        $resolvedPlanFile = ""
        $resolvedWorkingDir = ""

        foreach ($a in $Arguments) {
            if ((-not $planArgResolved) -and ($a -notmatch '^--')) {
                $resolved = Resolve-PlanId -Arg $a
                if (-not $resolved) { exit 1 }
                $resolvedPlanFile = $resolved.PlanFile
                $resolvedWorkingDir = $resolved.WorkingDir
                $null = $runArgs.Add("--plan-file")
                $null = $runArgs.Add($resolvedPlanFile)
                if ($resolvedWorkingDir) {
                    $null = $runArgs.Add("--working-dir")
                    $null = $runArgs.Add($resolvedWorkingDir)
                }
                $planArgResolved = $true
            }
            else {
                $null = $runArgs.Add($a)
            }
        }

        # ── Check for missing roles ──
        if ($planArgResolved -and (Test-Path $resolvedPlanFile)) {
            $planContent = Get-Content $resolvedPlanFile -Raw
            $neededRoles = [regex]::Matches($planContent, '(?m)^Role:\s*(.+)$') |
                ForEach-Object { $_.Groups[1].Value.Trim() -split '\s+' | Select-Object -First 1 } |
                Where-Object { $_ -and $_ -ne '<role-name>' } |
                Sort-Object -Unique

            $projectRoot = Split-Path $AgentsDir -Parent
            $missingRoles = @()
            foreach ($r in $neededRoles) {
                $found = $false
                foreach ($roleDir in @(
                    (Join-Path $AgentsDir "roles" $r),
                    (Join-Path $OstwinHome ".agents\roles" $r),
                    (Join-Path $projectRoot "contributes\roles" $r)
                )) {
                    if (Test-Path $roleDir -PathType Container) {
                        $found = $true
                        break
                    }
                }
                if (-not $found) { $missingRoles += $r }
            }

            if ($missingRoles.Count -gt 0) {
                Write-Host ([char]0x26A0 + " Found missing roles needed by the plan: $($missingRoles -join ', ')")

                $isInteractive = [Environment]::UserInteractive -and
                    (-not ($runArgs -contains '--non-interactive')) -and
                    (-not ($runArgs -contains '-n'))

                $doCreate = $false
                if ($isInteractive) {
                    $reply = Read-Host "Do you want the manager agent to automatically create these roles now? [Y/n]"
                    if (-not $reply -or $reply -match '^[Yy]') { $doCreate = $true }
                }
                else {
                    Write-Host "Non-interactive mode. Auto-creating missing roles..."
                    $doCreate = $true
                }

                if ($doCreate) {
                    Write-Host "Running manager agent to scaffold roles..."
                    foreach ($mr in $missingRoles) {
                        $createRoleScript = Join-Path $AgentsDir "bin\Auto-CreateRole.ps1"
                        if (Test-Path $createRoleScript) {
                            & pwsh -NoProfile -File $createRoleScript $mr $AgentsDir
                        }
                        else {
                            $bashScript = Join-Path $AgentsDir "bin\auto_create_role.sh"
                            if (Test-Path $bashScript) {
                                & bash $bashScript $mr $AgentsDir
                            }
                        }
                    }

                    # Verify creation
                    $failedRoles = @()
                    foreach ($mr in $missingRoles) {
                        $found = $false
                        foreach ($roleDir in @(
                            (Join-Path $AgentsDir "roles" $mr),
                            (Join-Path $OstwinHome ".agents\roles" $mr),
                            (Join-Path $projectRoot "contributes\roles" $mr)
                        )) {
                            if (Test-Path $roleDir -PathType Container) {
                                $found = $true
                                break
                            }
                        }
                        if (-not $found) { $failedRoles += $mr }
                    }

                    if ($failedRoles.Count -gt 0) {
                        Write-Error ([char]0x2717 + " Failed to create roles: $($failedRoles -join ', '). Aborting.")
                        exit 1
                    }
                }
                else {
                    Write-Host "Aborting run. Please create the missing roles manually."
                    exit 1
                }
            }
        }

        # ── Ensure working_dir exists and is initialized ──
        if (-not $resolvedWorkingDir -and (Test-Path $resolvedPlanFile)) {
            $pc = Get-Content $resolvedPlanFile -Raw
            if ($pc -match '(?m)^\s*working_dir:\s*(.+)$') {
                $resolvedWorkingDir = $Matches[1].Trim()
            }
            if (-not $resolvedWorkingDir -and ($pc -match '(?m)^>\s*Project:\s*(.+)$')) {
                $resolvedWorkingDir = $Matches[1].Trim()
            }
        }

        if ($resolvedWorkingDir -and $resolvedWorkingDir -ne ".") {
            if (-not (Test-Path $resolvedWorkingDir -PathType Container)) {
                Write-Host ([char]0x1F4C1 + " Creating project directory: $resolvedWorkingDir")
                New-Item -ItemType Directory -Path $resolvedWorkingDir -Force | Out-Null
            }
            if (-not (Test-Path (Join-Path $resolvedWorkingDir ".agents"))) {
                Write-Host ([char]0x1F527 + " Initializing project with ostwin init...")
                $initPs1 = Join-Path $AgentsDir "init.ps1"
                $initScript = Join-Path $AgentsDir "init.sh"
                if (Test-Path $initPs1) {
                    & pwsh -NoProfile -File $initPs1 $resolvedWorkingDir
                }
                elseif (Test-Path $initScript) {
                    Push-Location $resolvedWorkingDir
                    & bash $initScript .
                    Pop-Location
                }
            }
        }

        # Dispatch to Start-Plan.ps1
        $startPlan = Join-Path $AgentsDir "plan\Start-Plan.ps1"
        if (Test-Path $startPlan) {
            # Convert remaining bash-style flags to PS params
            $psArgs = [System.Collections.ArrayList]::new()
            $i = 0
            while ($i -lt $runArgs.Count) {
                switch ($runArgs[$i]) {
                    '--dry-run'     { $null = $psArgs.Add('-DryRun'); $i++ }
                    '--resume'      { $null = $psArgs.Add('-Resume'); $i++ }
                    '--expand'      { $null = $psArgs.Add('-Expand'); $i++ }
                    '--review'      { $null = $psArgs.Add('-Review'); $i++ }
                    '--max-rooms'   { $null = $psArgs.Add('-MaxConcurrent'); $i++; $null = $psArgs.Add($runArgs[$i]); $i++ }
                    '--working-dir' { $null = $psArgs.Add('-ProjectDir'); $i++; $null = $psArgs.Add($runArgs[$i]); $i++ }
                    '--plan-file'   { $null = $psArgs.Add('-PlanFile'); $i++; $null = $psArgs.Add($runArgs[$i]); $i++ }
                    '--non-interactive' { $null = $psArgs.Add('-NonInteractive'); $i++ }
                    '-n'            { $null = $psArgs.Add('-NonInteractive'); $i++ }
                    default         { $null = $psArgs.Add($runArgs[$i]); $i++ }
                }
            }
            & pwsh -NoProfile -File $startPlan @psArgs
        }
        else {
            # Fallback to run.sh
            $runSh = Join-Path $AgentsDir "run.sh"
            if (Test-Path $runSh) {
                & bash $runSh @runArgs
            }
            else {
                Write-Error "[ERROR] Neither Start-Plan.ps1 nor run.sh found."
                exit 1
            }
        }
    }

    # ── plan ─────────────────────────────────────────────────────────────────
    "plan" {
        $planSub = if ($Arguments.Count -gt 0) { $Arguments[0] } else { "create" }
        $planArgs = if ($Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }

        switch ($planSub) {
            "create" {
                $planTitle = ""
                $initFile = ""
                $projectDir = $cwd

                # Parse arguments
                $idx = 0
                while ($idx -lt $planArgs.Count) {
                    switch ($planArgs[$idx]) {
                        { $_ -eq '--file' -or $_ -eq '-f' } {
                            $idx++
                            $initFile = $planArgs[$idx]
                            $idx++
                        }
                        { $_.StartsWith('-') } {
                            Write-Error "Unknown option for plan create: $($planArgs[$idx])"
                            exit 1
                        }
                        default {
                            # Smart detect: if existing .md file, treat as --file
                            if (-not $initFile -and (Test-Path $planArgs[$idx]) -and $planArgs[$idx] -match '\.md$') {
                                $initFile = $planArgs[$idx]
                            }
                            elseif (-not $planTitle) {
                                $planTitle = $planArgs[$idx]
                            }
                            $idx++
                        }
                    }
                }

                # Read init file content if provided
                $initContent = ""
                if ($initFile) {
                    if (-not (Test-Path $initFile)) {
                        Write-Error ([char]0x2717 + " File not found: $initFile")
                        exit 1
                    }
                    $initContent = Get-Content $initFile -Raw

                    # Extract title from markdown if not explicitly provided
                    if (-not $planTitle) {
                        $titleMatch = [regex]::Match($initContent, '(?m)^#\s+(?:Plan:\s*)?(.+)')
                        if ($titleMatch.Success) {
                            $planTitle = $titleMatch.Groups[1].Value.Trim()
                        }
                        else {
                            $planTitle = [System.IO.Path]::GetFileNameWithoutExtension($initFile)
                        }
                    }
                }

                if (-not $planTitle) { $planTitle = "Untitled" }

                # Check dashboard reachable
                if (-not (Test-DashboardReachable)) {
                    Write-Warning "Dashboard not reachable at $DashboardUrl"
                    Write-Warning "Start it with: ostwin dashboard"
                    exit 1
                }

                # Build JSON payload
                $payload = @{ path = $projectDir; title = $planTitle }
                if ($initContent) { $payload["content"] = $initContent }
                $jsonPayload = $payload | ConvertTo-Json -Depth 5 -Compress

                # Create plan via API
                try {
                    $response = Invoke-DashboardApi -Endpoint "/api/plans/create" -Method POST -Body $jsonPayload
                }
                catch {
                    Write-Error ([char]0x2717 + " Failed to create plan: $_")
                    exit 1
                }

                $planId = $response.plan_id
                $planUrl = $response.url

                if (-not $planId) {
                    Write-Error ([char]0x2717 + " Failed to parse plan ID from response")
                    exit 1
                }

                # Prefer tunnel URL
                $shareUrl = $DashboardUrl
                try {
                    $tunnelData = Invoke-DashboardApi -Endpoint "/api/tunnel/status"
                    if ($tunnelData.url) { $shareUrl = $tunnelData.url }
                }
                catch { }

                $editorUrl = "${shareUrl}${planUrl}"
                Write-Host ([char]0x2713 + " Plan created: $planId")
                Write-Host "  Title:  $planTitle"
                Write-Host "  Dir:    $projectDir"
                if ($initFile) { Write-Host "  Source: $initFile" }
                Write-Host "  Editor: $editorUrl"

                # Open browser on Windows
                try { Start-Process $editorUrl } catch { Write-Host "  -> Open this URL in your browser to edit the plan" }
            }

            "start" {
                $startArgs = [System.Collections.ArrayList]::new()
                $startResolved = $false

                foreach ($a in $planArgs) {
                    if ((-not $startResolved) -and ($a -notmatch '^--')) {
                        $resolved = Resolve-PlanId -Arg $a
                        if (-not $resolved) { exit 1 }
                        $null = $startArgs.Add($resolved.PlanFile)
                        if ($resolved.WorkingDir) {
                            $null = $startArgs.Add("--working-dir")
                            $null = $startArgs.Add($resolved.WorkingDir)
                        }
                        $startResolved = $true
                    }
                    else {
                        $null = $startArgs.Add($a)
                    }
                }

                $startPlan = Join-Path $AgentsDir "plan\Start-Plan.ps1"
                if (Test-Path $startPlan) {
                    # Translate flags
                    $psArgs = [System.Collections.ArrayList]::new()
                    $si = 0
                    while ($si -lt $startArgs.Count) {
                        switch ($startArgs[$si]) {
                            '--dry-run'     { $null = $psArgs.Add('-DryRun'); $si++ }
                            '--resume'      { $null = $psArgs.Add('-Resume'); $si++ }
                            '--expand'      { $null = $psArgs.Add('-Expand'); $si++ }
                            '--review'      { $null = $psArgs.Add('-Review'); $si++ }
                            '--working-dir' { $null = $psArgs.Add('-ProjectDir'); $si++; $null = $psArgs.Add($startArgs[$si]); $si++ }
                            default         { $null = $psArgs.Add($startArgs[$si]); $si++ }
                        }
                    }
                    & pwsh -NoProfile -File $startPlan @psArgs
                }
                else {
                    $runSh = Join-Path $AgentsDir "run.sh"
                    if (Test-Path $runSh) { & bash $runSh @startArgs }
                    else { Write-Error "[ERROR] Start-Plan.ps1 and run.sh not found."; exit 1 }
                }
            }

            "list" {
                if (-not (Test-DashboardReachable)) {
                    Write-Warning "Dashboard not reachable at $DashboardUrl"
                    exit 1
                }
                try {
                    $data = Invoke-DashboardApi -Endpoint "/api/plans"
                    $plans = $data.plans
                    if (-not $plans -or $plans.Count -eq 0) {
                        Write-Host "No plans found."
                    }
                    else {
                        foreach ($p in $plans) {
                            $id = $p.plan_id.Substring(0, [Math]::Min(12, $p.plan_id.Length))
                            $title = if ($p.title) { $p.title } else { "Untitled" }
                            $status = if ($p.status) { $p.status } else { "unknown" }
                            $epicCount = if ($p.epic_count) { $p.epic_count } else { 0 }
                            Write-Host ("  {0}  {1,-30}  {2,-10}  {3} epics" -f $id, $title, $status, $epicCount)
                        }
                    }
                }
                catch {
                    Write-Host "Failed to list plans."
                }
            }

            "clear" {
                $force = $false
                foreach ($a in $planArgs) {
                    if ($a -in @('-f', '--force', '-y', '--yes')) { $force = $true }
                }

                $plansDir = Join-Path $OstwinHome ".agents\plans"
                $zvecPlans = Join-Path $OstwinHome ".zvec\plans_v2"

                # Count files to remove
                $fileCount = 0
                if (Test-Path $plansDir) {
                    $fileCount = (Get-ChildItem -Path $plansDir -File | Where-Object { $_.Name -ne 'PLAN.template.md' }).Count
                }
                $zvecExists = Test-Path $zvecPlans -PathType Container

                if ($fileCount -eq 0 -and -not $zvecExists) {
                    Write-Host ([char]0x2713 + " No plans to clear (registry already empty)")
                    exit 0
                }

                Write-Host "Will clear:"
                if ($fileCount -gt 0) { Write-Host "  * $fileCount plan file(s) in $plansDir" }
                if ($zvecExists) { Write-Host "  * zvec index at $zvecPlans" }

                if (-not $force) {
                    $reply = Read-Host "Proceed? [y/N]"
                    if ($reply -notmatch '^[Yy]') {
                        Write-Host "Cancelled."
                        exit 0
                    }
                }

                # Stop dashboard if running
                $dashboardWasRunning = $false
                $pidFile = Join-Path $OstwinHome "dashboard.pid"
                if (Test-Path $pidFile) {
                    $dashPid = (Get-Content $pidFile -Raw).Trim()
                    try {
                        $proc = Get-Process -Id $dashPid -ErrorAction Stop
                        $dashboardWasRunning = $true
                        Write-Host "-> Stopping dashboard (PID $dashPid)..."
                        Stop-Process -Id $dashPid -Force -ErrorAction SilentlyContinue
                        # Wait up to 5s
                        for ($w = 0; $w -lt 5; $w++) {
                            try { $null = Get-Process -Id $dashPid -ErrorAction Stop; Start-Sleep -Seconds 1 }
                            catch { break }
                        }
                    }
                    catch { }
                }

                # Delete plan files (preserve template)
                if ($fileCount -gt 0) {
                    Get-ChildItem -Path $plansDir -File | Where-Object { $_.Name -ne 'PLAN.template.md' } | Remove-Item -Force
                    Write-Host ([char]0x2713 + " Deleted $fileCount plan file(s)")
                }

                # Remove zvec index
                if ($zvecExists) {
                    Remove-Item -Path $zvecPlans -Recurse -Force
                    Write-Host ([char]0x2713 + " Cleared zvec plans index")
                }

                # Restart dashboard if it was running
                if ($dashboardWasRunning) {
                    Write-Host "-> Restarting dashboard..."
                    $logsDir = Join-Path $OstwinHome "logs"
                    if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
                    $dashScript = Join-Path $AgentsDir "dashboard.sh"
                    if (Test-Path $dashScript) {
                        $dashProc = Start-Process -FilePath "bash" `
                            -ArgumentList $dashScript, "--background", "--port", "9000", "--project-dir", $OstwinHome `
                            -NoNewWindow -PassThru `
                            -RedirectStandardOutput (Join-Path $logsDir "dashboard.log") `
                            -RedirectStandardError (Join-Path $logsDir "dashboard-error.log")
                        Write-Host "  PID $($dashProc.Id)"
                    }
                }

                Write-Host ([char]0x2713 + " All plans cleared")
            }

            default {
                Write-Error "Unknown plan subcommand: $planSub"
                Write-Host "  Usage: ostwin plan create [Title] [--file FILE]"
                Write-Host "         ostwin plan start [plan-file]"
                Write-Host "         ostwin plan list"
                Write-Host "         ostwin plan clear [--force]"
                exit 1
            }
        }
    }

    # ── init ─────────────────────────────────────────────────────────────────
    "init" {
        $initPs1 = Join-Path $AgentsDir "init.ps1"
        $initSh = Join-Path $AgentsDir "init.sh"
        if (Test-Path $initPs1) {
            # Translate bash-style flags to PS params
            $psArgs = [System.Collections.ArrayList]::new()
            $ii = 0
            while ($ii -lt $Arguments.Count) {
                switch ($Arguments[$ii]) {
                    { $_ -in @('--yes', '-y') } { $null = $psArgs.Add('-Yes'); $ii++ }
                    { $_ -in @('--help', '-h') } { $null = $psArgs.Add('-Help'); $ii++ }
                    default { $null = $psArgs.Add($Arguments[$ii]); $ii++ }
                }
            }
            & pwsh -NoProfile -File $initPs1 @psArgs
        }
        elseif ((Test-Path $initSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            & bash $initSh @Arguments
        }
        else {
            Write-Error "[ERROR] Neither init.ps1 nor init.sh found."
            exit 1
        }
    }

    # ── sync ─────────────────────────────────────────────────────────────────
    "sync" {
        $syncPs1 = Join-Path $AgentsDir "sync.ps1"
        $syncSh = Join-Path $AgentsDir "sync.sh"
        if (Test-Path $syncPs1) {
            & pwsh -NoProfile -File $syncPs1 @Arguments
        }
        elseif ((Test-Path $syncSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            & bash $syncSh @Arguments
        }
        else {
            Write-Error "[ERROR] Neither sync.ps1 nor sync.sh found."
            exit 1
        }
    }

    # ── status ───────────────────────────────────────────────────────────────
    "status" {
        $statusPs1 = Join-Path $AgentsDir "war-rooms\Get-WarRoomStatus.ps1"
        if (Test-Path $statusPs1) {
            # Translate flags
            $psArgs = [System.Collections.ArrayList]::new()
            $si = 0
            while ($si -lt $Arguments.Count) {
                switch ($Arguments[$si]) {
                    '--json'  { $null = $psArgs.Add('-JsonOutput'); $si++ }
                    '--watch' { $null = $psArgs.Add('-Watch'); $si++ }
                    default   { $null = $psArgs.Add($Arguments[$si]); $si++ }
                }
            }
            & pwsh -NoProfile -File $statusPs1 @psArgs
        }
        else {
            $statusSh = Join-Path $AgentsDir "war-rooms\status.sh"
            if (Test-Path $statusSh) { & bash $statusSh @Arguments }
            else { Write-Error "[ERROR] Status script not found."; exit 1 }
        }
    }

    # ── logs ─────────────────────────────────────────────────────────────────
    "logs" {
        $logsPs1 = Join-Path $AgentsDir "logs.ps1"
        $logsSh = Join-Path $AgentsDir "logs.sh"
        if (Test-Path $logsPs1) {
            # Translate bash-style flags to PS params
            $psArgs = [System.Collections.ArrayList]::new()
            $li = 0
            while ($li -lt $Arguments.Count) {
                switch ($Arguments[$li]) {
                    { $_ -in @('--follow', '-f') } { $null = $psArgs.Add('-Follow'); $li++ }
                    '--type'  { $null = $psArgs.Add('-Type'); $li++; $null = $psArgs.Add($Arguments[$li]); $li++ }
                    '--from'  { $null = $psArgs.Add('-From'); $li++; $null = $psArgs.Add($Arguments[$li]); $li++ }
                    '--last'  { $null = $psArgs.Add('-Last'); $li++; $null = $psArgs.Add($Arguments[$li]); $li++ }
                    default   { $null = $psArgs.Add($Arguments[$li]); $li++ }
                }
            }
            & pwsh -NoProfile -File $logsPs1 @psArgs
        }
        elseif ((Test-Path $logsSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            & bash $logsSh @Arguments
        }
        else {
            Write-Error "[ERROR] Neither logs.ps1 nor logs.sh found."
            exit 1
        }
    }

    # ── stop ─────────────────────────────────────────────────────────────────
    "stop" {
        $forceStop = $Arguments -contains '--force'

        # Stop dashboard
        $pidFile = Join-Path $OstwinHome "dashboard.pid"
        if (Test-Path $pidFile) {
            $dashPid = (Get-Content $pidFile -Raw).Trim()
            try {
                $proc = Get-Process -Id $dashPid -ErrorAction Stop
                Write-Host "Stopping dashboard (PID $dashPid)..."
                if ($forceStop) {
                    # Force kill entire process tree immediately
                    & taskkill /F /T /PID $dashPid 2>$null | Out-Null
                }
                else {
                    # Graceful: send termination signal, wait up to 5s
                    Stop-Process -Id $dashPid -ErrorAction SilentlyContinue
                    for ($w = 0; $w -lt 5; $w++) {
                        try { $null = Get-Process -Id $dashPid -ErrorAction Stop; Start-Sleep -Seconds 1 }
                        catch { break }
                    }
                    # Force kill tree if still alive
                    try {
                        $null = Get-Process -Id $dashPid -ErrorAction Stop
                        & taskkill /F /T /PID $dashPid 2>$null | Out-Null
                    } catch {}
                }
                Write-Host ([char]0x2713 + " Dashboard stopped")
            }
            catch {
                Write-Host "Dashboard not running (stale PID file)"
            }
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
        else {
            Write-Host "No dashboard PID file found"
        }

        # Stop channel processes — check both legacy and current PID file locations
        $channelPidFile = Join-Path $OstwinHome "channels.pid"
        $channelPidFileAlt = Join-Path $OstwinHome ".agents\channel.pid"
        $chanPid = $null
        foreach ($cpf in @($channelPidFile, $channelPidFileAlt)) {
            if (Test-Path $cpf) {
                $chanPid = (Get-Content $cpf -Raw).Trim()
                $channelPidFile = $cpf
                break
            }
        }
        if ($chanPid) {
            try {
                $proc = Get-Process -Id $chanPid -ErrorAction Stop
                Write-Host "Stopping channels (PID $chanPid)..."
                if ($forceStop) {
                    & taskkill /F /T /PID $chanPid 2>$null | Out-Null
                }
                else {
                    Stop-Process -Id $chanPid -ErrorAction SilentlyContinue
                    for ($w = 0; $w -lt 5; $w++) {
                        try { $null = Get-Process -Id $chanPid -ErrorAction Stop; Start-Sleep -Seconds 1 }
                        catch { break }
                    }
                    try {
                        $null = Get-Process -Id $chanPid -ErrorAction Stop
                        & taskkill /F /T /PID $chanPid 2>$null | Out-Null
                    } catch {}
                }
                Write-Host ([char]0x2713 + " Channels stopped")
            }
            catch {
                Write-Host "Channel process not running (stale PID file)"
            }
            Remove-Item $channelPidFile -Force -ErrorAction SilentlyContinue
        }

        # Also try the bash stop script for any additional cleanup (Unix-like only)
        $stopSh = Join-Path $AgentsDir "stop.sh"
        if ((Test-Path $stopSh) -and (Get-Command bash -ErrorAction SilentlyContinue) -and ($IsLinux -or $IsMacOS)) {
            & bash $stopSh @Arguments 2>$null
        }

        Write-Host ([char]0x2713 + " Shutdown complete")
    }

    # ── dashboard ────────────────────────────────────────────────────────────
    "dashboard" {
        $dashPs1 = Join-Path $AgentsDir "dashboard.ps1"
        $dashSh = Join-Path $AgentsDir "dashboard.sh"

        if (Test-Path $dashPs1) {
            # Translate bash-style flags to PS params
            $psArgs = [System.Collections.ArrayList]::new()
            $hasProjectDir = $false
            $di = 0
            while ($di -lt $Arguments.Count) {
                switch ($Arguments[$di]) {
                    '--port'        { $null = $psArgs.Add('-Port'); $di++; $null = $psArgs.Add($Arguments[$di]); $di++ }
                    '--project-dir' { $hasProjectDir = $true; $null = $psArgs.Add('-ProjectDir'); $di++; $null = $psArgs.Add($Arguments[$di]); $di++ }
                    '--background'  { $null = $psArgs.Add('-Background'); $di++ }
                    { $_ -in @('-h', '--help') } { $null = $psArgs.Add('-Help'); $di++ }
                    default         { $null = $psArgs.Add($Arguments[$di]); $di++ }
                }
            }
            if (-not $hasProjectDir) {
                $null = $psArgs.Insert(0, $OstwinHome)
                $null = $psArgs.Insert(0, "-ProjectDir")
            }
            & pwsh -NoProfile -File $dashPs1 @psArgs
        }
        elseif ((Test-Path $dashSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            $dashArgs = [System.Collections.ArrayList]::new()
            $hasProjectDir = $false
            foreach ($a in $Arguments) {
                if ($a -eq '--project-dir') { $hasProjectDir = $true }
                $null = $dashArgs.Add($a)
            }
            if (-not $hasProjectDir) {
                $null = $dashArgs.Insert(0, $OstwinHome)
                $null = $dashArgs.Insert(0, "--project-dir")
            }
            & bash $dashSh @dashArgs
        }
        else {
            Write-Error "[ERROR] Neither dashboard.ps1 nor dashboard.sh found."
            exit 1
        }
    }

    # ── channel ──────────────────────────────────────────────────────────────
    "channel" {
        $channelCmd = Join-Path $AgentsDir "bin\channel_cmd.py"
        if (Test-Path $channelCmd) {
            & $PythonCmd $channelCmd @Arguments
        }
        else {
            Write-Error "[ERROR] channel_cmd.py not found at $channelCmd"
            exit 1
        }
    }

    # ── clone-role ───────────────────────────────────────────────────────────
    "clone-role" {
        if ($Arguments.Count -eq 0) {
            Write-Host "Usage: ostwin clone-role <role> [--project-dir <path>]"
            exit 1
        }

        $roleName = $Arguments[0]
        $cloneProjectDir = $cwd
        $idx = 1
        while ($idx -lt $Arguments.Count) {
            if ($Arguments[$idx] -eq '--project-dir' -and ($idx + 1) -lt $Arguments.Count) {
                $idx++
                $cloneProjectDir = $Arguments[$idx]
            }
            $idx++
        }

        # Delegate to: ostwin role manager clone -RoleName <role> -ProjectDir <path>
        & $PSCommandPath role manager clone -RoleName $roleName -ProjectDir $cloneProjectDir
    }

    # ── skills ───────────────────────────────────────────────────────────────
    "skills" {
        $skillsSub = if ($Arguments.Count -gt 0) { $Arguments[0] } else { "sync" }
        $skillsArgs = if ($Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }

        # Find sync-skills script (prefer .ps1 over .sh)
        $syncScript = Join-Path $AgentsDir "sync-skills.ps1"
        if (-not (Test-Path $syncScript)) {
            $syncScript = Join-Path $OstwinHome "sync-skills.ps1"
        }
        if (-not (Test-Path $syncScript)) {
            $syncScript = Join-Path $AgentsDir "sync-skills.sh"
        }
        if (-not (Test-Path $syncScript)) {
            $syncScript = Join-Path $OstwinHome "sync-skills.sh"
        }

        # Find clawhub-install script (prefer .ps1 over .sh)
        $clawHubScript = Join-Path $AgentsDir "clawhub-install.ps1"
        if (-not (Test-Path $clawHubScript)) {
            $clawHubScript = Join-Path $OstwinHome "clawhub-install.ps1"
        }
        if (-not (Test-Path $clawHubScript)) {
            $clawHubScript = Join-Path $AgentsDir "clawhub-install.sh"
        }
        if (-not (Test-Path $clawHubScript)) {
            $clawHubScript = Join-Path $OstwinHome "clawhub-install.sh"
        }

        switch ($skillsSub) {
            "sync" {
                if (-not (Test-Path $syncScript)) {
                    Write-Error ([char]0x2717 + " sync-skills script not found")
                    exit 1
                }
                $env:OSTWIN_HOME = $OstwinHome
                if ($syncScript -match '\.ps1$') {
                    & pwsh -NoProfile -File $syncScript @skillsArgs
                } else {
                    & bash $syncScript @skillsArgs
                }
            }

            "install" {
                $fromDir = ""
                $agentRole = ""
                $extraArgs = [System.Collections.ArrayList]::new()
                $si = 0
                while ($si -lt $skillsArgs.Count) {
                    switch ($skillsArgs[$si]) {
                        '--from'  { $si++; $fromDir = $skillsArgs[$si]; $si++ }
                        '--agent' { $si++; $agentRole = $skillsArgs[$si]; $si++ }
                        default   { $null = $extraArgs.Add($skillsArgs[$si]); $si++ }
                    }
                }

                # Check for GitHub URL or ClawHub slug
                if (-not $fromDir -and $extraArgs.Count -gt 0) {
                    $firstArg = $extraArgs[0]

                    # ── GitHub URL install ──
                    if ($firstArg -match '^https?://github\.com/' -or $firstArg -match '^git@github\.com:') {
                        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
                            Write-Error ([char]0x2717 + " git is required for GitHub installs but was not found in PATH.")
                            exit 1
                        }

                        $ghUrl = $firstArg
                        $ghRepoName = [System.IO.Path]::GetFileNameWithoutExtension(($ghUrl -split '/')[-1])

                        Write-Host "Installing skill from GitHub: $ghUrl"

                        $ghTmp = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-skill-$([guid]::NewGuid().ToString('N').Substring(0,8))"
                        try {
                            Write-Host "  Cloning repository..."
                            $cloneResult = & git clone --depth 1 $ghUrl "$ghTmp\repo" 2>&1
                            if ($LASTEXITCODE -ne 0) {
                                Write-Host ($cloneResult | ForEach-Object { "    $_" })
                                Write-Error ([char]0x2717 + " git clone failed for $ghUrl")
                                exit 1
                            }

                            $ghCommit = & git -C "$ghTmp\repo" rev-parse HEAD 2>$null
                            if (-not $ghCommit) { $ghCommit = "unknown" }
                            $installTs = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
                            $ghInstalled = 0

                            # Find skills root
                            $ghSkillsRoot = ""
                            foreach ($candidateDir in @(
                                "$ghTmp\repo\source\skills",
                                "$ghTmp\repo\.agents\skills",
                                "$ghTmp\repo\skills",
                                "$ghTmp\repo"
                            )) {
                                if ((Test-Path $candidateDir) -and
                                    (Get-ChildItem -Path $candidateDir -Filter "SKILL.md" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1)) {
                                    $ghSkillsRoot = $candidateDir
                                    break
                                }
                            }

                            if (-not $ghSkillsRoot) {
                                Write-Error ([char]0x2717 + " No SKILL.md found in $ghUrl")
                                exit 1
                            }

                            # Collect top-level skill dirs (skip nested)
                            $allSkillMds = Get-ChildItem -Path $ghSkillsRoot -Filter "SKILL.md" -Recurse -ErrorAction SilentlyContinue |
                                Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' }

                            $ghSkillDirs = @()
                            foreach ($skillMd in $allSkillMds) {
                                $skillDir = $skillMd.DirectoryName
                                $isNested = $false
                                $parentDir = Split-Path $skillDir -Parent
                                while ($parentDir -and $parentDir -ne $ghSkillsRoot -and $parentDir -ne [System.IO.Path]::GetPathRoot($parentDir)) {
                                    if (Test-Path (Join-Path $parentDir "SKILL.md")) {
                                        $isNested = $true
                                        break
                                    }
                                    $parentDir = Split-Path $parentDir -Parent
                                }
                                if (-not $isNested) { $ghSkillDirs += $skillDir }
                            }

                            if ($ghSkillDirs.Count -eq 0) {
                                Write-Error ([char]0x2717 + " No SKILL.md found in $ghUrl")
                                exit 1
                            }

                            # Install each skill
                            foreach ($srcDir in $ghSkillDirs) {
                                $dirName = Split-Path $srcDir -Leaf
                                $skillMdPath = Join-Path $srcDir "SKILL.md"

                                # Read name from frontmatter
                                $metaName = ""
                                $skillContent = Get-Content $skillMdPath -Raw -ErrorAction SilentlyContinue
                                if ($skillContent -match '(?ms)^---\s*\n.*?^name:\s*[''"]?([^''"}\n]+)[''"]?.*?\n---') {
                                    $metaName = $Matches[1].Trim()
                                }

                                $skillName = if ($metaName) { $metaName }
                                             elseif ($ghSkillDirs.Count -eq 1) { $ghRepoName }
                                             else { $dirName }

                                $skillSubdir = if ($agentRole) { "roles\$agentRole\$skillName" } else { "global\$skillName" }

                                $dest1 = Join-Path $OstwinHome ".agents\skills\$skillSubdir"
                                $dest2 = Join-Path $OstwinHome "skills\$skillSubdir"

                                foreach ($dest in @($dest1, $dest2)) {
                                    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
                                    Get-ChildItem $dest -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
                                    Copy-Item -Path "$srcDir\*" -Destination $dest -Recurse -Force

                                    # Write origin.json
                                    $originJson = @{
                                        source       = "github"
                                        url          = $ghUrl
                                        commit       = $ghCommit
                                        agent        = $agentRole
                                        installed_at = $installTs
                                    } | ConvertTo-Json -Depth 3
                                    Set-Content -Path (Join-Path $dest "origin.json") -Value $originJson
                                }

                                Write-Host "  Installed '$skillName' ->"
                                Write-Host "    $($dest1 -replace [regex]::Escape($HOME), '~')"
                                Write-Host "    $($dest2 -replace [regex]::Escape($HOME), '~')"
                                $ghInstalled++

                                # Add to role's skill_refs if --agent
                                if ($agentRole) {
                                    $roleJson = Join-Path $OstwinHome ".agents\roles\$agentRole\role.json"
                                    if (Test-Path $roleJson) {
                                        try {
                                            $roleData = Get-Content $roleJson -Raw | ConvertFrom-Json
                                            $refs = @($roleData.skill_refs)
                                            if ($skillName -notin $refs) {
                                                $refs += $skillName
                                                $roleData.skill_refs = $refs
                                                $roleData | ConvertTo-Json -Depth 10 | Set-Content $roleJson
                                                Write-Host "  Added '$skillName' to $agentRole skill_refs"
                                            }
                                        }
                                        catch { }
                                    }
                                }
                            }

                            Write-Host "  $ghInstalled skill(s) installed from $ghRepoName"

                            # Sync with dashboard if reachable
                            if ((Test-DashboardReachable) -and (Test-Path $syncScript)) {
                                Write-Host "  Syncing with dashboard..."
                                $env:OSTWIN_HOME = $OstwinHome
                                if ($syncScript -match '\.ps1$') {
                                    & pwsh -NoProfile -File $syncScript 2>$null
                                } else {
                                    & bash $syncScript 2>$null
                                }
                            }
                        }
                        finally {
                            if (Test-Path $ghTmp) { Remove-Item $ghTmp -Recurse -Force -ErrorAction SilentlyContinue }
                        }
                        exit 0
                    }

                    # ── ClawHub slug install ──
                    if ($firstArg -notmatch '^[/\\.]' -and -not (Test-Path $firstArg -PathType Container)) {
                        if (Test-Path $clawHubScript) {
                            $env:OSTWIN_HOME = $OstwinHome
                            if ($clawHubScript -match '\.ps1$') {
                                & pwsh -NoProfile -File $clawHubScript install @extraArgs
                            } else {
                                & bash $clawHubScript install @extraArgs
                            }
                            exit $LASTEXITCODE
                        }
                        else {
                            Write-Error ([char]0x2717 + " clawhub-install script not found")
                            exit 1
                        }
                    }
                }

                # Local install: scan cwd for skills
                if (-not $fromDir) {
                    foreach ($candidate in @(
                        (Join-Path $cwd ".agents\skills"),
                        (Join-Path $cwd "skills"),
                        $cwd
                    )) {
                        if ((Test-Path $candidate) -and
                            (Get-ChildItem -Path $candidate -Filter "SKILL.md" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1)) {
                            $fromDir = $candidate
                            break
                        }
                    }
                }
                if (-not $fromDir -or -not (Test-Path $fromDir)) {
                    Write-Error ([char]0x2717 + " No skills found. Specify --from DIR, a ClawHub slug, or run from a project root.")
                    exit 1
                }

                Write-Host "Installing skills from: $fromDir"
                if (-not (Test-Path $syncScript)) {
                    Write-Error ([char]0x2717 + " sync-skills script not found")
                    exit 1
                }
                $env:OSTWIN_HOME = $OstwinHome
                if ($syncScript -match '\.ps1$') {
                    & pwsh -NoProfile -File $syncScript -InstallFrom $fromDir @extraArgs
                } else {
                    & bash $syncScript --install-from $fromDir @extraArgs
                }
            }

            "search" {
                if (Test-Path $clawHubScript) {
                    $env:OSTWIN_HOME = $OstwinHome
                    if ($clawHubScript -match '\.ps1$') {
                        & pwsh -NoProfile -File $clawHubScript search @skillsArgs
                    } else {
                        & bash $clawHubScript search @skillsArgs
                    }
                }
                else {
                    Write-Error ([char]0x2717 + " clawhub-install script not found")
                    exit 1
                }
            }

            "update" {
                if (Test-Path $clawHubScript) {
                    $env:OSTWIN_HOME = $OstwinHome
                    if ($clawHubScript -match '\.ps1$') {
                        & pwsh -NoProfile -File $clawHubScript update @skillsArgs
                    } else {
                        & bash $clawHubScript update @skillsArgs
                    }
                }
                else {
                    Write-Error ([char]0x2717 + " clawhub-install script not found")
                    exit 1
                }
            }

            "remove" {
                if (Test-Path $clawHubScript) {
                    $env:OSTWIN_HOME = $OstwinHome
                    if ($clawHubScript -match '\.ps1$') {
                        & pwsh -NoProfile -File $clawHubScript remove @skillsArgs
                    } else {
                        & bash $clawHubScript remove @skillsArgs
                    }
                }
                else {
                    Write-Error ([char]0x2717 + " clawhub-install script not found")
                    exit 1
                }
            }

            "list" {
                if (-not (Test-DashboardReachable)) {
                    Write-Warning "Dashboard not reachable at $DashboardUrl"
                    exit 1
                }
                try {
                    $skills = Invoke-DashboardApi -Endpoint "/api/skills"
                    if (-not $skills -or $skills.Count -eq 0) {
                        Write-Host "No skills found."
                    }
                    else {
                        foreach ($s in $skills) {
                            $tags = if ($s.tags) { ($s.tags -join ', ') } else { "" }
                            $desc = if ($s.description) { $s.description.Substring(0, [Math]::Min(50, $s.description.Length)) } else { "" }
                            Write-Host ("  {0,-30}  {1,-50}  [{2}]" -f $s.name, $desc, $tags)
                        }
                    }
                }
                catch { Write-Host "Failed to list skills." }
            }

            default {
                Write-Error "Unknown skills subcommand: $skillsSub"
                Write-Host "  Usage: ostwin skills sync"
                Write-Host "         ostwin skills install [<slug>|<github-url>|--from DIR] [--agent <role>]"
                Write-Host "         ostwin skills search <query>"
                Write-Host "         ostwin skills update [--all|<slug>]"
                Write-Host "         ostwin skills remove <slug>"
                Write-Host "         ostwin skills list"
                Write-Host ""
                Write-Host "  Options:"
                Write-Host "    --agent <role>   Install to a specific role (e.g. engineer, qa, architect)"
                Write-Host "                     Without --agent, skills install to global/"
                Write-Host ""
                Write-Host "  Examples:"
                Write-Host "    ostwin skills install https://github.com/user/skill-repo"
                Write-Host "    ostwin skills install https://github.com/user/repo --agent engineer"
                exit 1
            }
        }
    }

    # ── mcp ──────────────────────────────────────────────────────────────────
    "mcp" {
        # Resolve project root by walking up from cwd
        $mcpProjectRoot = ""
        $mcpSearch = $cwd
        while ($mcpSearch -and $mcpSearch -ne [System.IO.Path]::GetPathRoot($mcpSearch)) {
            if (Test-Path (Join-Path $mcpSearch ".agents\mcp") -PathType Container) {
                $mcpProjectRoot = $mcpSearch
                break
            }
            $mcpSearch = Split-Path $mcpSearch -Parent
        }

        $mcpScript = Join-Path $AgentsDir "mcp\mcp-extension.sh"
        if (-not (Test-Path $mcpScript)) {
            Write-Error "[ERROR] mcp-extension.sh not found"
            exit 1
        }

        if ($mcpProjectRoot) {
            & bash $mcpScript --project-dir $mcpProjectRoot @Arguments
        }
        else {
            & bash $mcpScript @Arguments
        }
    }

    # ── reload-env ───────────────────────────────────────────────────────────
    "reload-env" {
        $envFile = Join-Path $OstwinHome ".env"
        if (-not (Test-Path $envFile)) {
            Write-Error ([char]0x2717 + " .env not found at $envFile")
            exit 1
        }

        # Parse .env
        $envVars = @{}
        foreach ($line in Get-Content $envFile) {
            $trimmed = $line.Trim()
            if (-not $trimmed -or $trimmed.StartsWith('#') -or $trimmed -notmatch '=') { continue }
            $eqIdx = $trimmed.IndexOf('=')
            $key = $trimmed.Substring(0, $eqIdx).Trim()
            $val = $trimmed.Substring($eqIdx + 1).Trim().Trim('"').Trim("'")
            if ($key) { $envVars[$key] = $val }
        }

        if ($envVars.Count -eq 0) {
            Write-Host "  No variables found in .env"
            exit 0
        }

        # Collect MCP config files
        $mcpConfigs = @(
            (Join-Path $OstwinHome ".agents\mcp\config.json"),
            (Join-Path $OstwinHome "mcp\config.json"),
            (Join-Path $AgentsDir "mcp\config.json")
        ) | Where-Object { Test-Path $_ } | Sort-Object -Unique

        if ($mcpConfigs.Count -eq 0) {
            Write-Error ([char]0x2717 + " No MCP config found")
            exit 1
        }

        foreach ($mcpConfig in $mcpConfigs) {
            Write-Host "Reloading $envFile -> $mcpConfig ..."
            try {
                $config = Get-Content $mcpConfig -Raw | ConvertFrom-Json

                # Support both 'mcp' and 'mcpServers' keys
                $servers = if ($config.mcp) { $config.mcp } elseif ($config.mcpServers) { $config.mcpServers } else { @{} }

                foreach ($prop in $servers.PSObject.Properties) {
                    $server = $prop.Value
                    if ($server.type -eq 'remote') { continue }

                    # Determine env key name
                    $envKey = if ($server.PSObject.Properties['environment']) { 'environment' }
                              elseif ($server.PSObject.Properties['env']) { 'env' }
                              else { 'environment' }

                    if (-not $server.PSObject.Properties[$envKey]) {
                        $server | Add-Member -NotePropertyName $envKey -NotePropertyValue ([PSCustomObject]@{})
                    }

                    foreach ($kv in $envVars.GetEnumerator()) {
                        $server.$envKey | Add-Member -NotePropertyName $kv.Key -NotePropertyValue $kv.Value -Force
                    }
                }

                $config | ConvertTo-Json -Depth 10 | Set-Content $mcpConfig
                Write-Host "  $([char]0x2713) Injected $($envVars.Count) var(s) into $($servers.PSObject.Properties.Count) MCP server(s)"
                foreach ($name in $servers.PSObject.Properties.Name) {
                    Write-Host "    * $name"
                }
            }
            catch {
                Write-Warning "Failed to update $mcpConfig : $_"
            }
        }
        Write-Host "Done."
    }

    # ── role ─────────────────────────────────────────────────────────────────
    "role" {
        $roleName = if ($Arguments.Count -gt 0) { $Arguments[0] } else { "" }

        if (-not $roleName) {
            # List all roles with subcommands.json
            Write-Host "Available roles with subcommands:"
            Write-Host ""

            foreach ($searchDir in @(
                (Join-Path $AgentsDir "roles"),
                (Join-Path $OstwinHome ".agents\roles")
            )) {
                if (-not (Test-Path $searchDir)) { continue }
                $isGlobal = $searchDir -like "*$OstwinHome*"
                $suffix = if ($isGlobal) { " (global)" } else { "" }

                foreach ($manifest in Get-ChildItem -Path $searchDir -Filter "subcommands.json" -Recurse -Depth 1 -ErrorAction SilentlyContinue) {
                    $rname = $manifest.Directory.Name
                    $desc = ""
                    try {
                        $data = Get-Content $manifest.FullName -Raw | ConvertFrom-Json
                        $cmds = $data.subcommands
                        if ($cmds -is [array]) {
                            $names = $cmds | ForEach-Object { $_.name }
                        }
                        else {
                            $names = $cmds.PSObject.Properties.Name
                        }
                        $desc = "$($names.Count) sub-commands: $($names -join ', ')"
                    }
                    catch { }
                    Write-Host ("  {0,-30} {1}{2}" -f $rname, $desc, $suffix)
                }
            }
            exit 0
        }

        $roleArgs = if ($Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }
        $subName = if ($roleArgs.Count -gt 0) { $roleArgs[0] } else { "" }
        $subArgs = if ($roleArgs.Count -gt 1) { $roleArgs[1..($roleArgs.Count - 1)] } else { @() }

        # Find subcommands.json
        $roleManifest = ""
        foreach ($candidate in @(
            (Join-Path $AgentsDir "roles\$roleName\subcommands.json"),
            (Join-Path $OstwinHome ".agents\roles\$roleName\subcommands.json")
        )) {
            if (Test-Path $candidate) {
                $roleManifest = $candidate
                break
            }
        }

        if (-not $roleManifest) {
            Write-Error ([char]0x2717 + " Role '$roleName' not found or has no subcommands.json")
            Write-Host "  Searched: $(Join-Path $AgentsDir "roles\$roleName")"
            Write-Host "            $(Join-Path $OstwinHome ".agents\roles\$roleName")"
            exit 1
        }

        $roleDir = Split-Path $roleManifest -Parent

        if (-not $subName) {
            # List subcommands
            Write-Host "Subcommands for role '$roleName':"
            Write-Host ""
            try {
                $data = Get-Content $roleManifest -Raw | ConvertFrom-Json
                $cmds = $data.subcommands
                if ($cmds -is [array]) {
                    foreach ($c in $cmds) {
                        $desc = if ($c.description) { $c.description } else { "" }
                        Write-Host ("  {0,-20} {1}" -f $c.name, $desc)
                    }
                }
                else {
                    foreach ($prop in $cmds.PSObject.Properties) {
                        $desc = if ($prop.Value.description) { $prop.Value.description } else { "" }
                        Write-Host ("  {0,-20} {1}" -f $prop.Name, $desc)
                    }
                }
            }
            catch { Write-Error "Failed to parse subcommands.json" }
            exit 0
        }

        # Dispatch the subcommand
        try {
            $data = Get-Content $roleManifest -Raw | ConvertFrom-Json
            $moduleRoot = if ($data.module_root) { $data.module_root } else { "." }
            $cmds = $data.subcommands
            $cmd = $null

            if ($cmds -is [array]) {
                $cmd = $cmds | Where-Object { $_.name -eq $subName } | Select-Object -First 1
            }
            else {
                if ($cmds.PSObject.Properties[$subName]) {
                    $cmd = $cmds.$subName
                }
            }

            if (-not $cmd) {
                Write-Error ([char]0x2717 + " Subcommand '$subName' not found in role '$roleName'")
                exit 1
            }

            $resolvedRoot = Join-Path $roleDir $moduleRoot | Resolve-Path -ErrorAction Stop
            if (-not (Test-Path $resolvedRoot -PathType Container)) {
                Write-Error ([char]0x2717 + " Module root not found: $resolvedRoot")
                exit 1
            }

            # Build invocation: replace {args} with actual arguments
            $invokeTemplate = $cmd.invoke
            $argsStr = $subArgs -join ' '
            $invokeCmd = $invokeTemplate -replace '\{args\}', $argsStr

            Push-Location $resolvedRoot
            try {
                Invoke-Expression $invokeCmd
            }
            finally {
                Pop-Location
            }
        }
        catch {
            Write-Error "Failed to dispatch role command: $_"
            exit 1
        }
    }

    # ── mac ──────────────────────────────────────────────────────────────────
    "mac" {
        # Shorthand for: ostwin role macos-automation-engineer <sub> [args]
        & $PSCommandPath role macos-automation-engineer @Arguments
    }

    # ── config ───────────────────────────────────────────────────────────────
    "config" {
        $configPs1 = Join-Path $AgentsDir "config.ps1"
        $configSh = Join-Path $AgentsDir "config.sh"
        if (Test-Path $configPs1) {
            # Translate bash-style flags to PS params
            $psArgs = [System.Collections.ArrayList]::new()
            $ci = 0
            while ($ci -lt $Arguments.Count) {
                switch ($Arguments[$ci]) {
                    '--get'  { $null = $psArgs.Add('-Get'); $ci++; $null = $psArgs.Add($Arguments[$ci]); $ci++ }
                    '--set'  { $null = $psArgs.Add('-Set'); $ci++; $null = $psArgs.Add($Arguments[$ci]); $ci++; $null = $psArgs.Add('-Value'); $null = $psArgs.Add($Arguments[$ci]); $ci++ }
                    { $_ -in @('-h', '--help') } { $null = $psArgs.Add('-Help'); $ci++ }
                    default  { $null = $psArgs.Add($Arguments[$ci]); $ci++ }
                }
            }
            & pwsh -NoProfile -File $configPs1 @psArgs
        }
        elseif ((Test-Path $configSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            & bash $configSh @Arguments
        }
        else {
            Write-Error "[ERROR] Neither config.ps1 nor config.sh found."
            exit 1
        }
    }

    # ── health ───────────────────────────────────────────────────────────────
    "health" {
        $healthPs1 = Join-Path $AgentsDir "health.ps1"
        $healthSh = Join-Path $AgentsDir "health.sh"
        if (Test-Path $healthPs1) {
            $psArgs = [System.Collections.ArrayList]::new()
            foreach ($a in $Arguments) {
                if ($a -eq '--json') { $null = $psArgs.Add('-JsonOutput') }
                else { $null = $psArgs.Add($a) }
            }
            & pwsh -NoProfile -File $healthPs1 @psArgs
        }
        elseif ((Test-Path $healthSh) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
            & bash $healthSh @Arguments
        }
        else {
            Write-Error "[ERROR] Neither health.ps1 nor health.sh found."
            exit 1
        }
    }

    # ── test ─────────────────────────────────────────────────────────────────
    "test" {
        $testScript = Join-Path $AgentsDir "tests\run-all.sh"
        if (Test-Path $testScript) {
            & bash $testScript @Arguments
        }
        else {
            Write-Error "[ERROR] run-all.sh not found at $testScript"
            exit 1
        }
    }

    # ── test-ps ──────────────────────────────────────────────────────────────
    "test-ps" {
        if (Get-Command pwsh -ErrorAction SilentlyContinue) {
            & pwsh -NoProfile -Command @"
Invoke-Pester '$AgentsDir\lib','$AgentsDir\channel','$AgentsDir\war-rooms','$AgentsDir\roles','$AgentsDir\plan' -Output Detailed
"@
        }
        else {
            Write-Error "[ERROR] pwsh (PowerShell) not found. Install: https://aka.ms/install-powershell"
            exit 1
        }
    }

    # ── version ──────────────────────────────────────────────────────────────
    { $_ -in @('version', '-v', '--version') } {
        if ($BuildHash) {
            Write-Host "ostwin v${Version} (${BuildHash})"
        }
        else {
            Write-Host "ostwin v${Version}"
        }
    }

    # ── help ─────────────────────────────────────────────────────────────────
    { $_ -in @('-h', '--help', 'help', '') } {
        Show-OstwinHelp
    }

    # ── unknown ──────────────────────────────────────────────────────────────
    default {
        if (-not $Command) {
            Show-OstwinHelp
        }
        else {
            Write-Error "Unknown command: $Command"
            Write-Host "Run 'ostwin --help' for usage."
            exit 1
        }
    }
}
