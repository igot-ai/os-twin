# Preflight Check Tests

Describe "Preflight Skill Check" {
    BeforeAll {
        $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../..").Path "..")).Path
        $script:buildPrompt = Join-Path $script:agentsDir "roles" "_base" "Build-SystemPrompt.ps1"
        $script:skillsDir = Join-Path $script:agentsDir "skills"
        
        # Create a legacy skill without frontmatter
        $script:legacySkillDir = Join-Path $script:skillsDir "legacy-test"
        New-Item -ItemType Directory -Path $script:legacySkillDir -Force | Out-Null
        "This is a legacy skill without frontmatter." | Out-File -FilePath (Join-Path $script:legacySkillDir "SKILL.md") -Encoding utf8
    }

    AfterAll {
        Remove-Item -Path $script:legacySkillDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    It "should log a warning for a skill missing frontmatter when preflight is 'warn'" {
        # Use TestDrive for temp role
        $tempRoleDir = Join-Path $TestDrive "temp-role"
        New-Item -ItemType Directory -Path $tempRoleDir -Force | Out-Null
        @{
            name = "test-role"
            skill_refs = @("legacy-test")
        } | ConvertTo-Json | Out-File -FilePath (Join-Path $tempRoleDir "role.json") -Encoding utf8
        "Test role prompt" | Out-File -FilePath (Join-Path $tempRoleDir "ROLE.md") -Encoding utf8

        # Run Build-SystemPrompt and capture warnings
        $warning = $null
        # We need to set AGENT_OS_CONFIG so it finds the config with preflight="warn"
        $env:AGENT_OS_CONFIG = Join-Path $script:agentsDir "config.json"
        
        $prompt = & $script:buildPrompt -RolePath $tempRoleDir -WarningVariable localWarning -WarningAction Continue
        
        $localWarning | Should -Not -BeNullOrEmpty
        $localWarning[0].Message | Should -Match "missing YAML frontmatter"
    }

    It "should log a warning for a skill missing metadata in frontmatter when preflight is 'warn'" {
        # Create a skill with frontmatter but missing tags/trust_level
        $script:badMetaSkillDir = Join-Path $script:skillsDir "bad-meta-test"
        New-Item -ItemType Directory -Path $script:badMetaSkillDir -Force | Out-Null
        @"
---
name: bad-meta
---
Skill content.
"@ | Out-File -FilePath (Join-Path $script:badMetaSkillDir "SKILL.md") -Encoding utf8
        
        $tempRoleDir = Join-Path $TestDrive "temp-role-2"
        New-Item -ItemType Directory -Path $tempRoleDir -Force | Out-Null
        @{
            name = "test-role-2"
            skill_refs = @("bad-meta-test")
        } | ConvertTo-Json | Out-File -FilePath (Join-Path $tempRoleDir "role.json") -Encoding utf8
        "Test role prompt" | Out-File -FilePath (Join-Path $tempRoleDir "ROLE.md") -Encoding utf8

        # Run and capture using -WarningVariable
        $prompt = & $script:buildPrompt -RolePath $tempRoleDir -WarningVariable localWarning -WarningAction Continue
        
        $localWarning | Should -Not -BeNullOrEmpty
        $localWarning[0].Message | Should -Match "missing required metadata"
        
        # Cleanup
        Remove-Item -Path $script:badMetaSkillDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
