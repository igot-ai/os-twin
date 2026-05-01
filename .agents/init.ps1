<#
.SYNOPSIS
    Agent OS — MCP Initialization (PowerShell port of init.sh)

.DESCRIPTION
    Sets up the per-project MCP configuration and optionally installs
    MCP extensions from the catalog.

.PARAMETER TargetDir
    Directory to initialize. Defaults to current directory.

.PARAMETER Yes
    Non-interactive mode — auto-approve all prompts.

.PARAMETER Help
    Show help text.

.EXAMPLE
    .\init.ps1 ~/my-project
    .\init.ps1 ~/my-project -Yes
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$TargetDir = ".",

    [Alias('y')]
    [switch]$Yes,

    [Alias('h')]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $PSCommandPath -Detailed
    exit 0
}

$ScriptDir = Split-Path $PSCommandPath -Parent
$TargetAgents = Join-Path $TargetDir ".agents"

# ─── Helper functions ─────────────────────────────────────────────────────────

function Write-Ok    { param([string]$Msg) Write-Host "    [OK] $Msg" }
function Write-Warn  { param([string]$Msg) Write-Host "    [WARN] $Msg" }
function Write-Fail  { param([string]$Msg) Write-Host "    [FAIL] $Msg" }
function Write-Info  { param([string]$Msg) Write-Host "    $Msg" }
function Write-Step  { param([string]$Msg) Write-Host "  -> $Msg" }

function Invoke-Ask {
    param([string]$Prompt)
    if ($Yes) { return $true }
    $answer = Read-Host "    ? $Prompt [Y/n]"
    return (-not $answer -or $answer -match '^[Yy]')
}

# ─── Banner ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  +==================================================+"
Write-Host "  |          Ostwin -- MCP Configuration              |"
Write-Host "  +==================================================+"
Write-Host ""
Write-Host "  Project: $TargetDir"
Write-Host ""

# ─── Ensure .agents/mcp exists ────────────────────────────────────────────────

Write-Step "Scaffolding MCP directory..."

if (-not (Test-Path $TargetAgents)) { New-Item -ItemType Directory -Path $TargetAgents -Force | Out-Null }
$mcpDir = Join-Path $TargetAgents "mcp"
if (-not (Test-Path $mcpDir)) { New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null }

# Seed extensions.json if not present
$extensionsFile = Join-Path $mcpDir "extensions.json"
if (-not (Test-Path $extensionsFile)) {
    '{"extensions":[]}' | Set-Content -Path $extensionsFile -Encoding UTF8
}

# Copy catalog from source if not present or outdated
$srcCatalog = Join-Path $ScriptDir "mcp" "mcp-catalog.json"
if (Test-Path $srcCatalog) {
    Copy-Item -Path $srcCatalog -Destination (Join-Path $mcpDir "mcp-catalog.json") -Force -ErrorAction SilentlyContinue
}

# Copy builtin config from source
$srcBuiltin = Join-Path $ScriptDir "mcp" "mcp-builtin.json"
if (Test-Path $srcBuiltin) {
    Copy-Item -Path $srcBuiltin -Destination (Join-Path $mcpDir "mcp-builtin.json") -Force -ErrorAction SilentlyContinue
}

# Copy extension manager script
$srcExtScript = Join-Path $ScriptDir "mcp" "mcp-extension.sh"
if (Test-Path $srcExtScript) {
    $dstExtScript = Join-Path $mcpDir "mcp-extension.sh"
    $srcResolved = (Resolve-Path $srcExtScript -ErrorAction SilentlyContinue).Path ?? $srcExtScript
    $dstResolved = $dstExtScript
    if (Test-Path $dstExtScript) { $dstResolved = (Resolve-Path $dstExtScript -ErrorAction SilentlyContinue).Path ?? $dstExtScript }
    if ($srcResolved -ne $dstResolved) {
        Copy-Item -Path $srcExtScript -Destination $dstExtScript -Force
    }
}

# Copy vault.py and config_resolver.py
foreach ($pyFile in @("vault.py", "config_resolver.py")) {
    $srcPy = Join-Path $ScriptDir "mcp" $pyFile
    if (Test-Path $srcPy) {
        Copy-Item -Path $srcPy -Destination (Join-Path $mcpDir $pyFile) -Force -ErrorAction SilentlyContinue
    }
}

$ProjectMcpConfig = Join-Path $mcpDir "config.json"
$LegacyConfig = Join-Path $mcpDir "mcp-config.json"

if (-not (Test-Path $ProjectMcpConfig)) {
    $srcMcpConfig = Join-Path $ScriptDir "mcp" "mcp-config.json"
    $builtinConfig = Join-Path $mcpDir "mcp-builtin.json"

    if (Test-Path $srcMcpConfig) {
        Copy-Item -Path $srcMcpConfig -Destination $ProjectMcpConfig -Force
    }
    elseif (Test-Path $LegacyConfig) {
        Copy-Item -Path $LegacyConfig -Destination $ProjectMcpConfig -Force
    }
    elseif (Test-Path $builtinConfig) {
        Copy-Item -Path $builtinConfig -Destination $ProjectMcpConfig -Force
    }
    else {
        '{"mcp":{}}' | Set-Content -Path $ProjectMcpConfig -Encoding UTF8
    }
    Write-Ok "MCP config seeded"
}
else {
    Write-Ok "MCP config exists (will recompile)"
}

Write-Info "Config: $ProjectMcpConfig"

# ─── Global MCP config ───────────────────────────────────────────────────────

$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$GlobalMcpDir = Join-Path $HomeDir ".ostwin" ".agents" "mcp"
$GlobalMcpConfig = Join-Path $GlobalMcpDir "config.json"

if (-not (Test-Path $GlobalMcpDir)) { New-Item -ItemType Directory -Path $GlobalMcpDir -Force | Out-Null }

if (-not (Test-Path $GlobalMcpConfig)) {
    $globalBuiltin = Join-Path $GlobalMcpDir "mcp-builtin.json"
    if (Test-Path $globalBuiltin) {
        Copy-Item -Path $globalBuiltin -Destination $GlobalMcpConfig -Force
    }
    else {
        '{"mcp":{}}' | Set-Content -Path $GlobalMcpConfig -Encoding UTF8
    }
    Write-Ok "Global MCP config created at $GlobalMcpConfig"
}
else {
    Write-Ok "Global MCP config exists (preserved)"
}

# ─── Compile opencode.json ────────────────────────────────────────────────────

$McpExtensionScript = Join-Path $ScriptDir "mcp" "mcp-extension.sh"
if ((Test-Path $McpExtensionScript) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
    Write-Step "Compiling project-level MCP config..."
    & bash $McpExtensionScript --project-dir $TargetDir compile
}

# ─── Sync MCP to global ~/.config/opencode/opencode.json ─────────────────────
# After compiling the project-local config, also update the global opencode
# config so tools running outside a project context see the latest MCP servers
# with resolved API keys (e.g. knowledge server's OSTWIN_API_KEY).

$ResolveScript = Join-Path $ScriptDir "mcp" "resolve_opencode.py"
$CompiledConfig = Join-Path $TargetAgents "mcp" "config.json"
$GlobalOpencodeDir = if ($env:XDG_CONFIG_HOME) { Join-Path $env:XDG_CONFIG_HOME "opencode" } else { Join-Path $HOME ".config" "opencode" }

if ((Test-Path $ResolveScript) -and (Test-Path $CompiledConfig)) {
    Write-Step "Syncing MCP config to global opencode.json..."

    # Collect env files for resolution: project .env and .env.mcp
    $envArgs = @()
    $projectEnv = Join-Path $TargetDir ".env"
    $mcpEnv = Join-Path $TargetAgents "mcp" ".env.mcp"
    if (Test-Path $projectEnv)  { $envArgs = @("--env-file", $projectEnv) }
    elseif (Test-Path $mcpEnv) { $envArgs = @("--env-file", $mcpEnv) }

    # Find python: prefer venv, fall back to system
    $pythonCmd = "python3"
    $globalVenvPython = Join-Path $HOME ".ostwin" "venv" "bin" "python"
    if (Test-Path $globalVenvPython) { $pythonCmd = $globalVenvPython }

    & $pythonCmd $ResolveScript $CompiledConfig $GlobalOpencodeDir @envArgs --merge
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Global opencode.json synced at $GlobalOpencodeDir"
    } else {
        Write-Warn "Failed to sync global opencode.json (non-critical)"
    }
}

# ─── Update .gitignore ────────────────────────────────────────────────────────

$Gitignore = Join-Path $TargetDir ".gitignore"

$OstwinBlock = @"
# Ostwin generated
.opencode/opencode.json
.war-rooms/
.agents/*
!.agents/memory/
"@

if (Test-Path $Gitignore) {
    $content = Get-Content $Gitignore -Raw
    if ($content -match '# Ostwin generated') {
        # Remove existing Ostwin block and re-add
        $lines = Get-Content $Gitignore
        $filtered = $lines | Where-Object {
            $_ -ne '# Ostwin generated' -and
            $_ -ne '.opencode/opencode.json' -and
            $_ -ne '.war-rooms/' -and
            $_ -ne '.agents/*' -and
            $_ -ne '!.agents/memory/' -and
            $_ -ne '.agents/'
        }
        # Remove trailing blank lines
        while ($filtered.Count -gt 0 -and [string]::IsNullOrWhiteSpace($filtered[-1])) {
            $filtered = $filtered[0..($filtered.Count - 2)]
        }
        $filtered += ""
        $filtered += $OstwinBlock -split "`n"
        $filtered | Set-Content -Path $Gitignore -Encoding UTF8
        Write-Ok "Updated Ostwin entries in .gitignore"
    }
    else {
        Add-Content -Path $Gitignore -Value "`n$OstwinBlock" -Encoding UTF8
        Write-Ok "Added Ostwin entries to .gitignore"
    }
}
else {
    $OstwinBlock | Set-Content -Path $Gitignore -Encoding UTF8
    Write-Ok "Created .gitignore with Ostwin entries"
}

# ─── Summary ─────────────────────────────────────────────────────────────────

$OpencodeConfig = Join-Path $TargetDir ".opencode" "opencode.json"
Write-Host ""
Write-Host "  [OK] MCP configured at: $OpencodeConfig"
Write-Host ""
Write-Host "  Manage extensions:"
Write-Host "    ostwin mcp catalog              Show available packages"
Write-Host "    ostwin mcp install <name>       Install an extension"
Write-Host "    ostwin mcp list                 Show installed extensions"
Write-Host "    ostwin mcp sync                 Rebuild config.json"
Write-Host ""
