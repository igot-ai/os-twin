@echo off
REM ostwin.cmd — Thin CMD wrapper for ostwin.ps1
REM Forwards all arguments to the PowerShell CLI script.
REM
REM Usage from cmd.exe or Windows Terminal:
REM   ostwin run plans/my-feature.md
REM   ostwin status --watch
REM   ostwin --help
REM
REM Requires: PowerShell 7+ (pwsh) installed and on PATH.
REM   Install: https://aka.ms/install-powershell

REM Try pwsh (PowerShell 7+) first; fall back to powershell.exe (5.1)
where pwsh >nul 2>&1
if %errorlevel% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0ostwin.ps1" %*
    exit /b %errorlevel%
)

where powershell >nul 2>&1
if %errorlevel% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ostwin.ps1" %*
    exit /b %errorlevel%
)

echo [ERROR] PowerShell not found. Install from: https://aka.ms/install-powershell
exit /b 1
