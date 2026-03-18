Describe "Resolve-RoleSkills" {
    BeforeAll {
        $testSkillsDir = Join-Path $PSScriptRoot "test_skills"
        $testRolePath = Join-Path $PSScriptRoot "test_role"

        # Setup test environment
        if (Test-Path $testSkillsDir) { Remove-Item $testSkillsDir -Recurse -Force }
        if (Test-Path $testRolePath) { Remove-Item $testRolePath -Recurse -Force }

        mkdir -p (Join-Path $testSkillsDir "global" "global-skill")
        "Global Skill content" > (Join-Path $testSkillsDir "global" "global-skill" "SKILL.md")

        mkdir -p (Join-Path $testSkillsDir "roles" "engineer" "engineer-skill")
        "Engineer Skill content" > (Join-Path $testSkillsDir "roles" "engineer" "engineer-skill" "SKILL.md")

        mkdir -p (Join-Path $testSkillsDir "lang")
        "Lang Skill content" > (Join-Path $testSkillsDir "lang" "SKILL.md")

        mkdir -p $testRolePath
        @{
            name = "engineer"
            skill_refs = @("lang")
        } | ConvertTo-Json > (Join-Path $testRolePath "role.json")
    }

    AfterAll {
        if (Test-Path $testSkillsDir) { Remove-Item $testSkillsDir -Recurse -Force }
        if (Test-Path $testRolePath) { Remove-Item $testRolePath -Recurse -Force }
    }

    It "resolves all tiers for an engineer role" {
        $skills = & (Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1") -RoleName "engineer" -RolePath $testRolePath -SkillsBaseDir $testSkillsDir

        $skills.Count | Should -Be 3
        ($skills | Where-Object { $_.Name -eq "global-skill" }).Tier | Should -Be "Global"
        ($skills | Where-Object { $_.Name -eq "engineer-skill" }).Tier | Should -Be "Role"
        ($skills | Where-Object { $_.Name -eq "lang" }).Tier | Should -Be "Explicit"
    }

    It "deduplicates skills (Role overrides Global)" {
        # Setup duplicate skill in Role
        mkdir -p (Join-Path $testSkillsDir "roles" "engineer" "global-skill")
        "Overridden Global Skill content" > (Join-Path $testSkillsDir "roles" "engineer" "global-skill" "SKILL.md")

        $skills = & (Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1") -RoleName "engineer" -RolePath $testRolePath -SkillsBaseDir $testSkillsDir
        $skills.Count | Should -Be 3
        ($skills | Where-Object { $_.Name -eq "global-skill" }).Tier | Should -Be "Role"
    }

    It "deduplicates skills (Explicit overrides Role)" {
        # Setup duplicate skill in skill_refs
        # Update role.json to include engineer-skill as ref
        @{
            name = "engineer"
            skill_refs = @("lang", "engineer-skill")
        } | ConvertTo-Json > (Join-Path $testRolePath "role.json")

        # engineer-skill needs to be in base skills/ too for explicit ref to work if it's not in role-specific dir
        mkdir -p (Join-Path $testSkillsDir "engineer-skill")
        "Explicit Engineer Skill content" > (Join-Path $testSkillsDir "engineer-skill" "SKILL.md")

        $skills = & (Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1") -RoleName "engineer" -RolePath $testRolePath -SkillsBaseDir $testSkillsDir
        $skills.Count | Should -Be 3
        ($skills | Where-Object { $_.Name -eq "engineer-skill" }).Tier | Should -Be "Explicit"
    }

    It "throws error for missing explicit skill" {
        @{
            name = "engineer"
            skill_refs = @("non-existent-skill")
        } | ConvertTo-Json > (Join-Path $testRolePath "role.json")

        { & (Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1") -RoleName "engineer" -RolePath $testRolePath -SkillsBaseDir $testSkillsDir } | Should -Throw "Skill Not Found*"
    }
}
