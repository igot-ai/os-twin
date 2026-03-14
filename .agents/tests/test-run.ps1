Write-Host "--- LS OUTPUT ---"
ls /
Write-Host "--- PESTER OUTPUT ---"
Invoke-Pester /Users/paulaan/PycharmProjects/agent-os/.agents/tests/Channel-Negotiation.Tests.ps1 -Output Detailed

$job = Start-Job -ScriptBlock {
    param($pwd, $wd)
    $env:WARROOMS_DIR = $wd
    & "$pwd/plan/Start-Plan.ps1" -PlanFile "$pwd/tests/test-plan-negotiation.md" -ProjectDir $pwd
} -ArgumentList $PSScriptRoot, $warRoomsDir

Start-Sleep -Seconds 3

# check if room-000 was created
$r0 = "$warRoomsDir/room-000/channel.jsonl"
Write-Host "room-000 channel exists: $(Test-Path $r0)"

if (Test-Path $r0) {
    # Post a reject message
    & "$PSScriptRoot/channel/Post-Message.ps1" -RoomDir "$warRoomsDir/room-000" -From "team" -To "manager" -Type "plan-reject" -Ref "PLAN-REVIEW" -Body "nah" | Out-Null
    Start-Sleep -Seconds 2
}

Stop-Job $job
Receive-Job $job