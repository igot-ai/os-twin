# Agent OS — Config Module Pester Tests

BeforeAll {
    Import-Module (Join-Path (Resolve-Path "$PSScriptRoot/../../lib").Path "Config.psm1") -Force

    # ─── Test Config Data ────────────────────────────────────────────────────────
    $script:ValidConfig = @{
        version      = "0.1.0"
        project_name = "ostwin"
        manager      = @{
            poll_interval_seconds = 5
            max_concurrent_rooms  = 50
            max_engineer_retries  = 3
            auto_approve_tools    = $true
            state_timeout_seconds = 900
        }
        engineer     = @{
            cli              = "deepagents"
            default_model    = "gemini-3-flash-preview"
            shell_allow_list = "all"
            auto_approve     = $true
            timeout_seconds  = 600
            max_prompt_bytes = 102400
        }
        qa           = @{
            cli             = "deepagents"
            default_model   = "gemini-3-flash-preview"
            approval_mode   = "auto-approve"
            timeout_seconds = 300
        }
        channel      = @{
            format                 = "jsonl"
            max_message_size_bytes = 65536
        }
        release      = @{
            require_signoffs = @("engineer", "qa", "manager")
            auto_draft       = $true
        }
    }
}

AfterAll {
    Remove-Module -Name "Config" -ErrorAction SilentlyContinue
}

# ─── Get-OstwinConfig ───────────────────────────────────────────────────────

Describe "Get-OstwinConfig" {
    BeforeAll {
        $script:configFile = Join-Path $TestDrive "config.json"
        $script:ValidConfig | ConvertTo-Json -Depth 5 | Out-File $script:configFile -Encoding utf8
    }

    It "loads a valid config file" {
        $config = Get-OstwinConfig -ConfigPath $script:configFile
        $config.version | Should -Be "0.1.0"
        $config.project_name | Should -Be "ostwin"
    }

    It "reads nested values correctly" {
        $config = Get-OstwinConfig -ConfigPath $script:configFile
        $config.manager.poll_interval_seconds | Should -Be 5
        $config.engineer.cli | Should -Be "deepagents"
        $config.channel.format | Should -Be "jsonl"
    }

    It "throws when file not found" {
        { Get-OstwinConfig -ConfigPath "/nonexistent/config.json" } |
            Should -Throw "*not found*"
    }

    It "uses AGENT_OS_CONFIG env var" {
        $env:AGENT_OS_CONFIG = $script:configFile
        try {
            $config = Get-OstwinConfig
            $config.version | Should -Be "0.1.0"
        }
        finally {
            Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
        }
    }
}

# ─── Test-OstwinConfig ──────────────────────────────────────────────────────

Describe "Test-OstwinConfig" {
    It "validates a complete config successfully" {
        $config = $script:ValidConfig | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeTrue
        $result.Errors.Count | Should -Be 0
    }

    It "detects missing version" {
        $bad = $script:ValidConfig.Clone()
        $bad.Remove('version')
        $config = $bad | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeFalse
        $result.Errors | Should -Contain "Missing required field: version"
    }

    It "detects missing manager section" {
        $bad = $script:ValidConfig.Clone()
        $bad.Remove('manager')
        $config = $bad | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeFalse
        $result.Errors | Should -Contain "Missing required section: manager"
    }

    It "detects missing engineer.cli" {
        $bad = $script:ValidConfig.Clone()
        $bad.engineer = @{ default_model = "test"; timeout_seconds = 600 }
        $config = $bad | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeFalse
        $result.Errors | Should -Contain "Missing: engineer.cli"
    }

    It "detects invalid poll_interval_seconds" {
        $bad = $script:ValidConfig.Clone()
        $bad.manager = $script:ValidConfig.manager.Clone()
        $bad.manager.poll_interval_seconds = 0
        $config = $bad | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeFalse
        $result.Errors | Should -Contain "manager.poll_interval_seconds must be >= 1"
    }

    It "reports multiple errors" {
        $config = [PSCustomObject]@{ version = "1.0" }
        $result = Test-OstwinConfig -Config $config
        $result.IsValid | Should -BeFalse
        $result.Errors.Count | Should -BeGreaterThan 2
    }
}

# ─── New-RunConfig ───────────────────────────────────────────────────────────

Describe "New-RunConfig" {
    BeforeAll {
        $script:baseConfig = Join-Path $TestDrive "base-config.json"
        $script:ValidConfig | ConvertTo-Json -Depth 5 | Out-File $script:baseConfig -Encoding utf8
    }

    It "creates a copy of the base config" {
        $runConfig = Join-Path $TestDrive "run-config.json"
        New-RunConfig -ConfigPath $script:baseConfig -OutputPath $runConfig
        Test-Path $runConfig | Should -BeTrue
        $config = Get-Content $runConfig -Raw | ConvertFrom-Json
        $config.version | Should -Be "0.1.0"
    }

    It "applies overrides" {
        $runConfig = Join-Path $TestDrive "run-overridden.json"
        New-RunConfig -ConfigPath $script:baseConfig -OutputPath $runConfig `
                      -Overrides @{ "manager.max_concurrent_rooms" = 10 }
        $config = Get-Content $runConfig -Raw | ConvertFrom-Json
        $config.manager.max_concurrent_rooms | Should -Be 10
    }

    It "preserves non-overridden values" {
        $runConfig = Join-Path $TestDrive "run-preserved.json"
        New-RunConfig -ConfigPath $script:baseConfig -OutputPath $runConfig `
                      -Overrides @{ "manager.max_concurrent_rooms" = 5 }
        $config = Get-Content $runConfig -Raw | ConvertFrom-Json
        $config.manager.poll_interval_seconds | Should -Be 5
        $config.engineer.cli | Should -Be "deepagents"
    }

    It "throws when base config not found" {
        { New-RunConfig -ConfigPath "/nonexistent.json" -OutputPath "$TestDrive/out.json" } |
            Should -Throw "*not found*"
    }

    It "handles multiple overrides" {
        $runConfig = Join-Path $TestDrive "run-multi.json"
        New-RunConfig -ConfigPath $script:baseConfig -OutputPath $runConfig `
                      -Overrides @{
                          "manager.max_concurrent_rooms" = 25
                          "engineer.timeout_seconds"     = 1200
                      }
        $config = Get-Content $runConfig -Raw | ConvertFrom-Json
        $config.manager.max_concurrent_rooms | Should -Be 25
        $config.engineer.timeout_seconds | Should -Be 1200
    }
}
