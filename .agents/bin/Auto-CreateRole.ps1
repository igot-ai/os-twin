param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$RoleName,

    [Parameter(Position=1, Mandatory=$true)]
    [string]$AgentsDir
)

$ErrorActionPreference = "Stop"

Write-Host "Creating missing role: $RoleName..."

$ManagerPrompt = "We need a new agent role called '$RoleName'. Please use the create-role skill to scaffold it. You MUST also create the specific SKILLs this role needs (as .md files in $AgentsDir/skills/), and you MUST create a custom PowerShell start script (Start-*.ps1) in its role directory to orchestrate its specific workflow. Ensure the role is registered in registry.json pointing to this new runner script. Explain your reasoning."

$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $env:HOME ".ostwin" }
$agentBin = if ($env:OSTWIN_AGENT_CMD) { $env:OSTWIN_AGENT_CMD } else { Join-Path $OstwinHome ".agents" "bin" "agent" }

if (-not (Test-Path $agentBin)) {
    Write-Error "Agent binary not found at: $agentBin`nRun the installer or set `$OSTWIN_AGENT_CMD."
    exit 1
}

$McpConfig = Join-Path $AgentsDir "mcp/config.json"
& $agentBin -a manager -n $ManagerPrompt --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config $McpConfig
