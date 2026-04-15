# ──────────────────────────────────────────────────────────────────────────────
# Install.Integration.Tests.ps1 — Integration tests for install.ps1
# ──────────────────────────────────────────────────────────────────────────────

Describe "install.ps1 module loading" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $installerDir = $script:InstallerModDir
    }

    It "All module files should exist" {
        $modules = @(
            "Lib.ps1", "Versions.ps1", "Detect-OS.ps1", "Check-Deps.ps1",
            "Install-Deps.ps1", "Install-Files.ps1", "Setup-Venv.ps1",
            "Setup-Env.ps1", "Patch-MCP.ps1", "Build-Frontend.ps1",
            "Setup-Path.ps1", "Setup-OpenCode.ps1", "Sync-Agents.ps1",
            "Start-Dashboard.ps1", "Start-Channels.ps1", "Verify.ps1",
            "Orchestrate-Deps.ps1"
        )

        foreach ($mod in $modules) {
            $modPath = Join-Path $installerDir $mod
            Test-Path $modPath | Should -Be $true -Because "$mod should exist"
        }
    }

    It "All module files should parse without errors" {
        $modules = Get-ChildItem -Path $installerDir -Filter "*.ps1"
        foreach ($mod in $modules) {
            $errors = $null
            [System.Management.Automation.Language.Parser]::ParseFile(
                $mod.FullName,
                [ref]$null,
                [ref]$errors
            )
            $errors.Count | Should -Be 0 -Because "$($mod.Name) should parse cleanly"
        }
    }

    It "install.ps1 should exist and parse" {
        $installPs1 = $script:InstallPs1
        Test-Path $installPs1 | Should -Be $true

        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $installPs1,
            [ref]$null,
            [ref]$errors
        )
        $errors.Count | Should -Be 0 -Because "install.ps1 should parse cleanly"
    }

    It "install.ps1 should have param block with correct parameters" {
        $installPs1 = $script:InstallPs1
        $ast = [System.Management.Automation.Language.Parser]::ParseFile(
            $installPs1,
            [ref]$null,
            [ref]$null
        )
        $params = $ast.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath }

        $params | Should -Contain "Yes"
        $params | Should -Contain "Dir"
        $params | Should -Contain "SourceDir"
        $params | Should -Contain "Port"
        $params | Should -Contain "DashboardOnly"
        $params | Should -Contain "Channel"
        $params | Should -Contain "SkipOptional"
        $params | Should -Contain "Help"
    }
}

Describe "Module function exports" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        Import-InstallerModule -Modules @(
            "Lib.ps1", "Versions.ps1", "Detect-OS.ps1", "Check-Deps.ps1",
            "Install-Deps.ps1", "Install-Files.ps1", "Setup-Venv.ps1",
            "Setup-Env.ps1", "Patch-MCP.ps1", "Build-Frontend.ps1",
            "Setup-Path.ps1", "Setup-OpenCode.ps1", "Sync-Agents.ps1",
            "Start-Dashboard.ps1", "Start-Channels.ps1", "Verify.ps1",
            "Orchestrate-Deps.ps1"
        )
        . $script:_ImportedModuleScript
    }

    It "Should export Write-Header" { Get-Command Write-Header | Should -Not -BeNullOrEmpty }
    It "Should export Write-Ok" { Get-Command Write-Ok | Should -Not -BeNullOrEmpty }
    It "Should export Write-Warn" { Get-Command Write-Warn | Should -Not -BeNullOrEmpty }
    It "Should export Write-Fail" { Get-Command Write-Fail | Should -Not -BeNullOrEmpty }
    It "Should export Write-Info" { Get-Command Write-Info | Should -Not -BeNullOrEmpty }
    It "Should export Write-Step" { Get-Command Write-Step | Should -Not -BeNullOrEmpty }
    It "Should export Ask-User" { Get-Command Ask-User | Should -Not -BeNullOrEmpty }
    It "Should export Compare-VersionGte" { Get-Command Compare-VersionGte | Should -Not -BeNullOrEmpty }
    It "Should export Detect-WindowsOS" { Get-Command Detect-WindowsOS | Should -Not -BeNullOrEmpty }
    It "Should export Check-Python" { Get-Command Check-Python | Should -Not -BeNullOrEmpty }
    It "Should export Check-Pwsh" { Get-Command Check-Pwsh | Should -Not -BeNullOrEmpty }
    It "Should export Check-Node" { Get-Command Check-Node | Should -Not -BeNullOrEmpty }
    It "Should export Check-UV" { Get-Command Check-UV | Should -Not -BeNullOrEmpty }
    It "Should export Check-OpenCode" { Get-Command Check-OpenCode | Should -Not -BeNullOrEmpty }
    It "Should export Install-UV" { Get-Command Install-UV | Should -Not -BeNullOrEmpty }
    It "Should export Install-Python" { Get-Command Install-Python | Should -Not -BeNullOrEmpty }
    It "Should export Install-Pwsh" { Get-Command Install-Pwsh | Should -Not -BeNullOrEmpty }
    It "Should export Install-Node" { Get-Command Install-Node | Should -Not -BeNullOrEmpty }
    It "Should export Install-OpenCode" { Get-Command Install-OpenCode | Should -Not -BeNullOrEmpty }
    It "Should export Install-PesterModule" { Get-Command Install-PesterModule | Should -Not -BeNullOrEmpty }
    It "Should export Install-Files" { Get-Command Install-Files | Should -Not -BeNullOrEmpty }
    It "Should export Compute-BuildHash" { Get-Command Compute-BuildHash | Should -Not -BeNullOrEmpty }
    It "Should export Setup-Venv" { Get-Command Setup-Venv | Should -Not -BeNullOrEmpty }
    It "Should export Setup-Env" { Get-Command Setup-Env | Should -Not -BeNullOrEmpty }
    It "Should export Patch-McpConfig" { Get-Command Patch-McpConfig | Should -Not -BeNullOrEmpty }
    It "Should export Build-Frontend" { Get-Command Build-Frontend | Should -Not -BeNullOrEmpty }
    It "Should export Setup-Path" { Get-Command Setup-Path | Should -Not -BeNullOrEmpty }
    It "Should export Setup-OpenCodePermissions" { Get-Command Setup-OpenCodePermissions | Should -Not -BeNullOrEmpty }
    It "Should export Sync-OpenCodeAgents" { Get-Command Sync-OpenCodeAgents | Should -Not -BeNullOrEmpty }
    It "Should export Start-Dashboard" { Get-Command Start-Dashboard | Should -Not -BeNullOrEmpty }
    It "Should export Publish-Skills" { Get-Command Publish-Skills | Should -Not -BeNullOrEmpty }
    It "Should export Install-Channels" { Get-Command Install-Channels | Should -Not -BeNullOrEmpty }
    It "Should export Start-Channels" { Get-Command Start-Channels | Should -Not -BeNullOrEmpty }
    It "Should export Verify-Components" { Get-Command Verify-Components | Should -Not -BeNullOrEmpty }
    It "Should export Print-CompletionBanner" { Get-Command Print-CompletionBanner | Should -Not -BeNullOrEmpty }
    It "Should export Invoke-DependencyOrchestration" { Get-Command Invoke-DependencyOrchestration | Should -Not -BeNullOrEmpty }
}

Describe "Bash module parity" {
    It "Should have matching PowerShell module for each bash module" {
        $bashModules = @(
            "lib.sh", "versions.conf", "detect-os.sh", "check-deps.sh",
            "install-deps.sh", "install-files.sh", "setup-venv.sh",
            "setup-env.sh", "patch-mcp.sh", "build-frontend.sh",
            "setup-path.sh", "setup-opencode.sh", "sync-agents.sh",
            "start-dashboard.sh", "start-channels.sh", "verify.sh",
            "_orchestrate-deps.sh"
        )

        $ps1Modules = @(
            "Lib.ps1", "Versions.ps1", "Detect-OS.ps1", "Check-Deps.ps1",
            "Install-Deps.ps1", "Install-Files.ps1", "Setup-Venv.ps1",
            "Setup-Env.ps1", "Patch-MCP.ps1", "Build-Frontend.ps1",
            "Setup-Path.ps1", "Setup-OpenCode.ps1", "Sync-Agents.ps1",
            "Start-Dashboard.ps1", "Start-Channels.ps1", "Verify.ps1",
            "Orchestrate-Deps.ps1"
        )

        $bashModules.Count | Should -Be $ps1Modules.Count -Because "PS1 module count should match bash module count"

        foreach ($ps1 in $ps1Modules) {
            Test-Path (Join-Path $script:InstallerModDir $ps1) | Should -Be $true -Because "$ps1 should exist"
        }
    }
}

Describe "CLI flag parity" {
    It "install.ps1 parameters should mirror install.sh flags" {
        $installPs1 = $script:InstallPs1
        $ast = [System.Management.Automation.Language.Parser]::ParseFile(
            $installPs1,
            [ref]$null,
            [ref]$null
        )
        $params = $ast.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath }

        # Bash equivalents: --yes -> -Yes, --dir -> -Dir, --source-dir -> -SourceDir,
        # --port -> -Port, --dashboard-only -> -DashboardOnly, --channel -> -Channel,
        # --skip-optional -> -SkipOptional, --help -> -Help
        $params | Should -Contain "Yes"
        $params | Should -Contain "Dir"
        $params | Should -Contain "SourceDir"
        $params | Should -Contain "Port"
        $params | Should -Contain "DashboardOnly"
        $params | Should -Contain "Channel"
        $params | Should -Contain "SkipOptional"
        $params | Should -Contain "Help"
    }
}

Describe "No WSL/Cygwin/Git Bash dependencies" {
    It "Should not reference bash in any module" {
        $ps1Files = Get-ChildItem -Path $script:InstallerModDir -Filter "*.ps1"

        foreach ($file in $ps1Files) {
            $content = Get-Content $file.FullName -Raw
            # Allow references in comments and the sync-skills fallback
            $codeLines = Get-Content $file.FullName | Where-Object {
                $_ -notmatch '^\s*#' -and $_ -notmatch 'sync-skills' -and $_ -match '\S'
            }
            $codeContent = $codeLines -join "`n"

            $codeContent | Should -Not -Match '\bwsl\b' -Because "$($file.Name) should not use WSL"
            $codeContent | Should -Not -Match '\bcygwin\b' -Because "$($file.Name) should not use Cygwin"
            $codeContent | Should -Not -Match '\bgit\s+bash\b' -Because "$($file.Name) should not use Git Bash"
        }
    }

    It "Should not use rsync in any module" {
        $ps1Files = Get-ChildItem -Path $script:InstallerModDir -Filter "*.ps1"

        foreach ($file in $ps1Files) {
            $content = Get-Content $file.FullName -Raw
            $content | Should -Not -Match '\brsync\b' -Because "$($file.Name) should use robocopy/Copy-Item, not rsync"
        }
    }

    It "Should not use sed in any module" {
        $ps1Files = Get-ChildItem -Path $script:InstallerModDir -Filter "*.ps1"

        foreach ($file in $ps1Files) {
            $codeLines = Get-Content $file.FullName | Where-Object { $_ -notmatch '^\s*#' }
            $codeContent = $codeLines -join "`n"
            $codeContent | Should -Not -Match '\bsed\b' -Because "$($file.Name) should use -replace, not sed"
        }
    }
}

