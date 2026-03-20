param(
    [Parameter(Mandatory, Position=0)]
    [string]$PlanFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PlanFile)) {
    Write-Error "Markdown file not found: $PlanFile"
    exit 1
}

$content = Get-Content $PlanFile -Raw

# Match "Lifecycle:" followed immediately by a markdown code block (e.g. ```text)
$pattern = '(?ism)^Lifecycle:[^\S\r\n]*\r?\n[^\S\r\n]*```[a-z]*\r?\n(.*?)\r?\n[^\S\r\n]*```'
$lifecycleMatches = [regex]::Matches($content, $pattern)

if ($lifecycleMatches.Count -eq 0) {
    Write-Host "No lifecycles found in $PlanFile."
    exit 0
}

Write-Host "Found $($lifecycleMatches.Count) lifecycle(s) to bash out:" -ForegroundColor Cyan
Write-Host ""

$index = 1
foreach ($match in $lifecycleMatches) {
    Write-Host "--- Lifecycle $index ---" -ForegroundColor Yellow
    Write-Host $match.Groups[1].Value
    Write-Host ""
    $index++
}

Write-Host "Successfully extracted all lifecycles! (Test complete, no folders created)" -ForegroundColor Green
