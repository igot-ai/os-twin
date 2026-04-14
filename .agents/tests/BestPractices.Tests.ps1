#Requires -Version 7.0

Describe 'PowerShell Best Practices Compliance' {

    BeforeAll {
        $script:libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
        $script:libFiles = Get-ChildItem -Path $script:libDir -Filter '*.psm1'
    }

    Context '#Requires statements' {
        It "<Name> has #Requires -Version" -ForEach {
            $libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
            Get-ChildItem -Path $libDir -Filter '*.psm1' | ForEach-Object { @{ Name = $_.Name; FullName = $_.FullName } }
        } {
            $content = Get-Content $FullName -Raw
            $content | Should -Match '#Requires\s+-Version'
        }
    }

    Context 'No automatic variable shadowing' {
        It "<Name> does not shadow automatic variables" -ForEach {
            $libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
            Get-ChildItem -Path $libDir -Filter '*.psm1' | ForEach-Object { @{ Name = $_.Name; FullName = $_.FullName } }
        } {
            $autoVars = @('pid', 'host', 'input', 'error', 'args', 'home', 'true', 'false', 'null')
            $content = Get-Content $FullName -Raw
            foreach ($v in $autoVars) {
                $pattern = '\$' + $v + '\s*='
                $content | Should -Not -Match $pattern -Because "`$$v is an automatic variable"
            }
        }
    }

    Context 'Module exports' {
        It "<Name> has Export-ModuleMember" -ForEach {
            $libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
            Get-ChildItem -Path $libDir -Filter '*.psm1' | ForEach-Object { @{ Name = $_.Name; FullName = $_.FullName } }
        } {
            $content = Get-Content $FullName -Raw
            $content | Should -Match 'Export-ModuleMember'
        }
    }

    Context 'CmdletBinding on public functions' {
        It "<Name> uses [CmdletBinding()] on functions" -ForEach {
            $libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
            Get-ChildItem -Path $libDir -Filter '*.psm1' | ForEach-Object { @{ Name = $_.Name; FullName = $_.FullName } }
        } {
            $content = Get-Content $FullName -Raw
            $functions = [regex]::Matches($content, '(?m)^\s*function\s+\w')
            if ($functions.Count -gt 0) {
                $bindings = [regex]::Matches($content, '\[CmdletBinding\(\)\]')
                $bindings.Count | Should -BeGreaterOrEqual $functions.Count -Because "every function should have [CmdletBinding()]"
            }
        }
    }

    Context 'No exit 1 in module files' {
        It "<Name> does not use exit" -ForEach {
            $libDir = (Resolve-Path "$PSScriptRoot/../lib").Path
            Get-ChildItem -Path $libDir -Filter '*.psm1' | ForEach-Object { @{ Name = $_.Name; FullName = $_.FullName } }
        } {
            $content = Get-Content $FullName -Raw
            $content | Should -Not -Match '\bexit\s+\d'
        }
    }
}
