# window.ps1 — Windows window geometry control via Win32 API
# Usage: window.ps1 <cmd> <AppName> [args]
# Requires: PowerShell 5.1+, Windows
param(
    [Parameter(Position=0)][string]$Cmd = "help",
    [Parameter(Position=1)][string]$AppName = "",
    [Parameter(Position=2)][int]$X = 0,
    [Parameter(Position=3)][int]$Y = 0,
    [Parameter(Position=4)][int]$W = 800,
    [Parameter(Position=5)][int]$H = 600
)

. "$PSScriptRoot\_lib.ps1"

function Show-Usage {
    @"
Usage: window.ps1 <cmd> <AppName> [args]

Commands:
  move <AppName> <x> <y>                Move front window
  resize <AppName> <w> <h>              Resize front window
  set-bounds <AppName> <x> <y> <w> <h>  Set position and size
  minimize <AppName>                    Minimize to taskbar
  restore <AppName>                     Restore from taskbar
  fullscreen <AppName>                  Maximize window
  help                                  Show this help
"@ | Write-Host
}

Add-TypeSafe -TypeName "Win32Window" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32Window {
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    public struct RECT { public int Left, Top, Right, Bottom; }
    public const int SW_MINIMIZE = 6;
    public const int SW_RESTORE  = 9;
    public const int SW_MAXIMIZE = 3;
}
"@

function Get-MainWindow([string]$Name) {
    $proc = Get-Process -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { Write-Error "Process not found: $Name"; exit 1 }
    if ($proc.MainWindowHandle -eq [IntPtr]::Zero) { Write-Error "No visible window for: $Name"; exit 1 }
    return $proc.MainWindowHandle
}

switch ($Cmd) {
    "move" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        $rect = New-Object Win32Window+RECT
        [Win32Window]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
        $cw = $rect.Right - $rect.Left
        $ch = $rect.Bottom - $rect.Top
        [Win32Window]::MoveWindow($hwnd, $X, $Y, $cw, $ch, $true) | Out-Null
        Write-Host "Moved $AppName to $X,$Y"
    }

    "resize" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        $rect = New-Object Win32Window+RECT
        [Win32Window]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
        [Win32Window]::MoveWindow($hwnd, $rect.Left, $rect.Top, $W, $H, $true) | Out-Null
        Write-Host "Resized $AppName to ${W}x${H}"
    }

    "set-bounds" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        [Win32Window]::MoveWindow($hwnd, $X, $Y, $W, $H, $true) | Out-Null
        Write-Host "Set $AppName bounds: origin=$X,$Y size=${W}x${H}"
    }

    "minimize" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        [Win32Window]::ShowWindow($hwnd, [Win32Window]::SW_MINIMIZE) | Out-Null
        Write-Host "Minimized: $AppName"
    }

    "restore" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        [Win32Window]::ShowWindow($hwnd, [Win32Window]::SW_RESTORE) | Out-Null
        Write-Host "Restored: $AppName"
    }

    "fullscreen" {
        Assert-NonEmpty $AppName "AppName"
        $hwnd = Get-MainWindow $AppName
        [Win32Window]::ShowWindow($hwnd, [Win32Window]::SW_MAXIMIZE) | Out-Null
        Write-Host "Maximized: $AppName"
    }

    { $_ -in "help", "--help", "-h" } { Show-Usage }

    default {
        Write-Error "Unknown command: $Cmd"
        Show-Usage
        exit 1
    }
}
