# ──────────────────────────────────────────────────────────────────────────────
# TestHelper.ps1 — Shared test initialization for Windows installer tests
#
# Dot-source this in BeforeAll to load all installer modules.
# Handles the module guard `return` issue by stripping guard lines and
# writing a combined temp script that the caller dot-sources.
#
# Usage in test files:
#   BeforeAll {
#       . "$PSScriptRoot/TestHelper.ps1"
#       $tmpScript = New-InstallerModuleScript -Modules @("Lib.ps1", "Versions.ps1")
#       . $tmpScript
#   }
#
#   AfterAll {
#       if ($tmpScript -and (Test-Path $tmpScript)) { Remove-Item $tmpScript -Force }
#   }
# ──────────────────────────────────────────────────────────────────────────────

# Resolve paths — tests/windows is two levels below installer/
# So ../../ from tests/windows/ gives us installer/ which IS the module dir
$script:InstallerModDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
# The .agents/ root is one level above installer/
$script:InstallerRoot = [System.IO.Path]::GetFullPath((Join-Path $script:InstallerModDir ".."))
$script:InstallPs1 = Join-Path $script:InstallerRoot "install.ps1"

function New-InstallerModuleScript {
    <#
    .SYNOPSIS
        Creates a temporary .ps1 file containing the requested modules
        with guards stripped. The caller MUST dot-source the returned path
        so functions are defined in the caller's scope (not this function's).

    .OUTPUTS
        [string] Path to the temporary .ps1 file. Caller should clean up
        in AfterAll.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string[]]$Modules
    )

    $combined = [System.Text.StringBuilder]::new()
    [void]$combined.AppendLine("# Auto-generated combined module script for Pester tests")
    [void]$combined.AppendLine("# Modules: $($Modules -join ', ')")
    [void]$combined.AppendLine("")

    foreach ($mod in $Modules) {
        $modPath = Join-Path $script:InstallerModDir $mod
        if (Test-Path $modPath) {
            $content = Get-Content $modPath -Raw

            # Strip: if ($script:_XxxLoaded) { return }
            $content = $content -replace '(?m)^if \(\$script:_\w+\) \{ return \}\r?\n?', ''

            # Strip: $script:_XxxLoaded = $true
            $content = $content -replace '(?m)^\$script:_\w+Loaded = \$true\r?\n?', ''

            [void]$combined.AppendLine("# ── $mod ──────────────────────────────────")
            [void]$combined.AppendLine($content)
            [void]$combined.AppendLine("")
        }
        else {
            Write-Warning "Module not found: $modPath"
        }
    }

    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-test-modules-$(Get-Random).ps1"
    Set-Content -Path $tempFile -Value $combined.ToString() -Encoding UTF8
    return $tempFile
}

# ──────────────────────────────────────────────────────────────────────────────
# Backward-compatible wrapper: Import-InstallerModule
#
# This is a convenience alias that calls New-InstallerModuleScript and
# immediately dot-sources the result. The trick: we can't dot-source
# from within a function and have functions visible to the caller.
#
# WORKAROUND: We write the combined content to a well-known temp file,
# then the caller (BeforeAll block) can dot-source it after calling this.
# ──────────────────────────────────────────────────────────────────────────────

$script:_ImportedModuleScript = ""

function Import-InstallerModule {
    <#
    .SYNOPSIS
        Backward-compatible wrapper. Creates a combined module script and
        stores the path in $script:_ImportedModuleScript. The test file's
        BeforeAll block must call this, then dot-source the script:

            Import-InstallerModule -Modules @("Lib.ps1")
            . $script:_ImportedModuleScript
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string[]]$Modules
    )

    $script:_ImportedModuleScript = New-InstallerModuleScript -Modules $Modules
}
