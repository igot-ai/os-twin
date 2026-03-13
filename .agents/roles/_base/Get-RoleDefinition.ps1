<#
.SYNOPSIS
    Loads and validates a role definition from role.yaml.

.DESCRIPTION
    Reads a role.yaml (or role.json) file and returns a structured role object
    with name, capabilities, prompt template, quality gates, and skills.

    This enables the extensible role engine — new roles are added by creating
    a new directory with a role.yaml file, no code changes needed.

.PARAMETER RolePath
    Path to the role directory containing role.yaml.
.PARAMETER RoleName
    Role name to resolve from the standard roles/ directory.
    Used when RolePath is not specified.

.OUTPUTS
    PSCustomObject with Name, Description, Capabilities, PromptTemplate, QualityGates, Skills

.EXAMPLE
    $role = ./Get-RoleDefinition.ps1 -RolePath "./roles/engineer"
    $role = ./Get-RoleDefinition.ps1 -RoleName "qa"
#>
[CmdletBinding()]
param(
    [string]$RolePath = '',
    [string]$RoleName = ''
)

# --- Resolve role path ---
if (-not $RolePath -and $RoleName) {
    $rolesDir = (Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue).Path
    $RolePath = Join-Path $rolesDir $RoleName
}

if (-not $RolePath -or -not (Test-Path $RolePath)) {
    Write-Error "Role path not found: $RolePath"
    exit 1
}

# --- Load role definition ---
$roleFile = $null
$roleData = $null

# Try role.yaml first (via PowerShell YAML module or simple parser)
$yamlFile = Join-Path $RolePath "role.yaml"
$jsonFile = Join-Path $RolePath "role.json"

if (Test-Path $jsonFile) {
    $roleFile = $jsonFile
    $roleData = Get-Content $jsonFile -Raw | ConvertFrom-Json
}
elseif (Test-Path $yamlFile) {
    # Simple YAML parser for flat role definitions
    $roleFile = $yamlFile
    $yamlContent = Get-Content $yamlFile -Raw
    $roleData = ConvertFrom-SimpleYaml -Content $yamlContent
}
else {
    # Generate a default role definition from ROLE.md if it exists
    $roleMd = Join-Path $RolePath "ROLE.md"
    $displayName = if ($RoleName) { $RoleName } else { Split-Path $RolePath -Leaf }

    $roleData = [PSCustomObject]@{
        name         = $displayName
        description  = if (Test-Path $roleMd) { (Get-Content $roleMd -TotalCount 1) -replace '^#\s*', '' } else { "$displayName role" }
        capabilities = @("code-generation", "file-editing", "shell-execution")
        prompt_file  = if (Test-Path $roleMd) { "ROLE.md" } else { $null }
        quality_gates = @()
        skills       = @()
        cli          = "deepagents"
        model        = $null
        timeout      = 600
    }
}

# --- Simple YAML parser (handles flat + 1-level nested + arrays) ---
function ConvertFrom-SimpleYaml {
    param([string]$Content)

    $result = @{}
    $currentKey = $null
    $currentArray = $null

    foreach ($line in ($Content -split "`n")) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }

        # Array item
        if ($trimmed -match '^-\s+(.+)$') {
            if ($currentArray) {
                $currentArray += $Matches[1].Trim().Trim('"', "'")
                $result[$currentKey] = $currentArray
            }
            continue
        }

        # Key: value
        if ($trimmed -match '^(\w+)\s*:\s*(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim().Trim('"', "'")

            if (-not $value) {
                # Start of array or nested object
                $currentKey = $key
                $currentArray = @()
                $result[$key] = @()
            }
            else {
                $currentKey = $null
                $currentArray = $null

                # Type coercion
                if ($value -eq 'true') { $result[$key] = $true }
                elseif ($value -eq 'false') { $result[$key] = $false }
                elseif ($value -match '^\d+$') { $result[$key] = [int]$value }
                else { $result[$key] = $value }
            }
        }
    }

    return [PSCustomObject]$result
}

# --- Validate required fields ---
$name = if ($roleData.name) { $roleData.name }
        elseif ($RoleName) { $RoleName }
        else { Split-Path $RolePath -Leaf }

# --- Build the normalized role object ---
$role = [PSCustomObject]@{
    Name          = $name
    Description   = if ($roleData.description) { $roleData.description } else { "$name role" }
    Capabilities  = if ($roleData.capabilities) { @($roleData.capabilities) } else { @("code-generation") }
    PromptFile    = if ($roleData.prompt_file) { Join-Path $RolePath $roleData.prompt_file } else { $null }
    PromptTemplate = $null
    QualityGates  = if ($roleData.quality_gates) { @($roleData.quality_gates) } else { @() }
    Skills        = if ($roleData.skills) { @($roleData.skills) } else { @() }
    CLI           = if ($roleData.cli) { $roleData.cli } else { "deepagents" }
    Model         = $roleData.model
    Timeout       = if ($roleData.timeout) { $roleData.timeout } else { 600 }
    RolePath      = $RolePath
    SourceFile    = $roleFile
}

# --- Load prompt template ---
if ($role.PromptFile -and (Test-Path $role.PromptFile)) {
    $role.PromptTemplate = Get-Content $role.PromptFile -Raw
}

Write-Output $role
