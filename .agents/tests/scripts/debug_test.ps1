$AgentsDir = (Resolve-Path "$PSScriptRoot/../..").Path

python3 "$AgentsDir/../dashboard/test_epic4_models.py"



