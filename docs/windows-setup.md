# Windows Setup Guide for Ostwin

This guide covers everything you need to run Ostwin on Windows.

## Quick Start

### Option 1: PowerShell 7 (Recommended)

PowerShell 7 has native UTF-8 support:

```powershell
# Install PowerShell 7
winget install Microsoft.PowerShell

# Run the installer
pwsh -File .\.agents\install.ps1
```

### Option 2: Pre-Flight Commands

Before running `install.ps1`, set UTF-8 encoding:

```powershell
# Set UTF-8 encoding
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Run installer
.\.agents\install.ps1
```

### Option 3: One-Liner

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & '.\.agents\install.ps1'"
```

---

## System-Wide UTF-8 Setup (Permanent)

Run once as Administrator, then restart:

```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File .agents\Setup-WindowsEnvironment.ps1 -AutoFix

# Restart computer when prompted

# After restart, use normally:
.\install.ps1
```

This enables system-wide UTF-8 support (Windows 10 1903+ / Windows 11).

---

## Understanding UTF-8 on Windows

### Why It Matters

Ostwin uses Unicode characters for:
- Box-drawing characters (`-`, `=`, `|`, `+`)
- Status indicators (`[OK]`, `[X]`, `[!]`)
- Special symbols

Windows PowerShell 5.1 (default) doesn't use UTF-8 by default, causing:
- Parser errors
- Garbled output
- Script failures

### The Encoding Commands

| Command | Purpose |
|---------|---------|
| `chcp 65001` | Set console code page to UTF-8 |
| `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` | Output encoding |
| `[Console]::InputEncoding = [System.Text.Encoding]::UTF8` | Input encoding |
| `$OutputEncoding = [System.Text.Encoding]::UTF8` | Pipeline encoding |

---

## Verification

Test that UTF-8 works:

```powershell
[Console]::OutputEncoding.EncodingName
# Should output: Unicode (UTF-8)

Write-Host "Test: --- === [OK] [X] [!]"
# Should display correctly
```

---

## Troubleshooting

### "Scripts disabled" Error

```powershell
# Option 1: Use bypass flag
powershell -ExecutionPolicy Bypass -File .\.agents\install.ps1

# Option 2: Change policy permanently
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

### Garbled Characters

1. Ensure UTF-8 commands are run before the installer
2. Or install PowerShell 7: `winget install Microsoft.PowerShell`

### "Parser Error" / "Unexpected Token"

Set encoding before the script is parsed:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
.\.agents\install.ps1
```

---

## Compatibility

| Windows Version | Pre-Flight Commands | System UTF-8 | PowerShell 7 |
|----------------|---------------------|--------------|--------------|
| Windows 11 | Yes | Yes | Yes |
| Windows 10 (1903+) | Yes | Yes | Yes |
| Windows 10 (pre-1903) | Yes | Console only | Yes |
| Windows 8.1/8 | Yes | Console only | Yes |
| Windows 7 | Yes | No | Manual install |

---

## What Gets Installed

After successful installation:
- `~\.ostwin\` - Main installation directory
- `ostwin` command available in new PowerShell windows
- Dashboard running at http://localhost:3366
- Python virtual environment with all dependencies

---

## Summary

| Method | Duration | Restart Required | Best For |
|--------|----------|------------------|----------|
| PowerShell 7 | Permanent | No | Developers (Recommended) |
| Pre-Flight Commands | Session only | No | Quick use |
| System UTF-8 | Permanent | Yes | Regular users |
