# Agent OS — Configuration Module
#
# Import:
#   Import-Module "$PSScriptRoot/Config.psm1"
#
# Provides: config loading, validation, schema enforcement, run-config copy-on-write

function Get-OstwinConfig {
    <#
    .SYNOPSIS
        Loads and returns the full Agent OS configuration as a PSCustomObject.
    .PARAMETER ConfigPath
        Optional path to config.json. Defaults to AGENT_OS_CONFIG env var or .agents/config.json.
    #>
    [CmdletBinding()]
    param(
        [string]$ConfigPath = ''
    )

    if (-not $ConfigPath) {
        $ConfigPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
                      elseif ($env:AGENTS_DIR) { Join-Path $env:AGENTS_DIR "config.json" }
                      else {
                          $agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue).Path
                          Join-Path $agentsDir "config.json"
                      }
    }

    if (-not (Test-Path $ConfigPath)) {
        throw "Config file not found: $ConfigPath"
    }

    $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    return $config
}

function Test-OstwinConfig {
    <#
    .SYNOPSIS
        Validates a config object against required fields and returns validation results.
    .PARAMETER Config
        The config object (from Get-OstwinConfig).
    .OUTPUTS
        PSCustomObject with IsValid (bool) and Errors (string[]) properties.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [PSCustomObject]$Config
    )

    $errors = [System.Collections.Generic.List[string]]::new()

    # Required top-level fields
    if (-not $Config.version) { $errors.Add("Missing required field: version") }
    if (-not $Config.manager) { $errors.Add("Missing required section: manager") }
    if (-not $Config.engineer) { $errors.Add("Missing required section: engineer") }
    if (-not $Config.qa) { $errors.Add("Missing required section: qa") }
    if (-not $Config.channel) { $errors.Add("Missing required section: channel") }

    # Manager section
    if ($Config.manager) {
        if ($null -eq $Config.manager.poll_interval_seconds) {
            $errors.Add("Missing: manager.poll_interval_seconds")
        }
        elseif ($Config.manager.poll_interval_seconds -lt 1) {
            $errors.Add("manager.poll_interval_seconds must be >= 1")
        }

        if ($null -eq $Config.manager.max_concurrent_rooms) {
            $errors.Add("Missing: manager.max_concurrent_rooms")
        }
        elseif ($Config.manager.max_concurrent_rooms -lt 1) {
            $errors.Add("manager.max_concurrent_rooms must be >= 1")
        }

        if ($null -eq $Config.manager.max_engineer_retries) {
            $errors.Add("Missing: manager.max_engineer_retries")
        }
    }

    # Engineer section
    if ($Config.engineer) {
        if (-not $Config.engineer.cli) { $errors.Add("Missing: engineer.cli") }
        if (-not $Config.engineer.default_model) { $errors.Add("Missing: engineer.default_model") }
        if ($null -eq $Config.engineer.timeout_seconds) { $errors.Add("Missing: engineer.timeout_seconds") }
    }

    # QA section
    if ($Config.qa) {
        if (-not $Config.qa.cli) { $errors.Add("Missing: qa.cli") }
        if ($null -eq $Config.qa.timeout_seconds) { $errors.Add("Missing: qa.timeout_seconds") }
    }

    # Channel section
    if ($Config.channel) {
        if (-not $Config.channel.format) { $errors.Add("Missing: channel.format") }
    }

    return [PSCustomObject]@{
        IsValid = ($errors.Count -eq 0)
        Errors  = $errors.ToArray()
    }
}

function New-RunConfig {
    <#
    .SYNOPSIS
        Creates a copy-on-write run config from the base config.json, applying overrides.
    .PARAMETER ConfigPath
        Path to the base config.json.
    .PARAMETER OutputPath
        Path to write the run config.
    .PARAMETER Overrides
        Hashtable of dot-separated key paths to new values.
    .EXAMPLE
        New-RunConfig -ConfigPath ".agents/config.json" -OutputPath ".agents/config.run.json" `
                      -Overrides @{ "manager.max_concurrent_rooms" = 10 }
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ConfigPath,

        [Parameter(Mandatory)]
        [string]$OutputPath,

        [hashtable]$Overrides = @{}
    )

    if (-not (Test-Path $ConfigPath)) {
        throw "Base config not found: $ConfigPath"
    }

    $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

    # Apply overrides
    foreach ($key in $Overrides.Keys) {
        $parts = $key.Split('.')
        $current = $config

        for ($i = 0; $i -lt $parts.Count - 1; $i++) {
            $current = $current.($parts[$i])
            if ($null -eq $current) {
                throw "Override key path invalid: '$key' — '$($parts[$i])' not found"
            }
        }

        $lastKey = $parts[-1]
        $current | Add-Member -MemberType NoteProperty -Name $lastKey -Value $Overrides[$key] -Force
    }

    $config | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputPath -Encoding utf8

    return $OutputPath
}

Export-ModuleMember -Function Get-OstwinConfig, Test-OstwinConfig, New-RunConfig
