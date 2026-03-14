$warRoomsDir = "$PSScriptRoot/tests/temp-war-rooms-approve"
if (Test-Path $warRoomsDir) { Remove-Item $warRoomsDir -Recurse -Force }
New-Item -ItemType Directory -Path $warRoomsDir | Out-Null

$job = Start-Job -ScriptBlock {
    param($pwd, $wd)
    $env:WARROOMS_DIR = $wd
    & "$pwd/plan/Start-Plan.ps1" -PlanFile "$pwd/tests/test-plan-negotiation.md" -ProjectDir $pwd
} -ArgumentList $PSScriptRoot, $warRoomsDir

Write-Host "Waiting for room-000..."
$r0 = "$warRoomsDir/room-000/channel.jsonl"
$waited = 0
while (-not (Test-Path $r0) -and $waited -lt 10) {
    Start-Sleep -Seconds 1
    $waited++
}

if (Test-Path $r0) {
    Write-Host "Posting approval..."
    & "$PSScriptRoot/channel/Post-Message.ps1" -RoomDir "$warRoomsDir/room-000" -From "manager" -To "team" -Type "plan-approve" -Ref "PLAN-REVIEW" -Body "Approved" | Out-Null
    Start-Sleep -Seconds 5
}

Write-Host "Checking for room-001..."
$r1 = "$warRoomsDir/room-001"
Write-Host "room-001 exists: $(Test-Path $r1)"

Stop-Job $job
Receive-Job $job
