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

# Ensure RoomDir is absolute for bash wrapper consistency (EPIC-002)
# Using GetUnresolvedProviderPathFromPSPath to handle non-existent paths (unlikely but safe)
$absRoomDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RoomDir)

# --- Load config ---
$configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
              else { Join-Path $agentsDir "config.json" }

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json

    # --- Instance-aware config resolution ---
    $instanceConfig = $null
    if ($InstanceId -and $config.$RoleName.instances.$InstanceId) {
        $instanceConfig = $config.$RoleName.instances.$InstanceId
    }

    # Model: instance → role config.json → role.json → hardcoded default
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

    # Timeout: instance → role
    if ($TimeoutSeconds -eq 600) {
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
$isolatedSkillsDir = Join-Path $artifactsDir "skills"

# Clear isolated skills for each invocation to ensure no stale skills remain
if (Test-Path $isolatedSkillsDir) {
    Remove-Item -Path $isolatedSkillsDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $isolatedSkillsDir -Force | Out-Null

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
                Copy-Item -Path (Join-Path $skillSrcDir "*") -Destination $destPath -Recurse -Force
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

# --- Write PID before execution so manager can track ---
$PID | Out-File -FilePath $pidFile -Encoding utf8 -NoNewline



# --- Execute with timeout ---
$exitCode = 0
try {
    $stdinNull = if ($IsLinux -or $IsMacOS) { "/dev/null" }
                 else { "NUL" }

    # Write prompt to a file to avoid shell escaping issues
    $promptFile = Join-Path $artifactsDir "prompt.txt"
    $Prompt | Out-File -FilePath $promptFile -Encoding utf8 -NoNewline -Force

    # Build non-prompt CLI args safely
    $extraCliArgs = @()
    if ($RoleName) { $extraCliArgs += "--agent"; $extraCliArgs += $RoleName }
    if ($AutoApprove) { $extraCliArgs += "--auto-approve" }
    if ($Model) { $extraCliArgs += "--model"; $extraCliArgs += $Model }
    if ($RoleName -eq 'engineer') { $extraCliArgs += "--shell-allow-list"; $extraCliArgs += "all" }
    if ($Quiet) { $extraCliArgs += "--quiet" }

    # --- MCP config: let agents pick the best tool server available ---
    $resolvedMcpConfig = $McpConfig
    if (-not $resolvedMcpConfig) {
        $resolvedMcpConfig = Join-Path $agentsDir "mcp" "mcp-config.json"
    }
    if ($resolvedMcpConfig -and (Test-Path $resolvedMcpConfig)) {
        $mcpConfigContent = Get-Content $resolvedMcpConfig -Raw
        # Expand ${AGENT_DIR} → absolute agentsDir so deepagents gets concrete paths
        if ($mcpConfigContent -match '\$\{AGENT_DIR\}') {
            $mcpConfigContent = $mcpConfigContent -replace '\$\{AGENT_DIR\}', $agentsDir.Replace('\', '/')
            $tempMcpConfig = Join-Path $artifactsDir "mcp-config-resolved.json"
            $mcpConfigContent | Out-File -FilePath $tempMcpConfig -Encoding utf8 -NoNewline -Force
            $resolvedMcpConfig = $tempMcpConfig
        }
        $extraCliArgs += "--mcp-config"
        $extraCliArgs += (Resolve-Path $resolvedMcpConfig).Path
    }

    $extraCliArgs += $ExtraArgs

    $argsLine = ($extraCliArgs | ForEach-Object {
        if ($_ -match '[\s"]') { "'$($_ -replace "'", "'\''")'" } else { $_ }
    }) -join ' '

    # Write wrapper script
    $wrapperScript = Join-Path $artifactsDir "run-agent.sh"
    $safeOutput = $outputFile -replace "'", "'\''"
    $safePrompt = $promptFile -replace "'", "'\''"
    $safeCwd = if ($WorkingDir) { $WorkingDir -replace "'", "'\''" } else { "" }
    $safeRoomDir = $absRoomDir.Replace('\', '/').Replace("'", "'\''")
    $safeSkillsDir = $isolatedSkillsDir.Replace('\', '/').Replace("'", "'\''")
    $safeRole = $RoleName -replace "'", "'\''"

    $cwdLine = if ($safeCwd) { "cd '$safeCwd' 2>/dev/null || true" } else { "" }
    $scriptContent = @"
#!/bin/bash
export AGENT_OS_ROOM_DIR='$safeRoomDir'
export AGENT_OS_ROLE='$safeRole'
export AGENT_OS_PARENT_PID='$PID'
export AGENT_OS_SKILLS_DIR='$safeSkillsDir'
$cwdLine
$AgentCmd -n "`$(cat '$safePrompt')" $argsLine > '$safeOutput' 2>&1
"@
    $scriptContent | Out-File -FilePath $wrapperScript -Encoding utf8 -NoNewline -Force
    chmod +x $wrapperScript 2>$null

    $proc = Start-Process -FilePath "bash" `
        -ArgumentList $wrapperScript `
        -NoNewWindow -PassThru `
        -RedirectStandardInput $stdinNull

    # Overwrite PID file with the actual bash child PID (not PS $PID)
    # so manager's Test-PidAlive can detect when the agent process dies.
    $proc.Id | Out-File -FilePath $pidFile -Encoding utf8 -NoNewline

    $finished = $proc | Wait-Process -Timeout $TimeoutSeconds -ErrorAction SilentlyContinue
    if (-not $proc.HasExited) {
        # Timeout
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $exitCode = 124
        "Agent timed out after ${TimeoutSeconds}s" | Out-File -FilePath $outputFile -Encoding utf8 -Append
    }
    else {
        $exitCode = $proc.ExitCode
    }
}
catch {
    $exitCode = 1
    $_.Exception.Message | Out-File -FilePath $outputFile -Encoding utf8
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
