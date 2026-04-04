# app.ps1 — Windows application lifecycle control
# Usage: app.ps1 <cmd> [args]
# Requires: PowerShell 5.1+, Windows
param(
    [Parameter(Position=0)][string]$Cmd = "help",
    [Parameter(Position=1)][string]$Arg1 = "",
    [Parameter(Position=2)][string]$Arg2 = ""
)

. "$PSScriptRoot\_lib.ps1"

function Show-Usage {
    @"
Usage: app.ps1 <cmd> [args]

Commands:
  launch <AppName>      Start an application
  kill <AppName>        Stop a process by name
  frontmost             Get name of foreground window process
  list                  List all visible running applications
  is-running <AppName>  Exit 0 if running, 1 if not
  help                  Show this help
"@ | Write-Host
}

Add-TypeSafe -TypeName "Win32App" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32App {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
}
"@

switch ($Cmd) {
    "launch" {
        Assert-NonEmpty $Arg1 "AppName"
        try {
            Start-Process $Arg1 -ErrorAction Stop
            Write-Host "Launched: $Arg1"
        } catch {
            Write-Error "Failed to launch ${Arg1}: $_"
            exit 1
        }
    }

    "kill" {
        Assert-NonEmpty $Arg1 "AppName"
        $procs = Get-Process -Name $Arg1 -ErrorAction SilentlyContinue
        if ($procs) {
            $procs | ForEach-Object { $_.CloseMainWindow() | Out-Null }
            Start-Sleep -Milliseconds 500
            $remaining = Get-Process -Name $Arg1 -ErrorAction SilentlyContinue
            if ($remaining) { $remaining | Stop-Process -Force }
            Write-Host "Killed: $Arg1"
        } else {
            Write-Host "Not running: $Arg1"
        }
    }

    "frontmost" {
        $hwnd = [Win32App]::GetForegroundWindow()
        [uint32]$pid = 0
        [Win32App]::GetWindowThreadProcessId($hwnd, [ref]$pid) | Out-Null
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) { Write-Host $proc.ProcessName } else { Write-Host "unknown" }
    }

    "list" {
        Get-Process | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
            Select-Object -ExpandProperty ProcessName |
            Sort-Object -Unique |
            ForEach-Object { Write-Host $_ }
    }

    "is-running" {
        Assert-NonEmpty $Arg1 "AppName"
        $procs = Get-Process -Name $Arg1 -ErrorAction SilentlyContinue
        if ($procs) {
            Write-Host "running"
            exit 0
        } else {
            Write-Host "not running"
            exit 1
        }
    }

    { $_ -in "help", "--help", "-h" } { Show-Usage }

    default {
        Write-Error "Unknown command: $Cmd"
        Show-Usage
        exit 1
    }
}
