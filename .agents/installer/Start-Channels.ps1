# ──────────────────────────────────────────────────────────────────────────────
# Start-Channels.ps1 — Channel connector install + launch (Telegram, Discord, Slack)
#
# Provides: Install-Channels, Start-Channels
#
# Requires: Lib.ps1, Check-Deps.ps1 (Check-Node),
#           globals: $script:InstallDir, $script:SourceDir, $script:ScriptDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_StartChannelsPs1Loaded) { return }
$script:_StartChannelsPs1Loaded = $true

function Install-Channels {
    [CmdletBinding()]
    param()

    # Locate the channel connector directory
    $script:ChanDir = ""
    $candidates = @(
        (Join-Path $script:SourceDir "bot"),
        (Join-Path (Split-Path $script:ScriptDir -Parent) "bot")
    )

    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c) -and (Test-Path (Join-Path $c "package.json"))) {
            $script:ChanDir = (Resolve-Path $c).Path
            break
        }
    }

    if (-not $script:ChanDir) {
        Write-Warn "Channel connector dir (bot/) not found — skipping"
        Write-Info "Expected at bot\package.json relative to the repo root"
        return
    }

    if (-not (Check-Node)) {
        Write-Warn "Node.js not found — cannot install channel connectors"
        Write-Info "Install Node.js and re-run"
        return
    }

    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
        Write-Warn "pnpm not found — cannot install channel connectors"
        Write-Info "Install pnpm and re-run"
        return
    }

    Write-Step "Installing channel dependencies in $($script:ChanDir) with pnpm..."
    $originalDir = Get-Location
    try {
        Set-Location $script:ChanDir
        & pnpm install
        Write-Ok "Channel dependencies installed"
    }
    catch {
        Write-Warn "Channel dependency install failed: $_"
    }
    finally {
        Set-Location $originalDir
    }

    # Check tsx availability
    $tsxPath = Join-Path $script:ChanDir "node_modules\.bin\tsx.cmd"
    if (-not (Test-Path $tsxPath)) {
        Write-Warn "tsx not found after pnpm install"
    }
    else {
        Write-Ok "tsx available"
    }

    Write-Ok "Channel connector dir: $($script:ChanDir)"
}

function Start-Channels {
    [CmdletBinding()]
    param()

    if (-not $script:ChanDir) { return }

    # Load .env
    $envFile = Join-Path $script:InstallDir ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
            }
        }
    }

    # Load project root .env
    $projectRootEnv = Join-Path (Split-Path $script:ChanDir -Parent) ".env"
    if (Test-Path $projectRootEnv) {
        Get-Content $projectRootEnv | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
            }
        }
    }

    # Stop previous channel process
    $chanPidFile = Join-Path $script:InstallDir ".agents\channel.pid"
    if (Test-Path $chanPidFile) {
        $oldPid = Get-Content $chanPidFile -ErrorAction SilentlyContinue
        if ($oldPid) {
            try {
                $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Step "Stopping previous channel process (PID $oldPid)..."
                    Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Seconds 1
                }
            }
            catch { }
        }
    }

    # Register Discord slash commands if configured
    if ($env:DISCORD_TOKEN -and $env:DISCORD_CLIENT_ID) {
        Write-Step "Registering Discord slash commands..."
        $originalDir = Get-Location
        try {
            Set-Location $script:ChanDir
            & npx tsx src/deploy-commands.ts 2>$null
            Write-Ok "Discord commands registered"
        }
        catch {
            Write-Warn "Discord command registration failed (non-critical)"
        }
        finally {
            Set-Location $originalDir
        }
    }

    $logsDir = Join-Path $script:InstallDir "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    }

    Write-Step "Starting channels from $($script:ChanDir)..."
    $chanLogFile = Join-Path $logsDir "channel.log"

    $chanProcess = Start-Process -FilePath "npm" `
        -ArgumentList "start" `
        -WorkingDirectory $script:ChanDir `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $chanLogFile `
        -RedirectStandardError (Join-Path $logsDir "channel-error.log")

    $chanPid = $chanProcess.Id
    Set-Content -Path $chanPidFile -Value $chanPid -NoNewline
    Write-Ok "Channels started (PID $chanPid) — log: $chanLogFile"

    if ($env:TELEGRAM_BOT_TOKEN) { Write-Ok "Telegram: enabled" } else { Write-Info "Telegram: disabled (set TELEGRAM_BOT_TOKEN)" }
    if ($env:DISCORD_TOKEN) { Write-Ok "Discord: enabled" } else { Write-Info "Discord: disabled (set DISCORD_TOKEN)" }
    if ($env:SLACK_BOT_TOKEN) { Write-Ok "Slack: enabled" } else { Write-Info "Slack: disabled (set SLACK_BOT_TOKEN)" }
}
