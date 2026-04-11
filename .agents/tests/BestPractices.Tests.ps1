#Requires -Version 7.0

Describe 'PowerShell Best Practices Compliance' {

    BeforeAll {
        $projectRoot = Split-Path $PSScriptRoot
        $psm1Files = Get-ChildItem -Path "$projectRoot/.agents/lib" -Filter '*.psm1' -Recurse
        $ps1Files = Get-ChildItem -Path "$projectRoot/.agents" -Filter '*.ps1' -Recurse
        $allPsFiles = @($psm1Files) + @($ps1Files)
    }

    Context '#Requires statements' {
        foreach ($file in (Get-ChildItem -Path "$PSScriptRoot/../.agents/lib" -Filter '*.psm1')) {
            It "$($file.Name) has #Requires -Version" {
                $content = Get-Content $file.FullName -Raw
                $content | Should -Match '#Requires\s+-Version'
            }
        }
    }

    Context 'No automatic variable shadowing' {
        $autoVars = @('pid', 'host', 'input', 'error', 'args', 'home', 'true', 'false', 'null')

        foreach ($file in (Get-ChildItem -Path "$PSScriptRoot/../.agents/lib" -Filter '*.psm1')) {
            It "$($file.Name) does not shadow automatic variables" {
                $content = Get-Content $file.FullName -Raw
                foreach ($v in $autoVars) {
                    # Match assignment: $pid = (but not $targetPid, $processId, etc.)
                    $pattern = '\$' + $v + '\s*='
                    $content | Should -Not -Match $pattern -Because "`$$v is an automatic variable"
                }
            }
        }
    }

    Context 'Module exports' {
        foreach ($file in (Get-ChildItem -Path "$PSScriptRoot/../.agents/lib" -Filter '*.psm1')) {
            It "$($file.Name) has Export-ModuleMember" {
                $content = Get-Content $file.FullName -Raw
                $content | Should -Match 'Export-ModuleMember'
            }
        }
    }

    Context 'CmdletBinding on public functions' {
        foreach ($file in (Get-ChildItem -Path "$PSScriptRoot/../.agents/lib" -Filter '*.psm1')) {
            It "$($file.Name) uses [CmdletBinding()] on functions" {
                $content = Get-Content $file.FullName -Raw
                $functions = [regex]::Matches($content, '(?m)^\s*function\s+\w')
                if ($functions.Count -gt 0) {
                    $bindings = [regex]::Matches($content, '\[CmdletBinding\(\)\]')
                    $bindings.Count | Should -BeGreaterOrEqual $functions.Count -Because "every function should have [CmdletBinding()]"
                }
            }
        }
    }

    Context 'No exit 1 in module files' {
        foreach ($file in (Get-ChildItem -Path "$PSScriptRoot/../.agents/lib" -Filter '*.psm1')) {
            It "$($file.Name) does not use exit" {
                $content = Get-Content $file.FullName -Raw
                $content | Should -Not -Match '\bexit\s+\d'
            }
        }
    }
}
