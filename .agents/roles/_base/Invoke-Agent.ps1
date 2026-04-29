<#
.SYNOPSIS
    Universal agent launcher — wraps opencode run for any role.

.DESCRIPTION
    Provides a common interface for launching opencode run with role-specific
    prompts, config, PID tracking, timeout, and output capture.
    Used by Start-Engineer.ps1, Start-QA.ps1, and future role runners.

    v0.4 — direct child process execution (no generated wrapper script).
    Env vars set inline with save/restore to prevent process pollution.
    PID tracked directly from Start-Process, no polling needed.
    Ctrl+C propagation via try/finally cleanup.

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
$_homeDir = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $_homeDir ".ostwin" }

# Ensure RoomDir is absolute for wrapper script consistency (EPIC-002)
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
# Schema: { "<role>": { "default_model": "...", "timeout_seconds": N, "max_retries": N,
#                       "instances": { "<id>": { "default_model": "...", "timeout_seconds": N } } } }
$timeoutWasExplicit = $PSBoundParameters.ContainsKey('TimeoutSeconds')
$maxProcessRetries = 3  # default — overridden by plan roles / config / role.json below

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

    # max_retries from plan roles (highest priority)
    if ($planRoleNode.max_retries) {
        $maxProcessRetries = [int]$planRoleNode.max_retries
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

    # Normalize model: auto-prefix bare model names with their provider so opencode
    # can resolve them. Many dynamically-created role.json files store just
    # "gemini-3-flash-preview" without the "google-vertex/" prefix.
    if ($Model -and ($Model -notmatch '/')) {
        if ($Model -match '^gemini') {
            $Model = "google-vertex/$Model"
        }
        elseif ($Model -match '^claude') {
            $Model = "anthropic/$Model"
        }
        elseif ($Model -match '^gpt|^o1|^o3|^o4') {
            $Model = "openai/$Model"
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

    # max_retries fallback chain: plan roles (already applied) → instance → role config.json
    if ($maxProcessRetries -eq 3) {
        if ($instanceConfig -and $instanceConfig.max_retries) {
            $maxProcessRetries = [int]$instanceConfig.max_retries
        }
        elseif ($config.$RoleName.max_retries) {
            $maxProcessRetries = [int]$config.$RoleName.max_retries
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

    # --- CLI resolution: env override → OSTWIN_HOME/.agents/bin/agent (mandatory) ---
    if (-not $AgentCmd) {
        if ($env:OSTWIN_AGENT_CMD) {
            $AgentCmd = $env:OSTWIN_AGENT_CMD
        }
        else {
            $ostwinAgent = Join-Path $OstwinHome ".agents" "bin" "agent"
            if (Test-Path $ostwinAgent) {
                $AgentCmd = "'$ostwinAgent'"
            }
            else {
                Write-Error "Agent binary not found at: $ostwinAgent`nRun the installer or set `$OSTWIN_AGENT_CMD."
                exit 1
            }
        }
    }
}

if (-not $AgentCmd) { $AgentCmd = "opencode run" }

# --- Role.json model + max_retries fallback (runs even when config.json is absent) ---
# If no model was resolved from -Model param, plan.roles.json, or config.json,
# try role.json as the last config-based source before the hardcoded default.
# Search order: HOME-based (authoritative) → project-local (legacy).
if (-not $Model -or $maxProcessRetries -eq 3) {
    $homeRoleJson = Join-Path $OstwinHome ".agents" "roles" $RoleName "role.json"
    $localRoleJson = Join-Path $agentsDir "roles" $RoleName "role.json"
    $roleJsonPath = if (Test-Path $homeRoleJson) { $homeRoleJson } elseif (Test-Path $localRoleJson) { $localRoleJson } else { $null }
    if ($roleJsonPath) {
        try {
            $roleJson = Get-Content $roleJsonPath -Raw | ConvertFrom-Json
            if (-not $Model -and $roleJson.model) {
                $Model = $roleJson.model
            }
            # max_retries from role.json (lowest config priority, above hardcoded default)
            if ($maxProcessRetries -eq 3 -and $roleJson.max_retries) {
                $maxProcessRetries = [int]$roleJson.max_retries
            }
        }
        catch { }
    }
}
if (-not $Model) { $Model = "google-vertex/zai-org/glm-5-maas" }

# --- Env var overrides for testing ---
$envCmdVar = "${RoleName}_CMD".ToUpper()
$envCmd = [System.Environment]::GetEnvironmentVariable($envCmdVar)
if ($envCmd) { $AgentCmd = $envCmd }

# --- Log resolved model/timeout/retries for debugging ---
# These are the values that will actually drive opencode run.
Write-Host "[Invoke-Agent] Resolved Role=$RoleName Instance=$InstanceId Model=$Model Timeout=${TimeoutSeconds}s MaxRetries=$maxProcessRetries"

# --- Prepare output directory ---
$artifactsDir = Join-Path $absRoomDir "artifacts"
$pidsDir = Join-Path $absRoomDir "pids"
New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
New-Item -ItemType Directory -Path $pidsDir -Force | Out-Null

# --- Ensure ProjectDir is resolved (unconditional fallback) ---
# The config block above computes $ProjectDir only when config.json exists.
# Run the same walkup here so skill staging always uses the correct project dir,
# even for rooms without a config.json (e.g. test rooms, clean invocations).
if (-not $ProjectDir) {
    $searchDir2 = $absRoomDir
    for ($i = 0; $i -lt 6; $i++) {
        $parentDir2 = Split-Path $searchDir2 -Parent
        if (-not $parentDir2 -or $parentDir2 -eq $searchDir2) { break }
        if ((Split-Path $searchDir2 -Leaf) -eq ".war-rooms") {
            $ProjectDir = $parentDir2
            break
        }
        $searchDir2 = $parentDir2
    }
    if (-not $ProjectDir -and $env:PROJECT_DIR) { $ProjectDir = $env:PROJECT_DIR }
    if (-not $ProjectDir -and $WorkingDir) { $ProjectDir = $WorkingDir }
}

# --- Skill Staging: project-local .agents/skills/ (shared across rooms) ---
# Use the *project's* .agents/skills/, not the ostwin install tree ($agentsDir).
# This ensures skills appear at $project_dir/.agents/skills/ regardless of
# where Invoke-Agent.ps1 is installed (~/.ostwin or project-local dev copy).
$projectAgentsDir = if ($ProjectDir) { Join-Path $ProjectDir ".agents" } else { $agentsDir }
$isolatedSkillsDir = Join-Path $projectAgentsDir "skills"

# Ensure project-level skills dir exists
if (-not (Test-Path $isolatedSkillsDir)) {
    New-Item -ItemType Directory -Path $isolatedSkillsDir -Force | Out-Null
}

$rolePath = Join-Path $agentsDir "roles" $RoleName
$resolveSkillsScript = Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1"

if (Test-Path $resolveSkillsScript) {
    try {
        $skills = & $resolveSkillsScript -RoleName $RoleName -RolePath $rolePath -RoomDir $absRoomDir -ErrorAction Stop
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

# ═══════════════════════════════════════════════════════════════════
# Phase 2: Inline Environment Setup (replaces generated wrapper)
# ═══════════════════════════════════════════════════════════════════

# --- Import-EnvFile: load KEY=VALUE pairs from a .env file ---
function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#') -or $t -notmatch '=') { continue }
        $eqIdx = $t.IndexOf('=')
        $k = $t.Substring(0, $eqIdx).Trim()
        $v = $t.Substring($eqIdx + 1).Trim().Trim([char[]]@([char]39,[char]34))
        if (-not [System.Environment]::GetEnvironmentVariable($k)) {
            [System.Environment]::SetEnvironmentVariable($k, $v)
        }
    }
}

# Platform-specific venv Python path
$venvPythonPath = if ($IsWindows) {
    Join-Path $OstwinHome ".venv" "Scripts" "python.exe"
} else {
    Join-Path $OstwinHome ".venv" "bin" "python"
}

# Save env vars we're about to set (restore after child exits to prevent test pollution)
$_savedEnv = @{
    AGENT_OS_ROOM_DIR   = $env:AGENT_OS_ROOM_DIR
    AGENT_OS_ROLE       = $env:AGENT_OS_ROLE
    AGENT_OS_PARENT_PID = $env:AGENT_OS_PARENT_PID
    AGENT_OS_SKILLS_DIR = $env:AGENT_OS_SKILLS_DIR
    AGENT_OS_PID_FILE   = $env:AGENT_OS_PID_FILE
    OSTWIN_HOME         = $env:OSTWIN_HOME
    AGENT_DIR           = $env:AGENT_DIR
    OSTWIN_PYTHON       = $env:OSTWIN_PYTHON
    OPENCODE_CONFIG     = $env:OPENCODE_CONFIG
}

# Set env vars for child process inheritance
$env:AGENT_OS_ROOM_DIR   = $absRoomDir
$env:AGENT_OS_ROLE       = $RoleName
$env:AGENT_OS_PARENT_PID = $PID
$env:AGENT_OS_SKILLS_DIR = $isolatedSkillsDir
$env:AGENT_OS_PID_FILE   = $pidFile
$env:OSTWIN_HOME         = $OstwinHome
$env:AGENT_DIR           = $OstwinHome
$env:OSTWIN_PYTHON       = $venvPythonPath

# Load .env file (sets API keys etc. — only if not already set)
Import-EnvFile (Join-Path $OstwinHome ".env")

# MCP config
$tempMcpConfig = $null
if (-not $NoMcp -and $ProjectDir) {
    $precompiledOpencode = Join-Path $ProjectDir ".opencode" "opencode.json"
    if (Test-Path $precompiledOpencode) {
        $tempMcpConfig = $precompiledOpencode
    }
}
if ($tempMcpConfig) { $env:OPENCODE_CONFIG = $tempMcpConfig }

# Debug logging
$ts = Get-Date -Format "HH:mm:ss.fff"
Write-Host "[$ts][CONFIG] Model=$Model Timeout=${TimeoutSeconds}s Retries=$maxProcessRetries"
Write-Host "[$ts][ENV] OSTWIN_HOME=$OstwinHome OPENCODE_CONFIG=$($env:OPENCODE_CONFIG) PYTHON=$venvPythonPath"
Write-Host "[$ts][SKILLS] SkillsDir=$isolatedSkillsDir"

# ═══════════════════════════════════════════════════════════════════
# Phase 3: Build CLI Arguments & Execute
# ═══════════════════════════════════════════════════════════════════

$exitCode = 0

# Write prompt to file to avoid shell escaping / ARG_MAX issues
$promptFile = Join-Path $artifactsDir "prompt.txt"
$Prompt | Out-File -FilePath $promptFile -Encoding utf8 -NoNewline -Force
$promptFileAbsolute = (Resolve-Path $promptFile).Path

# Debug: human-readable copy of the compiled prompt
$debugPromptFile = Join-Path $artifactsDir "$RoleName-prompt-debug.md"
$Prompt | Out-File -FilePath $debugPromptFile -Encoding utf8 -Force

# Build CLI args array
$extraCliArgs = @("Execute the task described in the attached prompt file.")
if ($Model)           { $extraCliArgs += "--model";   $extraCliArgs += $Model }
if ($RoleName)        { $extraCliArgs += "--agent";   $extraCliArgs += $RoleName }
if ($Format)          { $extraCliArgs += "--format";  $extraCliArgs += $Format }
if ($SessionTitle)    { $extraCliArgs += "--title";   $extraCliArgs += $SessionTitle }
if ($SessionId)       { $extraCliArgs += "--session"; $extraCliArgs += $SessionId }
if ($ContinueSession) { $extraCliArgs += "--continue" }
if ($ForkSession)     { $extraCliArgs += "--fork" }
if ($ShareSession)    { $extraCliArgs += "--share" }
if ($Command)         { $extraCliArgs += "--command"; $extraCliArgs += $Command }
if ($AttachUrl)       { $extraCliArgs += "--attach";  $extraCliArgs += $AttachUrl }
if ($Port -gt 0)      { $extraCliArgs += "--port";    $extraCliArgs += $Port.ToString() }
if ($ProjectDir)      { $extraCliArgs += "--dir";     $extraCliArgs += $ProjectDir }
foreach ($f in $Files) { $extraCliArgs += "--file";   $extraCliArgs += $f }
$extraCliArgs += "--file"; $extraCliArgs += $promptFileAbsolute
$extraCliArgs += $ExtraArgs
$extraCliArgs += "--dangerously-skip-permissions"

# --- Phase 3a: Tokenize AgentCmd ---
$cmdParts = $AgentCmd.Trim("'").Trim('"').Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
$exe = $cmdParts[0]
$cmdBaseArgs = if ($cmdParts.Length -gt 1) { $cmdParts[1..($cmdParts.Length - 1)] } else { @() }

# Handle .ps1 mock scripts: wrap with pwsh
$isPwshScript = $false
if ($exe -match '\.ps1$') {
    $isPwshScript = $true
    $scriptPath = $exe
    $cmdBaseArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath) + $cmdBaseArgs
    $exe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
}

$allArgs = $cmdBaseArgs + $extraCliArgs
$ts = Get-Date -Format "HH:mm:ss.fff"
Write-Host "[$ts][CLI] EXE=$exe isPwshScript=$isPwshScript ARGS=$($allArgs -join ' ')"

# ═══════════════════════════════════════════════════════════════════
# Phase 4: Execute with timeout + retry (direct child process)
# ═══════════════════════════════════════════════════════════════════

for ($processAttempt = 1; $processAttempt -le $maxProcessRetries; $processAttempt++) {
    $exitCode = 0
    $proc = $null
    try {
        $ts = Get-Date -Format "HH:mm:ss.fff"
        Write-Host "[$ts][EXEC] Attempt $processAttempt/$maxProcessRetries — launching $exe"

        # Quote args containing spaces for Start-Process (which joins with spaces internally)
        $quotedArgs = $allArgs | ForEach-Object {
            if ($_ -match '\s') { "`"$_`"" } else { $_ }
        }

        $proc = Start-Process -FilePath $exe `
            -ArgumentList $quotedArgs `
            -NoNewWindow -PassThru `
            -RedirectStandardOutput $outputFile `
            -RedirectStandardError (Join-Path $artifactsDir "$RoleName-stderr.txt")

        # Immediate PID registration — no polling needed
        $proc.Id | Out-File -FilePath $pidFile -Encoding ascii -NoNewline -Force
        $ts = Get-Date -Format "HH:mm:ss.fff"
        Write-Host "[$ts][PID] Child PID=$($proc.Id) written to $pidFile (parent PID=$PID)"

        # Wait with timeout
        $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
        if (-not $finished) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            try { $proc.WaitForExit(3000) } catch {}
            $exitCode = 124
            try {
                "Agent timed out after ${TimeoutSeconds}s" | Out-File -FilePath $outputFile -Encoding utf8 -Append
            } catch {}
        } else {
            # Parameterless WaitForExit() ensures redirected stdout is fully flushed
            $proc.WaitForExit()
            $exitCode = $proc.ExitCode
            # Brief settle for file handle release (fast processes like /bin/echo)
            Start-Sleep -Milliseconds 50
        }

        $ts = Get-Date -Format "HH:mm:ss.fff"
        Write-Host "[$ts][EXIT] ExitCode=$exitCode (attempt $processAttempt)"
    }
    catch {
        $exitCode = 1
        Write-Host "[Invoke-Agent] ERROR (attempt $processAttempt): $($_.Exception.Message)" -ForegroundColor Red
        "$($_.Exception.GetType().FullName) : $($_.Exception.Message)" | Out-File -FilePath $outputFile -Encoding utf8
    }
    finally {
        # Ensure child is killed on Ctrl+C or unhandled error
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }

    # Retry on transient remote errors
    if ($exitCode -ne 0 -and $exitCode -ne 124 -and $processAttempt -lt $maxProcessRetries) {
        $agentOutput = if (Test-Path $outputFile) { Get-Content $outputFile -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($agentOutput -match "ClosedResourceError|RemoteException.*ClosedResource|ReadError|WriteError") {
            $backoff = [math]::Pow(2, $processAttempt)
            Write-Host "[Invoke-Agent] Transient error, retrying in ${backoff}s..."
            Start-Sleep -Seconds $backoff
            continue
        }
    }
    break
}

# ═══════════════════════════════════════════════════════════════════
# Phase 5: Restore env vars & return result
# ═══════════════════════════════════════════════════════════════════

foreach ($kv in $_savedEnv.GetEnumerator()) {
    if ($null -eq $kv.Value) {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $null)
    } else {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value)
    }
}

# Read output
$output = if (Test-Path $outputFile) {
    Get-Content $outputFile -Raw -ErrorAction SilentlyContinue
} else { "No output captured" }

# Clean up temp files
Remove-Item $promptFile -Force -ErrorAction SilentlyContinue

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
