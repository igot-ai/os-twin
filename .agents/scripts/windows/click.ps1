# click.ps1 — Windows mouse input simulation via Win32 SendInput (modern API)
# Usage: click.ps1 <cmd> [args]
# Requires: PowerShell 5.1+, Windows
param(
    [Parameter(Position=0)][string]$Cmd = "help",
    [Parameter(Position=1)][string]$RawX = "0",
    [Parameter(Position=2)][string]$RawY = "0"
)

. "$PSScriptRoot\_lib.ps1"

function Show-Usage {
    @"
Usage: click.ps1 <cmd> [args]

Commands:
  click <x> <y>             Single left click at screen coordinates
  double-click <x> <y>      Double click at screen coordinates
  right-click <x> <y>       Right click at screen coordinates
  move <x> <y>              Move cursor to coordinates
  help                      Show this help
"@ | Write-Host
}

# Modern SendInput API — replaces deprecated mouse_event.
# Properly handles DPI-scaled displays on Windows 10/11.
Add-TypeSafe -TypeName "Win32Mouse" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class Win32Mouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    public const uint INPUT_MOUSE = 0;
    public const uint MOUSEEVENTF_LEFTDOWN   = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP     = 0x0004;
    public const uint MOUSEEVENTF_RIGHTDOWN  = 0x0008;
    public const uint MOUSEEVENTF_RIGHTUP    = 0x0010;

    [StructLayout(LayoutKind.Sequential)]
    public struct MOUSEINPUT {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion {
        [FieldOffset(0)] public MOUSEINPUT mi;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT {
        public uint type;
        public InputUnion u;
    }

    private static void SendMouseEvent(uint flags) {
        INPUT input = new INPUT();
        input.type = INPUT_MOUSE;
        input.u.mi.dwFlags = flags;
        input.u.mi.dx = 0;
        input.u.mi.dy = 0;
        input.u.mi.mouseData = 0;
        input.u.mi.time = 0;
        input.u.mi.dwExtraInfo = IntPtr.Zero;
        INPUT[] inputs = new INPUT[] { input };
        SendInput(1, inputs, Marshal.SizeOf(typeof(INPUT)));
    }

    public static void LeftClick(int x, int y) {
        SetCursorPos(x, y);
        SendMouseEvent(MOUSEEVENTF_LEFTDOWN);
        SendMouseEvent(MOUSEEVENTF_LEFTUP);
    }

    public static void RightClick(int x, int y) {
        SetCursorPos(x, y);
        SendMouseEvent(MOUSEEVENTF_RIGHTDOWN);
        SendMouseEvent(MOUSEEVENTF_RIGHTUP);
    }

    public static void LeftDown(int x, int y) {
        SetCursorPos(x, y);
        SendMouseEvent(MOUSEEVENTF_LEFTDOWN);
    }

    public static void LeftUp(int x, int y) {
        SetCursorPos(x, y);
        SendMouseEvent(MOUSEEVENTF_LEFTUP);
    }
}
"@

# Validate coordinates
function Parse-Coords {
    Assert-UInt $RawX "x"
    Assert-UInt $RawY "y"
    $script:X = [int]$RawX
    $script:Y = [int]$RawY
}

switch ($Cmd) {
    "click" {
        Parse-Coords
        [Win32Mouse]::LeftClick($X, $Y)
        Write-Host "Clicked at $X,$Y"
    }

    "double-click" {
        Parse-Coords
        [Win32Mouse]::LeftClick($X, $Y)
        Start-Sleep -Milliseconds 50
        [Win32Mouse]::LeftClick($X, $Y)
        Write-Host "Double-clicked at $X,$Y"
    }

    "right-click" {
        Parse-Coords
        [Win32Mouse]::RightClick($X, $Y)
        Write-Host "Right-clicked at $X,$Y"
    }

    "move" {
        Parse-Coords
        [Win32Mouse]::SetCursorPos($X, $Y) | Out-Null
        Write-Host "Moved cursor to $X,$Y"
    }

    { $_ -in "help", "--help", "-h" } { Show-Usage }

    default {
        Write-Error "Unknown command: $Cmd"
        Show-Usage
        exit 1
    }
}
