function Resolve-RoleDir {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$RoleName,

        [string]$ProjectDir = $PWD
    )

    # Search Path Priority (highest -> lowest):
    # 1. $PROJECT_DIR/.ostwin/roles/{role}/
    # 2. $AGENT_DIR/roles/{role}/
    # 3. $HOME/.ostwin/roles/{role}/

    $ProjectLocalRole = Join-Path $ProjectDir ".ostwin" "roles" $RoleName
    if (Test-Path $ProjectLocalRole -PathType Container) {
        return (Get-Item $ProjectLocalRole).FullName
    }

    # Resolve AGENT_DIR (assumes script is running from somewhere within it or near it)
    $AgentDir = $null
    $CurrentDir = (Get-Item $PSScriptRoot).Parent.FullName # $PSScriptRoot should be $AGENT_DIR/roles/manager/
    
    # Try to find agent-dir by looking for config.json
    $SearchDir = $CurrentDir
    while ($SearchDir -ne (Split-Path $SearchDir -Qualifier)) {
        if (Test-Path (Join-Path $SearchDir "config.json") -PathType Leaf) {
            $AgentDir = $SearchDir
            break
        }
        $SearchDir = Split-Path $SearchDir -Parent
    }

    if ($null -ne $AgentDir) {
        $AgentRole = Join-Path $AgentDir "roles" $RoleName
        if (Test-Path $AgentRole -PathType Container) {
            return (Get-Item $AgentRole).FullName
        }
    }

    $GlobalRole = Join-Path $HOME ".ostwin" "roles" $RoleName
    if (Test-Path $GlobalRole -PathType Container) {
        return (Get-Item $GlobalRole).FullName
    }

    Write-Error "Role '$RoleName' not found in any search path."
    return $null
}

Export-ModuleMember -Function Resolve-RoleDir
