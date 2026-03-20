$AgentsDir = (Resolve-Path "$PSScriptRoot/../..").Path

"Parent starting"
& "$AgentsDir/child.ps1"
"Parent ending"
