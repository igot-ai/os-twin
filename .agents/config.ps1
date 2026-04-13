<#
.SYNOPSIS
    Agent OS — Configuration Manager (PowerShell port of config.sh)

.DESCRIPTION
    View and update Agent OS configuration.

.PARAMETER Get
    Get a specific config value by dot-notation key.

.PARAMETER Set
    Set a config key (requires Value parameter).

.PARAMETER Value
    Value to set (used with -Set).

.PARAMETER Help
    Show help text.

.EXAMPLE
    .\config.ps1                                       # Show full config
    .\config.ps1 -Get manager.poll_interval_seconds    # Get a value
    .\config.ps1 -Set manager.max_concurrent_rooms -Value 10  # Set a value
#>
[CmdletBinding()]
param(
    [string]$Get,

    [string]$Set,

    [string]$Value,

    [Alias('h')]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: config.ps1 [-Get KEY] [-Set KEY -Value VALUE]"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  config.ps1                                       # Show full config"
    Write-Host "  config.ps1 -Get manager.poll_interval_seconds"
    Write-Host "  config.ps1 -Set manager.max_concurrent_rooms -Value 10"
    Write-Host ""
    Write-Host "Keys use dot notation: manager.poll_interval_seconds"
    exit 0
}

$ScriptDir = Split-Path $PSCommandPath -Parent
$AgentsDir = $ScriptDir
$ConfigFile = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG } else { Join-Path $AgentsDir "config.json" }

if (-not (Test-Path $ConfigFile)) {
    Write-Error "[ERROR] Config file not found: $ConfigFile"
    exit 1
}

# ─── Helper: navigate JSON by dot-notation key ──────────────────────────────

function Get-JsonValue {
    param(
        [PSObject]$Object,
        [string]$Key
    )
    $keys = $Key -split '\.'
    $current = $Object
    foreach ($k in $keys) {
        if ($current.PSObject.Properties[$k]) {
            $current = $current.$k
        }
        else {
            throw "Key not found: $Key"
        }
    }
    return $current
}

function Set-JsonValue {
    param(
        [PSObject]$Object,
        [string]$Key,
        [object]$NewValue
    )
    $keys = $Key -split '\.'
    $current = $Object
    for ($i = 0; $i -lt $keys.Count - 1; $i++) {
        $k = $keys[$i]
        if ($current.PSObject.Properties[$k]) {
            $current = $current.$k
        }
        else {
            throw "Key not found: $Key"
        }
    }
    $lastKey = $keys[-1]

    # Try to parse value as number or boolean
    $parsedValue = $NewValue
    if ($NewValue -match '^\d+$') {
        $parsedValue = [int]$NewValue
    }
    elseif ($NewValue -match '^\d+\.\d+$') {
        $parsedValue = [double]$NewValue
    }
    elseif ($NewValue -ieq 'true') {
        $parsedValue = $true
    }
    elseif ($NewValue -ieq 'false') {
        $parsedValue = $false
    }

    if ($current.PSObject.Properties[$lastKey]) {
        $current.$lastKey = $parsedValue
    }
    else {
        $current | Add-Member -NotePropertyName $lastKey -NotePropertyValue $parsedValue -Force
    }
}

# ─── Mode: Print full config ────────────────────────────────────────────────

if (-not $Get -and -not $Set) {
    $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    $config | ConvertTo-Json -Depth 10
    exit 0
}

# ─── Mode: Get a value ──────────────────────────────────────────────────────

if ($Get) {
    try {
        $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $val = Get-JsonValue -Object $config -Key $Get
        if ($val -is [PSObject] -or $val -is [System.Collections.IDictionary]) {
            $val | ConvertTo-Json -Depth 10
        }
        else {
            Write-Host $val
        }
    }
    catch {
        Write-Error "[ERROR] Key not found: $Get"
        exit 1
    }
    exit 0
}

# ─── Mode: Set a value ──────────────────────────────────────────────────────

if ($Set) {
    if (-not $Value -and $Value -ne "0" -and $Value -ne "" -and $Value -ne "false") {
        Write-Error "[ERROR] -Value is required when using -Set"
        exit 1
    }
    try {
        $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        Set-JsonValue -Object $config -Key $Set -NewValue $Value
        $config | ConvertTo-Json -Depth 10 | Set-Content -Path $ConfigFile -Encoding UTF8
        Write-Host "Set $Set = $Value"
    }
    catch {
        Write-Error "[ERROR] Failed to set: $Set = $Value ($_)"
        exit 1
    }
    exit 0
}
