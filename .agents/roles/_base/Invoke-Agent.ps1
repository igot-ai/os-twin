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

# --- Build CLI arguments ---
$cliArgs = @("-n", $Prompt)

if ($AutoApprove) {
    $cliArgs += "--auto-approve"
}

if ($Model) {
    $cliArgs += @("--model", $Model)
}

# Shell allow list for engineer
if ($RoleName -eq 'engineer') {
    $cliArgs += @("--shell-allow-list", "all")
}

if ($Quiet) {
    $cliArgs += "-q"
}

$cliArgs += $ExtraArgs

# --- Execute with timeout ---
$exitCode = 0
try {
    $job = Start-Job -ScriptBlock {
        param($cmd, $args, $outFile, $cwd)
        if ($cwd -and (Test-Path $cwd)) {
            Set-Location $cwd
        }
        & $cmd @args 2>&1 | Tee-Object -FilePath $outFile
    } -ArgumentList $AgentCmd, $cliArgs, $outputFile, $WorkingDir

    $completed = $job | Wait-Job -Timeout $TimeoutSeconds

    if ($null -eq $completed) {
        # Timeout
        $job | Stop-Job
        $job | Remove-Job -Force
        $exitCode = 124
        "Agent timed out after ${TimeoutSeconds}s" | Out-File -FilePath $outputFile -Encoding utf8
    }
    else {
        $job | Receive-Job -ErrorAction SilentlyContinue | Out-Null
        $exitCode = if ($job.State -eq 'Failed') { 1 } else { 0 }
        $job | Remove-Job -Force
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

# --- Clean up PID file ---
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue

# --- Return result ---
[PSCustomObject]@{
    ExitCode   = $exitCode
    Output     = $output
    OutputFile = $outputFile
    PidFile    = $pidFile
    RoleName   = $RoleName
    TimedOut   = ($exitCode -eq 124)
}
