<#
.SYNOPSIS
    Fast role scaffolding — creates role.json + ROLE.md on disk for dynamic roles.

.DESCRIPTION
    Pure-PowerShell scaffolding (no LLM call). Creates role artifacts so that
    Tier 2 filesystem discovery in Resolve-Role.ps1 can find the role on
    subsequent lookups. Idempotent — skips if role.json already exists.

.PARAMETER RoleName
    The role identifier (e.g., "security-auditor", "database-architect").
.PARAMETER AgentsDir
    Path to the .agents directory.
.PARAMETER Description
    One-line role description.
.PARAMETER Capabilities
    Array of capability strings.
.PARAMETER Skills
    Array of skill strings.
.PARAMETER Model
    LLM model to use. Default: google-vertex/gemini-3-flash-preview.
.PARAMETER Timeout
    Timeout in seconds. Default: 600.
.PARAMETER CLI
    CLI tool to use. Default: deepagents.
.PARAMETER PromptContent
    Content for ROLE.md (the role's system prompt template).

.OUTPUTS
    [string] Path to the created role directory.

.EXAMPLE
    ./New-DynamicRole.ps1 -RoleName "security-auditor" -AgentsDir "./.agents" `
        -Description "Reviews code for security vulnerabilities" `
        -Capabilities @("security-review", "code-review") `
        -PromptContent "# Security Auditor`n`nYou review code for OWASP vulnerabilities..."
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoleName,

    [Parameter(Mandatory)]
    [string]$AgentsDir,

    [string]$Description = '',
    [string[]]$Capabilities = @(),
    [string[]]$Skills = @(),
    [string]$Model = 'google-vertex/gemini-3-flash-preview',
    [int]$Timeout = 600,
    [string]$CLI = 'agent',
    [string]$InstanceType = 'worker',
    [string]$PromptContent = ''
)

# --- Sanitize role name (kebab-case, no special chars) ---
$safeName = $RoleName -replace '[^a-zA-Z0-9\-]', '-' -replace '-+', '-' -replace '^-|-$', ''
if (-not $safeName) {
    Write-Error "Invalid role name: $RoleName"
    exit 1
}

$roleDir = Join-Path $AgentsDir "roles" $safeName

# Prefer contributes/roles/ for new dynamic roles (keep .agents/roles/ for builtins)
$projectRoot = (Resolve-Path (Join-Path $AgentsDir "..") -ErrorAction SilentlyContinue).Path
if ($projectRoot) {
    $contributesRoleDir = Join-Path $projectRoot "contributes" "roles" $safeName
    # If the role already exists in .agents/roles/, keep it there (builtin)
    # Otherwise, use contributes/roles/ for new dynamic roles
    if (-not (Test-Path (Join-Path $roleDir "role.json"))) {
        $roleDir = $contributesRoleDir
    }
}
$roleJsonPath = Join-Path $roleDir "role.json"

# --- Guard: don't overwrite existing roles ---
if (Test-Path $roleJsonPath) {
    Write-Host "[NEW-ROLE] Role '$safeName' already exists at $roleDir. Skipping."
    Write-Output $roleDir
    return
}

# --- Create directory ---
if (-not (Test-Path $roleDir)) {
    New-Item -ItemType Directory -Path $roleDir -Force | Out-Null
}

# --- Defaults ---
if (-not $Description) { $Description = "$safeName specialist agent" }
if ($Capabilities.Count -eq 0) { $Capabilities = @("code-generation", "file-editing", "shell-execution") }

# --- Write role.json ---
$roleDefinition = [ordered]@{
    name          = $safeName
    description   = $Description
    capabilities  = @($Capabilities)
    prompt_file   = "ROLE.md"
    quality_gates = @()
    skills        = @($Skills)
    cli           = $CLI
    instance_type = $InstanceType
    model         = $Model
    timeout       = $Timeout
}

$roleDefinition | ConvertTo-Json -Depth 5 | Out-File -FilePath $roleJsonPath -Encoding utf8 -Force
Write-Host "[NEW-ROLE] Created role.json for '$safeName'"

# --- Write ROLE.md if prompt content provided ---
if ($PromptContent) {
    $roleMdPath = Join-Path $roleDir "ROLE.md"
    $PromptContent | Out-File -FilePath $roleMdPath -Encoding utf8 -Force
    Write-Host "[NEW-ROLE] Created ROLE.md for '$safeName'"
}

Write-Host "[NEW-ROLE] Role '$safeName' scaffolded at $roleDir"
Write-Output $roleDir
