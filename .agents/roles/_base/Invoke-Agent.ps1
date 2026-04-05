<#
.SYNOPSIS
    Universal agent launcher — wraps deepagents CLI for any role.

.DESCRIPTION
    Provides a common interface for launching deepagents with role-specific
    prompts, config, PID tracking, timeout, and output capture.
    Used by Start-Engineer.ps1, Start-QA.ps1, and future role runners.

    New in v0.2 — replaces role-specific bash wrappers with a single reusable launcher.

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER RoleName
    Role identifier (engineer, qa, architect, etc.).
.PARAMETER Prompt
    Full prompt text to send to deepagents.
.PARAMETER Model
    Model to use. Default from config.
.PARAMETER TimeoutSeconds
    Max execution time. Default from config.
.PARAMETER AgentCmd
    Override CLI command (for testing with mocks). Default: deepagents.
.PARAMETER AutoApprove
    Auto-approve tool usage. Default: true.
.PARAMETER Quiet
    Always $true — agents always run in quiet mode (-q flag).
.PARAMETER McpConfig
    Path to the MCP config JSON. Defaults to <AGENTS_DIR>/mcp/mcp-config.json.
    Pass empty string to disable MCP tool injection.
.PARAMETER ExtraArgs
    Additional CLI arguments as string array.

.OUTPUTS
    PSCustomObject with ExitCode, Output, OutputFile, PidFile properties.

.EXAMPLE
    $result = ./Invoke-Agent.ps1 -RoomDir "./war-rooms/room-001" -RoleName "engineer" `
                                  -Prompt "Implement auth" -TimeoutSeconds 600
    if ($result.ExitCode -eq 0) { Write-Host "Success" }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [Parameter(Mandatory)]
    [string]$RoleName,

    [Parameter(Mandatory)]
    [string]$Prompt,

    [string]$Model = '',
    [int]$TimeoutSeconds = 600,
    [string]$AgentCmd = '',
    [bool]$AutoApprove = $true,
    [string]$InstanceId = '',
    [string]$WorkingDir = '',
    [string]$McpConfig = '',
    [string[]]$ExtraArgs = @()
)

# --- Always run agents in quiet mode ---
$Quiet = $true

# --- Resolve paths ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path

# Resolve OSTWIN_HOME: env var → ~/.ostwin
$homeDir = if ($env:HOME) {
    $env:HOME
}
elseif ($env:USERPROFILE) {
    $env:USERPROFILE
}
else {
    [System.Environment]::GetFolderPath('UserProfile')
}
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $homeDir ".ostwin" }

# Ensure RoomDir is absolute for bash wrapper consistency (EPIC-002)
# Using GetUnresolvedProviderPathFromPSPath to handle non-existent paths (unlikely but safe)
$absRoomDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RoomDir)

function Convert-ToBashPath {
    param([string]$Path)

    if (-not $Path) { return $Path }

    $candidate = $Path.Trim()
    if ($candidate.Length -ge 2 -and (
        ($candidate.StartsWith("'") -and $candidate.EndsWith("'")) -or
        ($candidate.StartsWith('"') -and $candidate.EndsWith('"'))
    )) {
        $candidate = $candidate.Substring(1, $candidate.Length - 2)
    }

    if ($candidate -match '^[A-Za-z]:[\\/]') {
        $drive = $candidate.Substring(0, 1).ToLower()
        $rest = $candidate.Substring(2).Replace('\', '/')
        if ($rest.StartsWith('/')) { $rest = $rest.Substring(1) }
        return "/mnt/$drive/$rest"
    }

    return $candidate.Replace('\', '/')
}

function Convert-ToBashCommand {
    param([string]$Command)

    if (-not $Command) { return $Command }

    $candidate = $Command.Trim()
    if ($candidate.Length -ge 2 -and (
        ($candidate.StartsWith("'") -and $candidate.EndsWith("'")) -or
        ($candidate.StartsWith('"') -and $candidate.EndsWith('"'))
    )) {
        $candidate = $candidate.Substring(1, $candidate.Length - 2)
    }

    try {
        if (Test-Path -LiteralPath $candidate) {
            $candidate = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
        }
    } catch { }

    if ($candidate -match '^[A-Za-z]:[\\/]' -or $candidate -match '^/') {
        $safe = (Convert-ToBashPath $candidate) -replace "'", "'\''"
        return "'$safe'"
    }

    return $Command
}

function New-LocalMcpConfig {
    param(
        [string]$ProjectDir,
        [string]$AgentsDir,
        [string]$OstwinHome
    )

    $mcpAgentsRoot = Join-Path $OstwinHome ".agents"
    $channelServer = Join-Path $mcpAgentsRoot "mcp" "channel-server.py"
    if (-not (Test-Path $channelServer)) {
        $mcpAgentsRoot = $AgentsDir
        $channelServer = Join-Path $mcpAgentsRoot "mcp" "channel-server.py"
    }

    $mcpPython = if ($env:OSTWIN_PYTHON) {
        $env:OSTWIN_PYTHON
    }
    else {
        Join-Path (Join-Path $OstwinHome ".venv") "bin/python"
    }

    $rootValue = if ($ProjectDir) { Convert-ToBashPath $ProjectDir } else { "." }
    $serverNames = @("channel", "warroom", "memory")
    $servers = [ordered]@{}
    foreach ($serverName in $serverNames) {
        $serverPath = Join-Path $mcpAgentsRoot "mcp" "$serverName-server.py"
        if (-not (Test-Path $serverPath)) { continue }

        $servers[$serverName] = [ordered]@{
            command = (Convert-ToBashPath $mcpPython)
            args    = @((Convert-ToBashPath $serverPath))
            env     = [ordered]@{
                AGENT_OS_ROOT = $rootValue
            }
        }
    }

    return [ordered]@{
        mcpServers = $servers
    }
}

# --- Load config ---
$configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
              else { Join-Path $agentsDir "config.json" }

# --- Load plan-specific roles config from room's config.json → plan_id ---
$planRolesConfig = $null
$roomConfigFile = Join-Path $absRoomDir "config.json"
if (Test-Path $roomConfigFile) {
    try {
        $roomCfg = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
        $roomPlanId = $roomCfg.plan_id
        if ($roomPlanId) {
            $planRolesFile = Join-Path $env:HOME ".ostwin" "plans" "$roomPlanId.roles.json"
            if (Test-Path $planRolesFile) {
                $planRolesConfig = Get-Content $planRolesFile -Raw | ConvertFrom-Json
            }
        }
    } catch { }
}

# Safe defaults (overridden inside config block below)
$NoMcp = $false
$ProjectDir = ""

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json

    # --- Instance-aware config resolution ---
    $instanceConfig = $null
    if ($InstanceId -and $config.$RoleName.instances.$InstanceId) {
        $instanceConfig = $config.$RoleName.instances.$InstanceId
    }

    # Model: plan roles.json → instance → role config.json → role.json → hardcoded default
    if (-not $Model) {
        # Priority 1: plan-specific roles.json
        if ($planRolesConfig -and $planRolesConfig.$RoleName -and $planRolesConfig.$RoleName.default_model) {
            $Model = $planRolesConfig.$RoleName.default_model
        }
        elseif ($instanceConfig -and $instanceConfig.default_model) {
            $Model = $instanceConfig.default_model
        }
        elseif ($config.$RoleName.default_model) {
            $Model = $config.$RoleName.default_model
        }
        else {
            # Try role.json as last config-based source
            $roleJsonPath = Join-Path $agentsDir "roles" $RoleName "role.json"
            if (Test-Path $roleJsonPath) {
                $roleJson = Get-Content $roleJsonPath -Raw | ConvertFrom-Json
                if ($roleJson.model) {
                    $Model = $roleJson.model
                }
            }
        }
    }

    # Timeout: plan roles.json → instance → role
    if ($TimeoutSeconds -eq 600) {
        if ($planRolesConfig -and $planRolesConfig.$RoleName -and $planRolesConfig.$RoleName.timeout_seconds) {
            $TimeoutSeconds = $planRolesConfig.$RoleName.timeout_seconds
        }
        elseif ($instanceConfig -and $instanceConfig.timeout_seconds) {
            $TimeoutSeconds = $instanceConfig.timeout_seconds
        }
        elseif ($config.$RoleName.timeout_seconds) {
            $TimeoutSeconds = $config.$RoleName.timeout_seconds
        }
    }

    # WorkingDir: instance → parameter
    if (-not $WorkingDir -and $instanceConfig -and $instanceConfig.working_dir) {
        $WorkingDir = $instanceConfig.working_dir
    }

    # no_mcp: instance → role → default false
    # MCP is enabled by default — pass --mcp-config from the project dir.
    # Set no_mcp: true in config.json for a role to disable MCP (e.g. unstable remote exec).
    $NoMcp = $false
    if ($instanceConfig -and $instanceConfig.PSObject.Properties['no_mcp']) {
        $NoMcp = [bool]$instanceConfig.no_mcp
    }
    elseif ($config.$RoleName -and $config.$RoleName.PSObject.Properties['no_mcp']) {
        $NoMcp = [bool]$config.$RoleName.no_mcp
    }

    # --- Resolve ProjectDir from RoomDir (parent of .war-rooms) ---
    # War-room paths follow: $PROJECT/.war-rooms/<plan>/<room>/
    # Walk up from RoomDir to find the directory containing .war-rooms
    $ProjectDir = ""
    $searchDir = $absRoomDir
    for ($i = 0; $i -lt 6; $i++) {
        $parentDir = Split-Path $searchDir -Parent
        if (-not $parentDir -or $parentDir -eq $searchDir) { break }
        if ((Split-Path $searchDir -Leaf) -eq ".war-rooms") {
            $ProjectDir = $parentDir
            break
        }
        $searchDir = $parentDir
    }
    # Fallback: env variable or WorkingDir
    if (-not $ProjectDir -and $env:PROJECT_DIR) { $ProjectDir = $env:PROJECT_DIR }
    if (-not $ProjectDir -and $WorkingDir) { $ProjectDir = $WorkingDir }

    # --- CLI resolution: local wrapper → role config → global fallback ---
    if (-not $AgentCmd) {
        $localAgent = Join-Path $agentsDir "bin" "agent"
        if (Test-Path $localAgent) {
            $AgentCmd = "'$localAgent'"
        }
        else {
            $AgentCmd = $config.$RoleName.cli
            if ($AgentCmd -eq "agent" -or $AgentCmd -eq "cli" -or (-not $AgentCmd)) { $AgentCmd = "deepagents" }
        }
    }
}

if (-not $AgentCmd) { $AgentCmd = "deepagents" }
if (-not $Model) { $Model = "gemini-3-flash-preview" }

# --- Env var overrides for testing ---
$envCmdVar = "${RoleName}_CMD".ToUpper()
$envCmd = [System.Environment]::GetEnvironmentVariable($envCmdVar)
if ($envCmd) { $AgentCmd = $envCmd }

# --- Prepare output directory ---
$artifactsDir = Join-Path $absRoomDir "artifacts"
$pidsDir = Join-Path $absRoomDir "pids"
New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
New-Item -ItemType Directory -Path $pidsDir -Force | Out-Null

# --- Skill Isolation (EPIC-002) ---
$isolatedSkillsDir = Join-Path $absRoomDir "skills"

# Ensure isolated skills dir exists without wiping existing API-matched skills
if (-not (Test-Path $isolatedSkillsDir)) {
    New-Item -ItemType Directory -Path $isolatedSkillsDir -Force | Out-Null
}

$rolePath = Join-Path $agentsDir "roles" $RoleName
$resolveSkillsScript = Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1"

if (Test-Path $resolveSkillsScript) {
    try {
        $skills = & $resolveSkillsScript -RoleName $RoleName -RolePath $rolePath -ErrorAction Stop
        foreach ($skill in $skills) {
            if ($skill.Path -and (Test-Path $skill.Path)) {
                # Copy the entire skill directory content to the isolated location
                $skillSrcDir = Split-Path $skill.Path -Parent
                $skillName = Split-Path $skillSrcDir -Leaf
                $destPath = Join-Path $isolatedSkillsDir $skillName
                
                # Ensure the destination skill directory exists and is clean
                if (Test-Path $destPath) {
                    Remove-Item -Path $destPath -Recurse -Force -ErrorAction SilentlyContinue
                }
                New-Item -ItemType Directory -Path $destPath -Force | Out-Null
                
                # Copy contents specifically to avoid nested directory issues
                Copy-Item -Path (Join-Path $skillSrcDir "*") -Destination $destPath -Recurse -Force -ErrorAction SilentlyContinue
            }
            else {
                Write-Warning "Skill source path not found for '$($skill.Name)': $($skill.Path)"
            }
        }
    }
    catch {
        Write-Warning "Failed to resolve or copy skills: $($_.Exception.Message)"
    }
}


$outputFile = Join-Path $artifactsDir "$RoleName-output.txt"
$pidFile = Join-Path $pidsDir "$RoleName.pid"

# --- PID is written by bin/agent via AGENT_OS_PID_FILE env var ---
# No premature PID write here. The agent process self-registers after startup.



# --- Execute with timeout and transient-error retry ---
$maxProcessRetries = 3
$exitCode = 0

$stdinNull = if ($IsLinux -or $IsMacOS) { "/dev/null" }
             else { "NUL" }

# Write prompt to a file to avoid shell escaping issues
$promptFile = Join-Path $artifactsDir "prompt.txt"
$Prompt | Out-File -FilePath $promptFile -Encoding utf8 -NoNewline -Force

# --- Debug: write a human-readable copy of the compiled prompt ---
$debugPromptFile = Join-Path $artifactsDir "$RoleName-prompt-debug.md"
$Prompt | Out-File -FilePath $debugPromptFile -Encoding utf8 -Force

# Build non-prompt CLI args safely
$extraCliArgs = @()
if ($RoleName) { $extraCliArgs += "--agent"; $extraCliArgs += $RoleName }
if ($AutoApprove) { $extraCliArgs += "--auto-approve" }
if ($Model) { $extraCliArgs += "--model"; $extraCliArgs += $Model }
if ($RoleName -eq 'engineer') { $extraCliArgs += "--shell-allow-list"; $extraCliArgs += "all" }
if ($Quiet) { $extraCliArgs += "--quiet" }

# Allow callers to explicitly suppress MCP by passing --no-mcp in ExtraArgs.
if ($ExtraArgs -contains "--no-mcp") {
    $NoMcp = $true
}

# --- MCP config: prefer project-local, fall back to global ---
# If no_mcp is set in role config, skip MCP entirely to avoid ClosedResourceError
# on remote LangGraph execution. Role scripts handle channel communication instead.
if ($NoMcp) {
    $extraCliArgs += "--no-mcp"
}
else {
    $resolvedMcpConfig = $McpConfig
    if (-not $resolvedMcpConfig) {
        # Priority 1: project-local MCP config ($ProjectDir/.agents/mcp/mcp-config.json)
        if ($ProjectDir) {
            $projectMcpConfig = Join-Path $ProjectDir ".agents" "mcp" "mcp-config.json"
            if (Test-Path $projectMcpConfig) {
                $resolvedMcpConfig = $projectMcpConfig
            }
        }
        # Priority 2: agents dir (same repo, e.g. installed copy)
        if (-not $resolvedMcpConfig) {
            $agentsDirMcpConfig = Join-Path $agentsDir "mcp" "mcp-config.json"
            if (Test-Path $agentsDirMcpConfig) {
                $resolvedMcpConfig = $agentsDirMcpConfig
            }
        }
        # Priority 3: OSTWIN_HOME global config (~/.ostwin/mcp/mcp-config.json)
        if (-not $resolvedMcpConfig) {
            $ostwinMcpConfig = Join-Path $OstwinHome "mcp" "mcp-config.json"
            if (Test-Path $ostwinMcpConfig) {
                $resolvedMcpConfig = $ostwinMcpConfig
            }
        }
    }
    if ($resolvedMcpConfig -and (Test-Path $resolvedMcpConfig)) {
        if (-not $McpConfig) {
            $tempMcpConfig = Join-Path $artifactsDir "mcp-config-resolved.json"
            $localMcpConfig = New-LocalMcpConfig -ProjectDir $ProjectDir -AgentsDir $agentsDir -OstwinHome $OstwinHome
            $localMcpConfig | ConvertTo-Json -Depth 10 | Out-File -FilePath $tempMcpConfig -Encoding utf8 -NoNewline -Force
            $resolvedMcpConfig = $tempMcpConfig
        }
        else {
            $mcpConfigContent = Get-Content $resolvedMcpConfig -Raw
            # Expand ${AGENT_DIR} → absolute agentsDir
            if ($mcpConfigContent -match '\$\{AGENT_DIR\}') {
                $mcpConfigContent = $mcpConfigContent -replace '\$\{AGENT_DIR\}', (Convert-ToBashPath $agentsDir)
            }
            # Expand ${PROJECT_DIR} → absolute project dir
            if ($ProjectDir -and ($mcpConfigContent -match '\$\{PROJECT_DIR\}')) {
                $mcpConfigContent = $mcpConfigContent -replace '\$\{PROJECT_DIR\}', (Convert-ToBashPath $ProjectDir)
            }
            # Write resolved config if any placeholders were expanded
            if ($mcpConfigContent -ne (Get-Content $resolvedMcpConfig -Raw)) {
                $tempMcpConfig = Join-Path $artifactsDir "mcp-config-resolved.json"
                $mcpConfigContent | Out-File -FilePath $tempMcpConfig -Encoding utf8 -NoNewline -Force
                $resolvedMcpConfig = $tempMcpConfig
            }
        }
        $extraCliArgs += "--mcp-config"
        $extraCliArgs += (Convert-ToBashPath (Resolve-Path $resolvedMcpConfig).Path)
    }
}

$extraCliArgs += $ExtraArgs

$argsLine = ($extraCliArgs | ForEach-Object {
    if ($_ -match '[\s"]') { "'$($_ -replace "'", "'\''")'" } else { $_ }
}) -join ' '

for ($processAttempt = 1; $processAttempt -le $maxProcessRetries; $processAttempt++) {
    $exitCode = 0
    try {
        # Write wrapper script
        $wrapperScript = Join-Path $artifactsDir "run-agent.sh"
        $safeOutput = (Convert-ToBashPath $outputFile) -replace "'", "'\''"
        $safePrompt = (Convert-ToBashPath $promptFile) -replace "'", "'\''"
        $safeCwd = if ($WorkingDir) { (Convert-ToBashPath $WorkingDir) -replace "'", "'\''" } else { "" }
        $safeRoomDir = (Convert-ToBashPath $absRoomDir) -replace "'", "'\''"
        $safeSkillsDir = (Convert-ToBashPath $isolatedSkillsDir) -replace "'", "'\''"
        $safeRole = $RoleName -replace "'", "'\''"

        $cwdLine = if ($safeCwd) { "cd '$safeCwd' 2>/dev/null || true" } else { "" }
        $safePidFile = (Convert-ToBashPath $pidFile) -replace "'", "'\''"
        $safeOstwinHome = (Convert-ToBashPath $OstwinHome) -replace "'", "'\''"
        $safeProjectDir = if ($ProjectDir) { (Convert-ToBashPath $ProjectDir) -replace "'", "'\''"} else { "" }
        $safeAgentCmd = Convert-ToBashCommand $AgentCmd
        $scriptContent = @"
#!/bin/bash
export AGENT_OS_ROOM_DIR='$safeRoomDir'
export AGENT_OS_ROLE='$safeRole'
export AGENT_OS_PARENT_PID='$PID'
export AGENT_OS_SKILLS_DIR='$safeSkillsDir'
export AGENT_OS_PID_FILE='$safePidFile'
export OSTWIN_HOME='$safeOstwinHome'
export AGENT_OS_PROJECT_DIR='$safeProjectDir'
$cwdLine
# Write PID before exec — `$`$ survives exec, so this is the real agent PID.
# bin/agent also writes this (harmless overwrite); this fallback ensures
# non-bin/agent commands (deepagents, custom CLIs) still get tracked.
echo "`$$" > '$safePidFile'
# Log diagnostic info before exec
echo "[wrapper] PID=`$$, CMD=$safeAgentCmd, CWD=`$(pwd)" >> '$safeOutput'
exec $safeAgentCmd -n "`$(cat '$safePrompt')" $argsLine >> '$safeOutput' 2>&1
# If exec fails, this line runs:
echo "[wrapper] EXEC FAILED: exit=`$?" >> '$safeOutput'
"@
        $scriptContent | Out-File -FilePath $wrapperScript -Encoding utf8 -NoNewline -Force
        if (Get-Command chmod -ErrorAction SilentlyContinue) {
            chmod +x $wrapperScript 2>$null
        }

        # --- Launch bash via System.Diagnostics.Process ---
        # Start-Process -NoNewWindow is unreliable inside Start-Job on macOS
        # (no console to attach to in headless runspace). Direct Process API works.
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = "bash"
        $bashWrapperScript = Convert-ToBashPath $wrapperScript
        $psi.Arguments = "`"$bashWrapperScript`""
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        $proc.StandardInput.Close()  # equivalent to /dev/null stdin

        Write-Warning "[Invoke-Agent] bash launched as PID $($proc.Id), HasExited=$($proc.HasExited), wrapper=$wrapperScript"

        # --- Wait for agent to self-register its PID (max 15s) ---
        # The wrapper writes $$ to the PID file before exec, and bin/agent
        # also writes it. We poll until we see a valid, alive PID.
        $pidConfirmTimeout = 15
        $pidConfirmStart = [int][double]::Parse((Get-Date -UFormat %s))
        $confirmedPid = $null
        while (([int][double]::Parse((Get-Date -UFormat %s)) - $pidConfirmStart) -lt $pidConfirmTimeout) {
            if ($proc.HasExited) {
                # Process already done — do one final PID file read before giving up.
                # The wrapper writes PID before exec, so the file may exist even if
                # the process exited quickly (fast completion or exec failure).
                if (Test-Path $pidFile) {
                    $pidContent = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
                    if ($pidContent -and ($pidContent.Trim() -match '^\d+$')) {
                        $confirmedPid = [int]$pidContent.Trim()
                    }
                }
                break
            }
            if (Test-Path $pidFile) {
                $pidContent = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
                if ($pidContent -and ($pidContent.Trim() -match '^\d+$')) {
                    $candidatePid = [int]$pidContent.Trim()
                    # Verify it's actually alive and not our own PowerShell PID
                    if ($candidatePid -ne $PID) {
                        try {
                            $p = Get-Process -Id $candidatePid -ErrorAction Stop
                            if ($p) { $confirmedPid = $candidatePid; break }
                        } catch { }
                    }
                }
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $confirmedPid -and -not $proc.HasExited) {
            Write-Warning "[Invoke-Agent] PID confirmation timed out after ${pidConfirmTimeout}s for '$RoleName'. Falling back to proc.Id ($($proc.Id)). Agent may not be tracked correctly."
        }
        Write-Warning "[Invoke-Agent] PID confirmation result: confirmedPid=$confirmedPid procId=$($proc.Id) procHasExited=$($proc.HasExited)"

        $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
        if (-not $proc.HasExited) {
            # Timeout — kill the confirmed agent PID if available, else fall back to proc.Id
            $killPid = if ($confirmedPid) { $confirmedPid } else { $proc.Id }
            Stop-Process -Id $killPid -Force -ErrorAction SilentlyContinue
            # Also kill proc.Id in case they differ (belt-and-suspenders)
            if ($confirmedPid -and $confirmedPid -ne $proc.Id) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
            $exitCode = 124
            "Agent timed out after ${TimeoutSeconds}s" | Out-File -FilePath $outputFile -Encoding utf8 -Append
        }
        else {
            $exitCode = $proc.ExitCode
        }

        # --- Diagnostic: log output on failure ---
        if ($exitCode -ne 0 -and (Test-Path $outputFile)) {
            $firstLines = Get-Content $outputFile -TotalCount 5 -ErrorAction SilentlyContinue
            if ($firstLines) {
                Write-Warning "[Invoke-Agent] Agent exited with code $exitCode. First output lines: $($firstLines -join ' | ')"
            }
        }
    }
    catch {
        $exitCode = 1
        $_.Exception.Message | Out-File -FilePath $outputFile -Encoding utf8
    }

    # --- Retry on transient remote errors (ClosedResourceError, RemoteException) ---
    if ($exitCode -ne 0 -and $exitCode -ne 124 -and $processAttempt -lt $maxProcessRetries) {
        $agentOutput = if (Test-Path $outputFile) { Get-Content $outputFile -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($agentOutput -match "ClosedResourceError|RemoteException.*ClosedResource|ReadError|WriteError") {
            $backoff = [math]::Pow(2, $processAttempt)
            Write-Host "[Invoke-Agent] Transient remote error on attempt $processAttempt/$maxProcessRetries, retrying in ${backoff}s..."
            Start-Sleep -Seconds $backoff
            continue
        }
    }
    break  # Success or non-transient error — stop retrying
}

# --- Read output ---
$output = if (Test-Path $outputFile) {
    Get-Content $outputFile -Raw -ErrorAction SilentlyContinue
}
else { "No output captured" }

    # --- Clean up temp files (OPT-003: prevent accumulation on retries) ---
    Remove-Item $wrapperScript -Force -ErrorAction SilentlyContinue
    Remove-Item $promptFile -Force -ErrorAction SilentlyContinue
# Remove resolved MCP config copy if one was generated
if ($tempMcpConfig -and (Test-Path $tempMcpConfig)) {
    Remove-Item $tempMcpConfig -Force -ErrorAction SilentlyContinue
}

# Note: PID file is NOT removed here. The caller (Start-Engineer/Start-QA)
# must clean it up after posting the channel message, to avoid race conditions
# with the manager's deadlock detection.

# --- Return result ---
[PSCustomObject]@{
    ExitCode   = $exitCode
    Output     = $output
    OutputFile = $outputFile
    PidFile    = $pidFile
    RoleName   = $RoleName
    TimedOut   = ($exitCode -eq 124)
}
