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
    Suppress interactive output (-q flag). Default: false.
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
    [switch]$Quiet,
    [string]$InstanceId = '',
    [string]$WorkingDir = '',
    [string[]]$ExtraArgs = @()
)

# --- Resolve paths ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path

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

    # Model: instance → role → engineer fallback
    if (-not $Model) {
        if ($instanceConfig -and $instanceConfig.default_model) {
            $Model = $instanceConfig.default_model
        }
        elseif ($config.$RoleName.default_model) {
            $Model = $config.$RoleName.default_model
        }
        else {
            $Model = $config.engineer.default_model
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

    # CLI: role → default
    if (-not $AgentCmd) {
        $AgentCmd = $config.$RoleName.cli
        if (-not $AgentCmd) { $AgentCmd = "deepagents" }
    }
}

if (-not $AgentCmd) { $AgentCmd = "deepagents" }
if (-not $Model) { $Model = "gemini-3-flash-preview" }

# --- Env var overrides for testing ---
$envCmdVar = "${RoleName}_CMD".ToUpper()
$envCmd = [System.Environment]::GetEnvironmentVariable($envCmdVar)
if ($envCmd) { $AgentCmd = $envCmd }

# --- Prepare output directory ---
$artifactsDir = Join-Path $RoomDir "artifacts"
$pidsDir = Join-Path $RoomDir "pids"
New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
New-Item -ItemType Directory -Path $pidsDir -Force | Out-Null

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
    if ($AutoApprove) { $extraCliArgs += "--auto-approve" }
    if ($Model) { $extraCliArgs += "--model"; $extraCliArgs += $Model }
    if ($RoleName -eq 'engineer') { $extraCliArgs += "--shell-allow-list"; $extraCliArgs += "all" }
    if ($Quiet) { $extraCliArgs += "-q" }
    $extraCliArgs += $ExtraArgs

    $argsLine = ($extraCliArgs | ForEach-Object {
        if ($_ -match '[\s"]') { "'$($_ -replace "'", "'\''")'" } else { $_ }
    }) -join ' '

    # Write wrapper script
    $wrapperScript = Join-Path $artifactsDir "run-agent.sh"
    $safeOutput = $outputFile -replace "'", "'\''"
    $safePrompt = $promptFile -replace "'", "'\''"
    $safeCwd = if ($WorkingDir) { $WorkingDir -replace "'", "'\''" } else { "" }

    $cwdLine = if ($safeCwd) { "cd '$safeCwd' 2>/dev/null || true" } else { "" }
    $scriptContent = @"
#!/bin/bash
$cwdLine
$AgentCmd -n "`$(cat '$safePrompt')" $argsLine > '$safeOutput' 2>&1
"@
    $scriptContent | Out-File -FilePath $wrapperScript -Encoding utf8 -NoNewline -Force
    chmod +x $wrapperScript 2>$null

    $proc = Start-Process -FilePath "bash" `
        -ArgumentList $wrapperScript `
        -NoNewWindow -PassThru `
        -RedirectStandardInput $stdinNull

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
