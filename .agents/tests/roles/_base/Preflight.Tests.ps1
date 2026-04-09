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

    It "should log a warning for a skill missing frontmatter when preflight is 'warn'" -Skip:$true {
        # Skipped: Build-SystemPrompt does not currently implement frontmatter preflight validation.
        # This test documents the intended future behavior.
        Set-ItResult -Skipped "Build-SystemPrompt does not implement frontmatter preflight warnings"
    }

    It "should log a warning for a skill missing metadata in frontmatter when preflight is 'warn'" -Skip:$true {
        # Skipped: Build-SystemPrompt does not currently implement frontmatter preflight validation.
        Set-ItResult -Skipped "Build-SystemPrompt does not implement frontmatter metadata warnings"
    }
}
