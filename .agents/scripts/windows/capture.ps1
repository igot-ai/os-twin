# capture.ps1 — Windows screenshot capture via System.Drawing
# Usage: capture.ps1 <cmd> [args]
# Requires: PowerShell 5.1+, Windows, .NET Framework (built-in)
param(
    [Parameter(Position=0)][string]$Cmd = "help",
    [Parameter(Position=1)][string]$Arg1 = "",
    [Parameter(Position=2)][string]$Arg2 = "",
    [Parameter(Position=3)][string]$Arg3 = "",
    [Parameter(Position=4)][string]$Arg4 = "",
    [Parameter(Position=5)][string]$Arg5 = ""
)

. "$PSScriptRoot\_lib.ps1"

function Show-Usage {
    @"
Usage: capture.ps1 <cmd> [args]

Commands:
  full [outfile]                    Capture primary screen
  region <x> <y> <w> <h> [outfile] Capture a screen region
  window <AppName> [outfile]        Capture main window of an app
  clipboard                         Capture screen to clipboard
  help                              Show this help

Output defaults to: $env:TEMP\ostwin-capture-<timestamp>.png
"@ | Write-Host
}

Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

Add-TypeSafe -TypeName "Win32Capture" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32Capture {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

function Default-Out {
    $ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    return "$env:TEMP\ostwin-capture-$ts.png"
}

function Save-Bitmap([System.Drawing.Bitmap]$bmp, [string]$path) {
    $dir = Split-Path $path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

switch ($Cmd) {
    "full" {
        $out = if ($Arg1) { $Arg1 } else { Default-Out }
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($screen.Left, $screen.Top, 0, 0, $bmp.Size)
        $g.Dispose()
        Save-Bitmap $bmp $out
        Write-Host "Captured full screen: $out"
    }

    "region" {
        Assert-UInt $Arg1 "x"; Assert-UInt $Arg2 "y"
        Assert-UInt $Arg3 "width"; Assert-UInt $Arg4 "height"
        $x = [int]$Arg1; $y = [int]$Arg2; $w = [int]$Arg3; $h = [int]$Arg4
        $out = if ($Arg5) { $Arg5 } else { Default-Out }
        $bmp = New-Object System.Drawing.Bitmap($w, $h)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($x, $y, 0, 0, (New-Object System.Drawing.Size($w, $h)))
        $g.Dispose()
        Save-Bitmap $bmp $out
        Write-Host "Captured region ${w}x${h} at $x,$y: $out"
    }

    "window" {
        Assert-NonEmpty $Arg1 "AppName"
        $out = if ($Arg2) { $Arg2 } else { Default-Out }
        $proc = Get-Process -Name $Arg1 -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $proc -or $proc.MainWindowHandle -eq [IntPtr]::Zero) {
            Write-Error "No visible window found for: $Arg1"; exit 1
        }
        $rect = New-Object Win32Capture+RECT
        [Win32Capture]::GetWindowRect($proc.MainWindowHandle, [ref]$rect) | Out-Null
        $w = $rect.Right - $rect.Left
        $h = $rect.Bottom - $rect.Top
        $bmp = New-Object System.Drawing.Bitmap($w, $h)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size($w, $h)))
        $g.Dispose()
        Save-Bitmap $bmp $out
        Write-Host "Captured $Arg1 window: $out"
    }

    "clipboard" {
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($screen.Left, $screen.Top, 0, 0, $bmp.Size)
        $g.Dispose()
        [System.Windows.Forms.Clipboard]::SetImage($bmp)
        $bmp.Dispose()
        Write-Host "Captured screen to clipboard"
    }

    { $_ -in "help", "--help", "-h" } { Show-Usage }

    default {
        Write-Error "Unknown command: $Cmd"
        Show-Usage
        exit 1
    }
}
