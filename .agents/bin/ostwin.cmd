@echo off
REM ostwin.cmd - Thin CMD wrapper for the extensionless ostwin PowerShell CLI.
REM Forwards all arguments to the PowerShell CLI script.
REM
REM Usage from cmd.exe or Windows Terminal:
REM   ostwin run plans/my-feature.md
REM   ostwin status --watch
REM   ostwin --help
REM
REM Requires: PowerShell 7+ (pwsh) installed and on PATH.
REM   Install: https://aka.ms/install-powershell

set "OSTWIN_CLI=%~dp0ostwin"

where pwsh >nul 2>&1
if %errorlevel% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -Command "$script = [scriptblock]::Create((Get-Content -Raw -LiteralPath $env:OSTWIN_CLI)); & $script @args" %*
    exit /b %errorlevel%
)

echo [ERROR] PowerShell 7+ (pwsh) not found. Install from: https://aka.ms/install-powershell
exit /b 1
