param(
    [Parameter(Mandatory, Position=0)]
    [string]$PlanFile
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$newDynamicRoleScript = Join-Path $agentsDir "roles\_base\New-DynamicRole.ps1"

if (-not (Test-Path $PlanFile)) {
    Write-Error "Markdown file not found: $PlanFile"
    exit 1
}

$content = Get-Content $PlanFile -Raw

# Match lines like "Roles: backend, frontend (some comment)"
$roleMatches = [regex]::Matches($content, '(?im)^Roles?:\s*(.+)$')

$allRoles = @()
foreach ($match in $roleMatches) {
    $line = $match.Groups[1].Value
    # Remove anything from an opening parenthesis to the end
    $line = $line -replace '\(.*$', ''
    # Split by comma and filter out invalid/placeholder roles
    $roles = $line -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
    $allRoles += $roles
}

if ($allRoles.Count -eq 0) {
    Write-Host "No roles found in $PlanFile."
    exit 0
}

$uniqueRoles = $allRoles | Select-Object -Unique

Write-Host "Found $($uniqueRoles.Count) unique role(s) to bash out:" -ForegroundColor Cyan
foreach ($r in $uniqueRoles) {
    Write-Host " - $r"
}
Write-Host ""

Write-Host "`nSuccessfully extracted all roles! (Test complete, no folders created)" -ForegroundColor Green
