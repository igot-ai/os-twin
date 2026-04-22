# Test-UnicodeCompatibility.ps1
# Tests that all PowerShell scripts use only ASCII-compatible characters
# to prevent parsing errors on Windows systems with default code pages.

[CmdletBinding()]
param(
    [string]$RootPath = (Join-Path $PSScriptRoot "..\.."),
    [switch]$FailOnFindings
)

# Problematic Unicode characters that cause PowerShell parsing issues
$ProblematicChars = @{
    # Em-dash (U+2014) - most common culprit
    "\u2014" = "EM DASH (—)"
    # En-dash (U+2013)
    "\u2013" = "EN DASH (–)"
    # Horizontal bar (U+2015)
    "\u2015" = "HORIZONTAL BAR (―)"
    # Box drawing characters (commonly used in headers)
    "\u2500" = "BOX DRAWINGS LIGHT HORIZONTAL (─)"
    "\u2550" = "BOX DRAWINGS DOUBLE HORIZONTAL (═)"
    "\u2501" = "BOX DRAWINGS HEAVY HORIZONTAL (━)"
    # Double angle brackets
    "\u00AB" = "LEFT-POINTING DOUBLE ANGLE QUOTATION MARK («)"
    "\u00BB" = "RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK (»)"
    # Smart quotes
    "\u201C" = "LEFT DOUBLE QUOTATION MARK (")"
    "\u201D" = "RIGHT DOUBLE QUOTATION MARK (")"
    "\u2018" = "LEFT SINGLE QUOTATION MARK (')"
    "\u2019" = "RIGHT SINGLE QUOTATION MARK (')"
    # Ellipsis
    "\u2026" = "HORIZONTAL ELLIPSIS (…)"
    # Bullet points
    "\u2022" = "BULLET (•)"
    "\u25CF" = "BLACK CIRCLE (●)"
    # Check marks and X marks commonly used in output
    "\u2713" = "CHECK MARK (✓)"
    "\u2714" = "HEAVY CHECK MARK (✔)"
    "\u2715" = "MULTIPLICATION X (✕)"
    "\u2716" = "HEAVY MULTIPLICATION X (✖)"
    "\u2717" = "BALLOT X (✗)"
    "\u2718" = "HEAVY BALLOT X (✘)"
    "\u274C" = "CROSS MARK (❌)"
    "\u2705" = "WHITE HEAVY CHECK MARK (✅)"
    # Warning and info symbols
    "\u26A0" = "WARNING SIGN (⚠)"
    "\u2139" = "INFORMATION SOURCE (ℹ)"
    # Arrows commonly used in diagrams
    "\u2190" = "LEFTWARDS ARROW (←)"
    "\u2192" = "RIGHTWARDS ARROW (→)"
    "\u2191" = "UPWARDS ARROW (↑)"
    "\u2193" = "DOWNWARDS ARROW (↓)"
    "\u25B6" = "BLACK RIGHT-POINTING TRIANGLE (▶)"
    "\u25C0" = "BLACK LEFT-POINTING TRIANGLE (◀)"
    # Triangle bullets
    "\u25B8" = "BLACK RIGHT-POINTING SMALL TRIANGLE (▸)"
    "\u25B9" = "WHITE RIGHT-POINTING SMALL TRIANGLE (▹)"
    # Math symbols
    "\u00D7" = "MULTIPLICATION SIGN (×)"
    "\u00F7" = "DIVISION SIGN (÷)"
    "\u00B1" = "PLUS-MINUS SIGN (±)"
    # Other box drawing characters
    "\u2502" = "BOX DRAWINGS LIGHT VERTICAL (│)"
    "\u250C" = "BOX DRAWINGS LIGHT DOWN AND RIGHT (┌)"
    "\u2510" = "BOX DRAWINGS LIGHT DOWN AND LEFT (┐)"
    "\u2514" = "BOX DRAWINGS LIGHT UP AND RIGHT (└)"
    "\u2518" = "BOX DRAWINGS LIGHT UP AND LEFT (┘)"
    "\u251C" = "BOX DRAWINGS LIGHT VERTICAL AND RIGHT (├)"
    "\u2524" = "BOX DRAWINGS LIGHT VERTICAL AND LEFT (┤)"
    "\u252C" = "BOX DRAWINGS LIGHT DOWN AND HORIZONTAL (┬)"
    "\u2534" = "BOX DRAWINGS LIGHT UP AND HORIZONTAL (┴)"
    "\u253C" = "BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL (┼)"
    # Double line box drawing
    "\u2551" = "BOX DRAWINGS DOUBLE VERTICAL (║)"
    "\u2554" = "BOX DRAWINGS DOUBLE DOWN AND RIGHT (╔)"
    "\u2557" = "BOX DRAWINGS DOUBLE DOWN AND LEFT (╗)"
    "\u255A" = "BOX DRAWINGS DOUBLE UP AND RIGHT (╚)"
    "\u255D" = "BOX DRAWINGS DOUBLE UP AND LEFT (╝)"
    # Corner pieces with arrows (common in ASCII art)
    "\u2560" = "BOX DRAWINGS DOUBLE VERTICAL AND RIGHT (╠)"
    "\u2563" = "BOX DRAWINGS DOUBLE VERTICAL AND LEFT (╣)"
    "\u2566" = "BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL (╦)"
    "\u2569" = "BOX DRAWINGS DOUBLE UP AND HORIZONTAL (╩)"
    "\u256C" = "BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL (╬)"
    # Single to double transitions
    "\u2561" = "BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE (╡)"
    "\u2562" = "BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE (╢)"
}

function Test-FileUnicodeCompatibility {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath
    )

    $findings = @()
    $content = Get-Content -Path $FilePath -Raw -ErrorAction Stop
    $lines = $content -split "`r?`n"

    for ($lineNum = 0; $lineNum -lt $lines.Count; $lineNum++) {
        $line = $lines[$lineNum]
        $lineDisplay = $lineNum + 1

        foreach ($char in $ProblematicChars.Keys) {
            if ($line.Contains($char)) {
                $positions = @()
                for ($i = 0; $i -lt $line.Length; $i++) {
                    if ($line[$i] -eq $char) {
                        $positions += $i + 1
                    }
                }

                $findings += [PSCustomObject]@{
                    File = $FilePath
                    Line = $lineDisplay
                    Character = $char
                    Description = $ProblematicChars[$char]
                    Positions = $positions -join ", "
                    Context = $line.Trim()
                }
            }
        }
    }

    return $findings
}

# Main execution
Write-Host ""
Write-Host "=== Unicode Compatibility Test for PowerShell Scripts ===" -ForegroundColor Cyan
Write-Host "Scanning for problematic Unicode characters..." -ForegroundColor Gray
Write-Host ""

$allFindings = @()
$filesChecked = 0

# Find all PowerShell files
$psFiles = Get-ChildItem -Path $RootPath -Filter "*.ps1" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\.git" -and $_.FullName -notmatch "node_modules" }

Write-Host "Found $($psFiles.Count) PowerShell files to check" -ForegroundColor Gray
Write-Host ""

foreach ($file in $psFiles) {
    $filesChecked++
    $findings = Test-FileUnicodeCompatibility -FilePath $file.FullName

    if ($findings.Count -gt 0) {
        $allFindings += $findings
        Write-Host "FAIL: $($file.FullName.Replace($RootPath, '.'))" -ForegroundColor Red

        foreach ($finding in $findings) {
            Write-Host "  Line $($finding.Line): $($finding.Description) at position(s) $($finding.Positions)" -ForegroundColor Yellow
            Write-Host "    Context: $($finding.Context.Substring(0, [Math]::Min(80, $finding.Context.Length)))..." -ForegroundColor DarkGray
        }
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Files checked: $filesChecked" -ForegroundColor White
Write-Host "Files with issues: $($allFindings | Select-Object -Property File -Unique | Measure-Object | Select-Object -ExpandProperty Count)" -ForegroundColor $(if ($allFindings.Count -gt 0) { "Red" } else { "Green" })
Write-Host "Total findings: $($allFindings.Count)" -ForegroundColor $(if ($allFindings.Count -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($allFindings.Count -gt 0) {
    Write-Host "RECOMMENDATION: Replace the problematic characters with ASCII equivalents:" -ForegroundColor Yellow
    Write-Host "  • EM DASH (—) -> HYPHEN (-)" -ForegroundColor Gray
    Write-Host "  • EN DASH (–) -> HYPHEN (-)" -ForegroundColor Gray
    Write-Host "  • BOX DRAWINGS (─, ═, etc.) -> Simple ASCII (-, =, |, +)" -ForegroundColor Gray
    Write-Host "  • SMART QUOTES (", ') -> STRAIGHT QUOTES ('", "')" -ForegroundColor Gray
    Write-Host "  • BULLETS (•, ●) -> HYPHEN (-) or ASTERISK (*)" -ForegroundColor Gray
    Write-Host "  • CHECK/X MARKS (✓, ✔, ✗, ✘, ❌, ✅) -> [OK], [FAIL], [X]" -ForegroundColor Gray
    Write-Host ""

    if ($FailOnFindings) {
        exit 1
    }
}
else {
    Write-Host "SUCCESS: All PowerShell scripts use ASCII-compatible characters only!" -ForegroundColor Green
}

exit 0
