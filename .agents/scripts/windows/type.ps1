# type.ps1 — Windows keyboard input simulation via SendKeys and keybd_event
# Usage: type.ps1 <cmd> [args]
# Requires: PowerShell 5.1+, Windows
param(
    [Parameter(Position=0)][string]$Cmd = "help",
    [Parameter(Position=1)][string]$Arg1 = "",
    [Parameter(Position=2)][string]$Arg2 = "",
    [Parameter(Position=3,ValueFromRemainingArguments=$true)][string[]]$Rest = @()
)

. "$PSScriptRoot\_lib.ps1"

function Show-Usage {
    @"
Usage: type.ps1 <cmd> [args]

Commands:
  text <string>                   Type a string of text
  key <keycode>                   Press a virtual key code (decimal)
  combo <key> [mod mod ...]       Key + modifiers (ctrl, alt, shift, win)
  hold <keycode> <ms>             Hold a key for N milliseconds
  help                            Show this help

Examples:
  type.ps1 text "Hello, World!"
  type.ps1 key 13                  # Enter (VK_RETURN)
  type.ps1 key 27                  # Escape (VK_ESCAPE)
  type.ps1 combo c ctrl            # Ctrl+C
  type.ps1 combo z ctrl            # Ctrl+Z
  type.ps1 hold 32 500             # Hold Space 500ms

Common VK codes: 8=Back 9=Tab 13=Enter 27=Esc 32=Space 37=Left 38=Up 39=Right 40=Down
"@ | Write-Host
}

Add-TypeSafe -TypeName "Win32Key" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32Key {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public static void KeyDown(byte vk) { keybd_event(vk, 0, 0, UIntPtr.Zero); }
    public static void KeyUp(byte vk)   { keybd_event(vk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero); }
}
"@

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

# VK codes for modifiers
$MOD_VK = @{ ctrl=0x11; control=0x11; alt=0x12; option=0x12; shift=0x10; win=0x5B }

switch ($Cmd) {
    "text" {
        Assert-NonEmpty $Arg1 "string"
        [System.Windows.Forms.SendKeys]::SendWait($Arg1)
        Write-Host "Typed: $Arg1"
    }

    "key" {
        Assert-NonEmpty $Arg1 "keycode"
        Assert-UInt $Arg1 "keycode"
        $vk = [byte][int]$Arg1
        [Win32Key]::KeyDown($vk)
        Start-Sleep -Milliseconds 30
        [Win32Key]::KeyUp($vk)
        Write-Host "Key: $Arg1"
    }

    "combo" {
        Assert-NonEmpty $Arg1 "key"
        $key = $Arg1
        $mods = @($Arg2) + $Rest | Where-Object { $_ -ne "" }
        # Press modifiers down
        foreach ($mod in $mods) {
            $vkMod = $MOD_VK[$mod.ToLower()]
            if (-not $vkMod) { Write-Error "Unknown modifier: $mod (valid: ctrl, alt, shift, win)"; exit 1 }
            [Win32Key]::KeyDown([byte]$vkMod)
        }
        # Press and release the key
        [System.Windows.Forms.SendKeys]::SendWait($key)
        # Release modifiers in reverse order
        [array]::Reverse($mods)
        foreach ($mod in $mods) {
            $vkMod = $MOD_VK[$mod.ToLower()]
            [Win32Key]::KeyUp([byte]$vkMod)
        }
        Write-Host "Combo: $key + ($($mods -join ', '))"
    }

    "hold" {
        Assert-NonEmpty $Arg1 "keycode"
        Assert-UInt $Arg1 "keycode"
        Assert-NonEmpty $Arg2 "duration"
        Assert-UInt $Arg2 "duration"
        $vk = [byte][int]$Arg1
        $ms = [int]$Arg2
        [Win32Key]::KeyDown($vk)
        Start-Sleep -Milliseconds $ms
        [Win32Key]::KeyUp($vk)
        Write-Host "Held key $Arg1 for ${ms}ms"
    }

    { $_ -in "help", "--help", "-h" } { Show-Usage }

    default {
        Write-Error "Unknown command: $Cmd"
        Show-Usage
        exit 1
    }
}
