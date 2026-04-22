# Agent OS - Unicode Compatibility Pester Tests
# Ensures all PowerShell scripts use only ASCII-compatible characters
# to prevent parsing errors on Windows systems with default code pages.

[CmdletBinding()]
param()

# Problematic Unicode characters that cause PowerShell parsing issues
$script:ProblematicChars = @{
    "\u2014" = "EM DASH (—)"
    "\u2013" = "EN DASH (–)"
    "\u2015" = "HORIZONTAL BAR (―)"
    "\u2500" = "BOX DRAWINGS LIGHT HORIZONTAL (─)"
    "\u2550" = "BOX DRAWINGS DOUBLE HORIZONTAL (═)"
    "\u2501" = "BOX DRAWINGS HEAVY HORIZONTAL (━)"
    "\u00AB" = "LEFT-POINTING DOUBLE ANGLE QUOTATION MARK («)"
    "\u00BB" = "RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK (»)"
    "\u201C" = "LEFT DOUBLE QUOTATION MARK (")"
    "\u201D" = "RIGHT DOUBLE QUOTATION MARK (")"
    "\u2018" = "LEFT SINGLE QUOTATION MARK (')"
    "\u2019" = "RIGHT SINGLE QUOTATION MARK (')"
    "\u2026" = "HORIZONTAL ELLIPSIS (…)"
    "\u2022" = "BULLET (•)"
    "\u25CF" = "BLACK CIRCLE (●)"
    "\u2713" = "CHECK MARK (✓)"
    "\u2714" = "HEAVY CHECK MARK (✔)"
    "\u2715" = "MULTIPLICATION X (✕)"
    "\u2716" = "HEAVY MULTIPLICATION X (✖)"
    "\u2717" = "BALLOT X (✗)"
    "\u2718" = "HEAVY BALLOT X (✘)"
    "\u274C" = "CROSS MARK (❌)"
    "\u2705" = "WHITE HEAVY CHECK MARK (✅)"
    "\u26A0" = "WARNING SIGN (⚠)"
    "\u2139" = "INFORMATION SOURCE (ℹ)"
    "\u2190" = "LEFTWARDS ARROW (←)"
    "\u2192" = "RIGHTWARDS ARROW (→)"
    "\u2191" = "UPWARDS ARROW (↑)"
    "\u2193" = "DOWNWARDS ARROW (↓)"
    "\u25B6" = "BLACK RIGHT-POINTING TRIANGLE (▶)"
    "\u25C0" = "BLACK LEFT-POINTING TRIANGLE (◀)"
    "\u25B8" = "BLACK RIGHT-POINTING SMALL TRIANGLE (▸)"
    "\u25B9" = "WHITE RIGHT-POINTING SMALL TRIANGLE (▹)"
    "\u00D7" = "MULTIPLICATION SIGN (×)"
    "\u00F7" = "DIVISION SIGN (÷)"
    "\u00B1" = "PLUS-MINUS SIGN (±)"
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
    "\u2551" = "BOX DRAWINGS DOUBLE VERTICAL (║)"
    "\u2554" = "BOX DRAWINGS DOUBLE DOWN AND RIGHT (╔)"
    "\u2557" = "BOX DRAWINGS DOUBLE DOWN AND LEFT (╗)"
    "\u255A" = "BOX DRAWINGS DOUBLE UP AND RIGHT (╚)"
    "\u255D" = "BOX DRAWINGS DOUBLE UP AND LEFT (╝)"
    "\u2560" = "BOX DRAWINGS DOUBLE VERTICAL AND RIGHT (╠)"
    "\u2563" = "BOX DRAWINGS DOUBLE VERTICAL AND LEFT (╣)"
    "\u2566" = "BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL (╦)"
    "\u2569" = "BOX DRAWINGS DOUBLE UP AND HORIZONTAL (╩)"
    "\u256C" = "BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL (╬)"
    "\u2561" = "BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE (╡)"
    "\u2562" = "BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE (╢)"
}

function Get-UnicodeFindings {
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

        foreach ($char in $script:ProblematicChars.Keys) {
            if ($line.Contains($char)) {
                $positions = @()
                for ($i = 0; $i -lt $line.Length; $i++) {
                    if ($line[$i] -eq $char) {
                        $positions += $i + 1
                    }
                }

                $findings += [PSCustomObject]@{
                    Line = $lineDisplay
                    Character = $char
                    Description = $script:ProblematicChars[$char]
                    Positions = $positions -join ", "
                    Context = $line.Trim()
                }
            }
        }
    }

    return $findings
}

# Resolve the .agents root (three levels up from tests/windows)
$agentsRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")

Describe "Unicode Compatibility - All PowerShell Files" {

    # Get all PowerShell files, excluding common non-project directories
    $psFiles = Get-ChildItem -Path $agentsRoot -Filter "*.ps1" -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch "\.git" -and
            $_.FullName -notmatch "node_modules" -and
            $_.FullName -notmatch "\.venv"
        }

    Context "EM DASH (U+2014) - Most common cause of parser errors" {
        It "No .ps1 files should contain EM DASH characters (—)" {
            $filesWithEmDash = @()

            foreach ($file in $psFiles) {
                $content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
                if ($content -and $content.Contains("\u2014")) {
                    $filesWithEmDash += $file.FullName.Replace($agentsRoot, ".")
                }
            }

            $filesWithEmDash | Should -BeNullOrEmpty -Because "EM DASH (—) causes PowerShell parser errors. Replace with simple hyphen (-). Found in: $($filesWithEmDash -join ', ')"
        }
    }

    Context "Box Drawing Characters - Common in decorative headers" {
        It "No .ps1 files should contain box drawing characters" {
            $boxDrawingChars = @("\u2500", "\u2550", "\u2501", "\u2502", "\u2551",
                                  "\u250C", "\u2554", "\u2510", "\u2557",
                                  "\u2514", "\u255A", "\u2518", "\u255D",
                                  "\u251C", "\u2560", "\u2524", "\u2563",
                                  "\u252C", "\u2566", "\u2534", "\u2569",
                                  "\u253C", "\u256C")

            $filesWithBoxDrawing = @()

            foreach ($file in $psFiles) {
                $content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
                if ($content) {
                    foreach ($char in $boxDrawingChars) {
                        if ($content.Contains($char)) {
                            $filesWithBoxDrawing += "$($file.FullName.Replace($agentsRoot, ".')) contains $($script:ProblematicChars[$char])"
                            break
                        }
                    }
                }
            }

            $filesWithBoxDrawing | Should -BeNullOrEmpty -Because "Box drawing characters cause encoding issues. Replace with ASCII equivalents like -, =, |, +"
        }
    }

    Context "Smart Quotes - Can cause string parsing issues" {
        It "No .ps1 files should contain smart quotes" {
            $smartQuotes = @("\u201C", "\u201D", "\u2018", "\u2019")

            $filesWithSmartQuotes = @()

            foreach ($file in $psFiles) {
                $content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
                if ($content) {
                    foreach ($char in $smartQuotes) {
                        if ($content.Contains($char)) {
                            $filesWithSmartQuotes += "$($file.FullName.Replace($agentsRoot, ".')) contains $($script:ProblematicChars[$char])"
                            break
                        }
                    }
                }
            }

            $filesWithSmartQuotes | Should -BeNullOrEmpty -Because "Smart quotes can cause string parsing issues. Replace with straight quotes (' and `")"
        }
    }

    Context "All problematic Unicode characters" {
        It "All .ps1 files should be free of problematic Unicode characters" {
            $allProblematicFindings = @()

            foreach ($file in $psFiles) {
                $findings = Get-UnicodeFindings -FilePath $file.FullName

                if ($findings.Count -gt 0) {
                    foreach ($finding in $findings) {
                        $allProblematicFindings += "$($file.FullName.Replace($agentsRoot, ".')): Line $($finding.Line) - $($finding.Description)"
                    }
                }
            }

            $allProblematicFindings | Should -BeNullOrEmpty -Because "Problematic Unicode characters cause PowerShell parser errors on Windows"
        }
    }
}

Describe "Unicode Compatibility - Critical Files" {

    Context "Installer scripts must be ASCII-clean" {
        $installerPath = Join-Path $agentsRoot "installer"

        if (Test-Path $installerPath) {
            $installerFiles = Get-ChildItem -Path $installerPath -Filter "*.ps1" -Recurse

            foreach ($file in $installerFiles) {
                It "$($file.Name) should have no Unicode issues" {
                    $findings = Get-UnicodeFindings -FilePath $file.FullName
                    $findings | Should -BeNullOrEmpty -Because "Installer file contains problematic Unicode characters"
                }
            }
        }
    }

    Context "install.ps1 must be ASCII-clean" {
        $installPs1 = Join-Path $agentsRoot "install.ps1"

        if (Test-Path $installPs1) {
            It "install.ps1 should have no Unicode issues" {
                $findings = Get-UnicodeFindings -FilePath $installPs1
                $findings | Should -BeNullOrEmpty -Because "Main installer contains problematic Unicode characters"
            }
        }
    }
}
