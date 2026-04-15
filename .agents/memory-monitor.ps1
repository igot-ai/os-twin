<#
.SYNOPSIS
    Memory Monitor — check status and watch ledger in real-time (PowerShell port of memory-monitor.sh)

.DESCRIPTION
    Monitors the Agent OS memory subsystem.

.PARAMETER Command
    Subcommand: status (default), watch, on, off.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("status", "watch", "on", "off")]
    [string]$Command = "status"
)

$ErrorActionPreference = "SilentlyContinue"

$AgentsDir = Split-Path $PSCommandPath -Parent
$Ledger = Join-Path $AgentsDir "memory" "ledger.jsonl"

# Resolve venv paths (cross-platform)
$VenvWin = Join-Path $AgentsDir ".venv" "Scripts" "python.exe"
$VenvUnix = Join-Path $AgentsDir ".venv" "bin" "python"
$Venv = if (Test-Path $VenvWin) { Split-Path $VenvWin -Parent | Split-Path -Parent }
        elseif (Test-Path $VenvUnix) { Split-Path $VenvUnix -Parent | Split-Path -Parent }
        else { Join-Path $AgentsDir ".venv" }
$VenvBak = Join-Path $AgentsDir ".venv.bak"

$PythonInVenv = if (Test-Path $VenvWin) { $VenvWin }
                elseif (Test-Path $VenvUnix) { $VenvUnix }
                else { $null }

switch ($Command) {
    "status" {
        Write-Host ""
        # Check .venv
        if ($PythonInVenv) {
            $mcpCheck = & $PythonInVenv -c "import mcp" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  MCP venv:  ON  ($Venv)"
            }
            else {
                Write-Host "  MCP venv:  EXISTS but missing mcp module"
            }
        }
        else {
            Write-Host "  MCP venv:  OFF  (.venv not found)"
        }

        # Check ledger
        if (Test-Path $Ledger) {
            $lines = (Get-Content $Ledger | Measure-Object -Line).Lines
            $lastLine = Get-Content $Ledger -Tail 1 -ErrorAction SilentlyContinue
            $lastTs = "?"
            if ($lastLine) {
                try {
                    $lastEntry = $lastLine | ConvertFrom-Json
                    $lastTs = $lastEntry.ts
                }
                catch { }
            }
            Write-Host "  Ledger:    $lines entries  (last: $lastTs)"
        }
        else {
            Write-Host "  Ledger:    empty  (no file)"
        }
        Write-Host ""
    }

    "watch" {
        Write-Host "Watching memory ledger... (Ctrl+C to stop)"
        Write-Host ""

        $initial = 0
        if (Test-Path $Ledger) {
            $initial = (Get-Content $Ledger | Measure-Object -Line).Lines
        }
        Write-Host "Starting at $initial entries"
        Write-Host "---"

        if (-not (Test-Path $Ledger)) {
            Write-Host "Ledger file not found. Waiting for creation..."
            while (-not (Test-Path $Ledger)) { Start-Sleep -Seconds 1 }
        }

        Get-Content $Ledger -Wait -Tail 0 | ForEach-Object {
            $line = $_.Trim()
            if (-not $line) { return }
            try {
                $entry = $line | ConvertFrom-Json
                $kind = if ($entry.kind) { $entry.kind } else { "?" }
                $room = if ($entry.room_id) { $entry.room_id } else { "?" }
                $ref = if ($entry.ref) { $entry.ref } else { "?" }
                $summary = if ($entry.summary) { $entry.summary.Substring(0, [Math]::Min(80, $entry.summary.Length)) } else { "" }
                $ts = if ($entry.ts) { $entry.ts } else { "?" }
                Write-Host ("  [{0}] {1,-12} {2,-12} {3,-10} {4}" -f $ts, $kind, $room, $ref, $summary)
            }
            catch { }
        }
    }

    "on" {
        if ($PythonInVenv) {
            Write-Host "Memory already ON"
        }
        elseif (Test-Path $VenvBak -PathType Container) {
            Move-Item -Path $VenvBak -Destination $Venv -Force
            Write-Host "Memory ON (restored .venv)"
        }
        else {
            Write-Host "No .venv or .venv.bak found. Create with:"
            if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
                Write-Host "  cd $AgentsDir && python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install 'mcp[cli]' fastmcp"
            }
            else {
                Write-Host "  cd $AgentsDir && python3 -m venv .venv && source .venv/bin/activate && pip install 'mcp[cli]' fastmcp"
            }
        }
    }

    "off" {
        if (Test-Path $Venv -PathType Container) {
            Move-Item -Path $Venv -Destination $VenvBak -Force
            Write-Host "Memory OFF (moved .venv -> .venv.bak)"
        }
        else {
            Write-Host "Memory already OFF"
        }
    }
}
