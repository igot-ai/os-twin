<#
.SYNOPSIS
    Universal agent launcher — wraps opencode run for any role.

.DESCRIPTION
    Provides a common interface for launching opencode run with role-specific
    prompts, config, PID tracking, timeout, and output capture.
    Used by Start-Engineer.ps1, Start-QA.ps1, and future role runners.

    v0.3 — migrated from deepagents CLI to opencode run.

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER RoleName
    Role identifier (engineer, qa, architect, etc.). Passed as --agent.
.PARAMETER Prompt
    Full prompt text. Passed as a positional argument to opencode run.
.PARAMETER Model
    Model to use (provider/model format). Passed as --model / -m.
.PARAMETER TimeoutSeconds
    Max execution time. Default from config.
.PARAMETER AgentCmd
    Override CLI command (for testing with mocks). Default: opencode run.
.PARAMETER McpConfig
    Path to the MCP config JSON. Used to generate an opencode.json config
    in the artifacts dir. Pass empty string to disable MCP tool injection.
.PARAMETER Format
    Output format: 'default' (formatted) or 'json' (raw JSON events).
.PARAMETER Files
    File(s) to attach to the message. Each is passed as --file.
.PARAMETER SessionTitle
    Title for the session. Passed as --title.
.PARAMETER SessionId
    Session ID to continue. Passed as --session / -s.
.PARAMETER ContinueSession
    Continue the last session. Passed as --continue / -c.
.PARAMETER ForkSession
    Fork the session when continuing. Passed as --fork.
.PARAMETER ShareSession
    Share the session. Passed as --share.
.PARAMETER Command
    Command to run, use message for args. Passed as --command.
.PARAMETER AttachUrl
    Attach to a running opencode server. Passed as --attach.
.PARAMETER Port
    Port for the local server. Passed as --port.
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
    [string]$InstanceId = '',
    [string]$WorkingDir = '',
    [string]$McpConfig = '',
    [string]$Format = '',
    [string[]]$Files = @(),
    [string]$SessionTitle = '',
    [string]$SessionId = '',
    [switch]$ContinueSession,
    [switch]$ForkSession,
    [switch]$ShareSession,
    [string]$Command = '',
    [string]$AttachUrl = '',
    [int]$Port = 0,
    [string[]]$ExtraArgs = @()
)

# --- Resolve paths ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path

# Resolve OSTWIN_HOME: env var → ~/.ostwin
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $env:HOME ".ostwin" }

# Ensure RoomDir is absolute for bash wrapper consistency (EPIC-002)
# Using GetUnresolvedProviderPathFromPSPath to handle non-existent paths (unlikely but safe)
$absRoomDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RoomDir)

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
            $planRolesFile = Join-Path $OstwinHome ".agents" "plans" "$roomPlanId.roles.json"
            if (Test-Path $planRolesFile) {
                $planRolesConfig = Get-Content $planRolesFile -Raw | ConvertFrom-Json
            }
        }
    }
    catch { }
}

# --- Plan roles resolution (highest priority after explicit -Model) ---
# Runs unconditionally — does NOT depend on .agents/config.json existing.
# Schema: { "<role>": { "default_model": "...", "timeout_seconds": N,
#                       "instances": { "<id>": { "default_model": "...", "timeout_seconds": N } } } }
$timeoutWasExplicit = $PSBoundParameters.ContainsKey('TimeoutSeconds')

if ($planRolesConfig -and $planRolesConfig.$RoleName) {
    $planRoleNode = $planRolesConfig.$RoleName

    if (-not $Model) {
        # Priority 1a: plan-roles instance override
        if ($InstanceId -and $planRoleNode.instances `
            -and $planRoleNode.instances.$InstanceId `
            -and $planRoleNode.instances.$InstanceId.default_model) {
            $Model = $planRoleNode.instances.$InstanceId.default_model
        }
        # Priority 1b: plan-roles role default
        elseif ($planRoleNode.default_model) {
            $Model = $planRoleNode.default_model
        }
    }

    if (-not $timeoutWasExplicit) {
        if ($InstanceId -and $planRoleNode.instances `
            -and $planRoleNode.instances.$InstanceId `
            -and $planRoleNode.instances.$InstanceId.timeout_seconds) {
            $TimeoutSeconds = [int]$planRoleNode.instances.$InstanceId.timeout_seconds
        }
        elseif ($planRoleNode.timeout_seconds) {
            $TimeoutSeconds = [int]$planRoleNode.timeout_seconds
        }
    }
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

    # Model fallback chain (plan roles already applied above):
    # instance → role config.json → role.json → hardcoded default
    if (-not $Model) {
        if ($instanceConfig -and $instanceConfig.default_model) {
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

    # Timeout fallback chain (plan roles already applied above): instance → role
    if (-not $timeoutWasExplicit) {
        if ($instanceConfig -and $instanceConfig.timeout_seconds) {
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

    # --- CLI resolution: OSTWIN_HOME bin/agent → role config → opencode fallback ---
    # ALWAYS resolve to $OstwinHome/.agents/bin/agent (canonical install).
    # Never the project-local $agentsDir/bin/agent (dev tree) — those can drift.
    if (-not $AgentCmd) {
        $ostwinAgent = Join-Path $OstwinHome ".agents" "bin" "agent"
        if (Test-Path $ostwinAgent) {
            $AgentCmd = "'$ostwinAgent'"
        }
        else {
            $AgentCmd = $config.$RoleName.cli
            if ($AgentCmd -eq "agent" -or $AgentCmd -eq "cli" -or $AgentCmd -eq "deepagents" -or (-not $AgentCmd)) { $AgentCmd = "opencode run" }
        }
    }
}

if (-not $AgentCmd) { $AgentCmd = "opencode run" }
if (-not $Model) { $Model = "google-vertex/zai-org/glm-5-maas" }

# --- Env var overrides for testing ---
$envCmdVar = "${RoleName}_CMD".ToUpper()
$envCmd = [System.Environment]::GetEnvironmentVariable($envCmdVar)
if ($envCmd) { $AgentCmd = $envCmd }

# --- Log resolved model/timeout for debugging ---
# This is the value that will actually drive opencode run.
Write-Host "[Invoke-Agent] Resolved Role=$RoleName Instance=$InstanceId Model=$Model Timeout=${TimeoutSeconds}s"

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
# Resolve to absolute path for -f flag
$promptFileAbsolute = (Resolve-Path $promptFile).Path

# --- Debug: write a human-readable copy of the compiled prompt ---
$debugPromptFile = Join-Path $artifactsDir "$RoleName-prompt-debug.md"
$Prompt | Out-File -FilePath $debugPromptFile -Encoding utf8 -Force

# Build non-prompt CLI args safely (opencode run flags)
# Prompt is passed as --file <path> to avoid ARG_MAX limits with large prompts
$extraCliArgs = @()
if ($Model) { $extraCliArgs += "--model"; $extraCliArgs += $Model }
if ($RoleName) { $extraCliArgs += "--agent"; $extraCliArgs += $RoleName }
if ($Format) { $extraCliArgs += "--format"; $extraCliArgs += $Format }
if ($SessionTitle) { $extraCliArgs += "--title"; $extraCliArgs += $SessionTitle }
if ($SessionId) { $extraCliArgs += "--session"; $extraCliArgs += $SessionId }
if ($ContinueSession) { $extraCliArgs += "--continue" }
if ($ForkSession) { $extraCliArgs += "--fork" }
if ($ShareSession) { $extraCliArgs += "--share" }
if ($Command) { $extraCliArgs += "--command"; $extraCliArgs += $Command }
if ($AttachUrl) { $extraCliArgs += "--attach"; $extraCliArgs += $AttachUrl }
if ($Port -gt 0) { $extraCliArgs += "--port"; $extraCliArgs += $Port.ToString() }
foreach ($f in $Files) { $extraCliArgs += "--file"; $extraCliArgs += $f }
# Attach prompt file — avoids inlining huge prompt text on the command line
$extraCliArgs += "--file"; $extraCliArgs += $promptFileAbsolute

# --- MCP config: resolve and generate opencode.json for MCP servers ---
# opencode run reads MCP config from .opencode/opencode.json (standard location).
# If no_mcp is set in role config, skip MCP entirely.
$tempMcpConfig = $null
if (-not $NoMcp) {
    # Priority 0: pre-compiled .opencode/opencode.json in project dir (written by ostwin init/compile)
    $precompiledOpencode = $null
    if ($ProjectDir) {
        $precompiledOpencode = Join-Path $ProjectDir ".opencode" "opencode.json"
    }
    if ($precompiledOpencode -and (Test-Path $precompiledOpencode)) {
        # Use pre-compiled config directly — already in OpenCode format with $schema
        $tempMcpConfig = $precompiledOpencode
    }
    else {
        # Fallback: resolve from .agents/mcp/ configs and generate opencode.json
        $resolvedMcpConfig = $McpConfig
        if (-not $resolvedMcpConfig) {
            # Priority 1: project-local MCP config
            if ($ProjectDir) {
                foreach ($projectMcpConfig in @(
                        (Join-Path $ProjectDir ".agents" "mcp" "config.json"),
                        (Join-Path $ProjectDir ".agents" "mcp" "mcp-config.json")
                    )) {
                    if (Test-Path $projectMcpConfig) {
                        $resolvedMcpConfig = $projectMcpConfig
                        break
                    }
                }
            }
            # Priority 2: agents dir (same repo, e.g. installed copy)
            if (-not $resolvedMcpConfig) {
                foreach ($agentsDirMcpConfig in @(
                        (Join-Path $agentsDir "mcp" "config.json"),
                        (Join-Path $agentsDir "mcp" "mcp-config.json")
                    )) {
                    if (Test-Path $agentsDirMcpConfig) {
                        $resolvedMcpConfig = $agentsDirMcpConfig
                        break
                    }
                }
            }
            # Priority 3: OSTWIN_HOME global config
            if (-not $resolvedMcpConfig) {
                foreach ($ostwinMcpConfig in @(
                        (Join-Path $OstwinHome ".agents" "mcp" "config.json"),
                        (Join-Path $OstwinHome ".agents" "mcp" "mcp-config.json"),
                        (Join-Path $OstwinHome "mcp" "config.json"),
                        (Join-Path $OstwinHome "mcp" "mcp-config.json")
                    )) {
                    if (Test-Path $ostwinMcpConfig) {
                        $resolvedMcpConfig = $ostwinMcpConfig
                        break
                    }
                }
            }
        }
        if ($resolvedMcpConfig -and (Test-Path $resolvedMcpConfig)) {
            $mcpConfigContent = Get-Content $resolvedMcpConfig -Raw
            # Expand {env:AGENT_DIR} → absolute agentsDir (OpenCode format)
            if ($mcpConfigContent -match '\{env:AGENT_DIR\}') {
                $mcpConfigContent = $mcpConfigContent -replace '\{env:AGENT_DIR\}', $agentsDir.Replace('\', '/')
            }
            # Expand {env:PROJECT_DIR} → absolute project dir (OpenCode format)
            if ($ProjectDir -and ($mcpConfigContent -match '\{env:PROJECT_DIR\}')) {
                $mcpConfigContent = $mcpConfigContent -replace '\{env:PROJECT_DIR\}', $ProjectDir.Replace('\', '/')
            }
            # Legacy: also expand ${AGENT_DIR} / ${PROJECT_DIR} for pre-migration configs
            if ($mcpConfigContent -match '\$\{AGENT_DIR\}') {
                $mcpConfigContent = $mcpConfigContent -replace '\$\{AGENT_DIR\}', $agentsDir.Replace('\', '/')
            }
            if ($ProjectDir -and ($mcpConfigContent -match '\$\{PROJECT_DIR\}')) {
                $mcpConfigContent = $mcpConfigContent -replace '\$\{PROJECT_DIR\}', $ProjectDir.Replace('\', '/')
            }
            # Parse the MCP config and wrap it for opencode.json format
            try {
                $mcpParsed = $mcpConfigContent | ConvertFrom-Json
                # opencode.json expects { "$schema": "...", "mcp": { ... } }
                # Source config uses "mcp" key directly (OpenCode format), fallback to legacy "mcpServers"/"servers"
                $mcpServers = $null
                if ($mcpParsed.PSObject.Properties['mcp']) { $mcpServers = $mcpParsed.mcp }
                elseif ($mcpParsed.PSObject.Properties['mcpServers']) { $mcpServers = $mcpParsed.mcpServers }
                elseif ($mcpParsed.PSObject.Properties['servers']) { $mcpServers = $mcpParsed.servers }
                else { $mcpServers = $mcpParsed }

                if ($mcpServers) {
                    $opencodeConfig = @{ '$schema' = 'https://opencode.ai/config.json'; mcp = $mcpServers } | ConvertTo-Json -Depth 10
                    $tempMcpConfig = Join-Path $artifactsDir "opencode.json"
                    $opencodeConfig | Out-File -FilePath $tempMcpConfig -Encoding utf8 -NoNewline -Force
                }
            }
            catch {
                Write-Warning "[Invoke-Agent] Failed to parse MCP config for opencode.json: $($_.Exception.Message)"
            }
        }
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
        $safeOutput = $outputFile -replace "'", "'\''"
        $safePrompt = $promptFile -replace "'", "'\''"
        $safeCwd = if ($WorkingDir) { $WorkingDir -replace "'", "'\''" } else { "" }
        $safeRoomDir = $absRoomDir.Replace('\', '/').Replace("'", "'\''")
        $safeSkillsDir = $isolatedSkillsDir.Replace('\', '/').Replace("'", "'\''")
        $safeRole = $RoleName -replace "'", "'\''"

        $cwdLine = if ($safeCwd) { "cd '$safeCwd' 2>/dev/null || true" } else { "" }
        $safePidFile = $pidFile -replace "'", "'\''"
        $safeOstwinHome = $OstwinHome.Replace('\', '/').Replace("'", "'\''")
        $safeProjectDir = if ($ProjectDir) { $ProjectDir.Replace('\', '/').Replace("'", "'\''") } else { "" }
        $opencodeConfigLine = ""
        if ($tempMcpConfig) {
            $safeOpencodeConfig = $tempMcpConfig.Replace('\', '/').Replace("'", "'\''")
            $opencodeConfigLine = "export OPENCODE_CONFIG='$safeOpencodeConfig'"
        }
        # Log diagnostic info before exec
        Write-Host "[Invoke-Agent] Launching: CMD=$AgentCmd, PromptFile=$promptFile, ArgsLine=$argsLine"
        $scriptContent = @"
#!/bin/bash
export AGENT_OS_ROOM_DIR='$safeRoomDir'
export AGENT_OS_ROLE='$safeRole'
export AGENT_OS_PARENT_PID='$PID'
export AGENT_OS_SKILLS_DIR='$safeSkillsDir'
export AGENT_OS_PID_FILE='$safePidFile'
export OSTWIN_HOME='$safeOstwinHome'
export AGENT_OS_PROJECT_DIR='$safeProjectDir'
$opencodeConfigLine
$cwdLine
# Write PID before exec — `$`$ survives exec, so this is the real agent PID.
# bin/agent also writes this (harmless overwrite); this fallback ensures
# non-bin/agent commands (opencode run, custom CLIs) still get tracked.
echo "`$$" > '$safePidFile'
# Log diagnostic info before exec
echo "[wrapper] PID=`$$, CMD=$AgentCmd, CWD=`$(pwd)" >> '$safeOutput'
echo "[wrapper] PROMPT_FILE='$safePrompt' (exists: `$(test -f '$safePrompt' && echo yes || echo no), size: `$(wc -c < '$safePrompt' 2>/dev/null || echo 0) bytes)" >> '$safeOutput'
echo "[wrapper] EXEC: $AgentCmd 'start' $argsLine" >> '$safeOutput'
exec $AgentCmd 'start' $argsLine >> '$safeOutput' 2>&1
# If exec fails, this line runs:
echo "[wrapper] EXEC FAILED: exit=`$?" >> '$safeOutput'
"@
        $scriptContent | Out-File -FilePath $wrapperScript -Encoding utf8 -NoNewline -Force
        chmod +x $wrapperScript 2>$null

        # --- Launch bash via System.Diagnostics.Process ---
        # Start-Process -NoNewWindow is unreliable inside Start-Job on macOS
        # (no console to attach to in headless runspace). Direct Process API works.
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = "bash"
        $psi.Arguments = "`"$wrapperScript`""
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
                        }
                        catch { }
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
# Remove generated opencode.json (MCP config) if one was created
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
