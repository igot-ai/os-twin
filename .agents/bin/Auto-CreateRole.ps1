param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$RoleName,

    [Parameter(Position=1, Mandatory=$true)]
    [string]$AgentsDir
)

$ErrorActionPreference = "Stop"

Write-Host "Creating missing role: $RoleName..."

$OstwinPath = Join-Path -Path $AgentsDir -ChildPath "bin/ostwin"

# Construct the prompt for the manager agent
$ManagerPrompt = "We need a new agent role called '$RoleName'. Please use the create-role skill to scaffold it. You MUST also create the specific SKILLs this role needs (as .md files in $AgentsDir/skills/), and you MUST create a custom PowerShell start script (Start-*.ps1) in its role directory to orchestrate its specific workflow. Ensure the role is registered in registry.json pointing to this new runner script. Explain your reasoning."

# Execute deepagents non-interactively
$deepagentsCmd = Get-Command deepagents -ErrorAction SilentlyContinue
if ($null -eq $deepagentsCmd) {
    # Fallback paths
    $homeDir = [System.Environment]::GetFolderPath('UserProfile')
    $uvPath = Join-Path $homeDir ".local/share/uv/tools/deepagents-cli/bin/deepagents"
    $localBinPath = Join-Path $homeDir ".local/bin/deepagents"
    if (Test-Path $uvPath) { $deepagentsCmd = $uvPath }
    elseif (Test-Path $localBinPath) { $deepagentsCmd = $localBinPath }
    else { $deepagentsCmd = "deepagents" } # Hope it works
}

$McpConfig = Join-Path $AgentsDir "mcp/mcp-config.json"
& $deepagentsCmd -a manager -n $ManagerPrompt --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config $McpConfig