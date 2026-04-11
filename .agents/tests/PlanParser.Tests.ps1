#Requires -Version 7.0
# Agent OS — PlanParser Module Pester Tests
#
# Tests for ConvertFrom-PlanMarkdown: epic/task extraction, metadata parsing,
# dependency resolution, role defaults, and edge cases.

BeforeAll {
    Import-Module (Join-Path (Resolve-Path "$PSScriptRoot/../.agents/lib").Path "PlanParser.psm1") -Force
}

AfterAll {
    Remove-Module -Name "PlanParser" -ErrorAction SilentlyContinue
}

Describe 'ConvertFrom-PlanMarkdown' {
    It 'parses a single epic with DoD and AC' {
        $md = @"
## EPIC-001 - Build Auth Module

Implement JWT authentication.

#### Definition of Done
- [ ] JWT tokens generated
- [ ] Refresh tokens work
- [ ] Tests pass

#### Acceptance Criteria
- [ ] POST /login returns 200
- [ ] Expired tokens return 401

depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result.Count | Should -Be 1
        $result[0].TaskRef | Should -Be 'EPIC-001'
        $result[0].DoD.Count | Should -Be 3
        $result[0].AC.Count | Should -Be 2
        $result[0].DependsOn.Count | Should -Be 0
        $result[0].Type | Should -Be 'epic'
    }

    It 'parses multiple epics with dependencies' {
        $md = @"
## EPIC-001 - First Epic
Description here.
#### Definition of Done
- [ ] Done 1
- [ ] Done 2
- [ ] Done 3
- [ ] Done 4
- [ ] Done 5
#### Acceptance Criteria
- [ ] AC 1
- [ ] AC 2
- [ ] AC 3
- [ ] AC 4
- [ ] AC 5
depends_on: []

## EPIC-002 - Second Epic
Depends on first.
#### Definition of Done
- [ ] Done A
- [ ] Done B
- [ ] Done C
- [ ] Done D
- [ ] Done E
#### Acceptance Criteria
- [ ] AC A
- [ ] AC B
- [ ] AC C
- [ ] AC D
- [ ] AC E
depends_on: ["EPIC-001"]
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result.Count | Should -Be 2
        $result[1].DependsOn | Should -Contain 'EPIC-001'
    }

    It 'parses Role/Roles directive' {
        $md = @"
## EPIC-001 - Test
Role: engineer:fe
Objective: Build the frontend
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].Roles | Should -Contain 'engineer:fe'
    }

    It 'defaults role to engineer when no Role directive' {
        $md = @"
## EPIC-001 - No Role Specified
Some description.
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].Roles | Should -Contain 'engineer'
    }

    It 'returns empty list for content with no epics' {
        $result = ConvertFrom-PlanMarkdown -Content "# Just a title"
        $result.Count | Should -Be 0
    }

    It 'extracts standalone tasks outside epic blocks' {
        $md = @"
## EPIC-001 - An Epic
Desc.
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []

## Other Section
- [ ] TASK-099 - Standalone task
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $standaloneTask = $result | Where-Object { $_.TaskRef -eq 'TASK-099' }
        $standaloneTask | Should -Not -BeNullOrEmpty
        $standaloneTask.Type | Should -Be 'task'
    }

    It 'extracts Working_dir directive' {
        $md = @"
## EPIC-001 - Scoped
Working_dir: src/frontend
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].EpicWorkingDir | Should -Be 'src/frontend'
    }

    It 'extracts Objective directive' {
        $md = @"
## EPIC-001 - With Objective
Objective: Deliver a working MVP
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].Objective | Should -Be 'Deliver a working MVP'
    }

    It 'extracts Pipeline directive' {
        $md = @"
## EPIC-001 - CI Pipeline
Pipeline: build-test-deploy
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].Pipeline | Should -Be 'build-test-deploy'
    }

    It 'extracts Capabilities directive' {
        $md = @"
## EPIC-001 - With Caps
Capabilities: unity-editor, mcp-tools
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].Capabilities | Should -Contain 'unity-editor'
        $result[0].Capabilities | Should -Contain 'mcp-tools'
    }

    It 'assigns sequential room IDs' {
        $md = @"
## EPIC-001 - First
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []

## EPIC-002 - Second
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].RoomId | Should -Be 'room-001'
        $result[1].RoomId | Should -Be 'room-002'
    }

    It 'handles multiple comma-separated dependencies' {
        $md = @"
## EPIC-003 - Third
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: ["EPIC-001", "EPIC-002"]
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        $result[0].DependsOn.Count | Should -Be 2
        $result[0].DependsOn | Should -Contain 'EPIC-001'
        $result[0].DependsOn | Should -Contain 'EPIC-002'
    }

    It 'marks HasExplicitRoles correctly' {
        $mdWithRole = @"
## EPIC-001 - Has Role
Role: architect
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $mdWithoutRole = @"
## EPIC-002 - No Role
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $withRole = ConvertFrom-PlanMarkdown -Content $mdWithRole
        $withRole[0].HasExplicitRoles | Should -BeTrue

        $withoutRole = ConvertFrom-PlanMarkdown -Content $mdWithoutRole
        $withoutRole[0].HasExplicitRoles | Should -BeFalse
    }

    It 'does not duplicate tasks that appear inside an epic block' {
        $md = @"
## EPIC-001 - Contains Tasks
Some work items:
- [ ] TASK-001 - Sub task inside epic
#### Definition of Done
- [ ] Done
#### Acceptance Criteria
- [ ] AC
depends_on: []
"@
        $result = ConvertFrom-PlanMarkdown -Content $md
        # EPIC-001 should be parsed, but TASK-001 should NOT appear as standalone
        $result.Count | Should -Be 1
        $result[0].TaskRef | Should -Be 'EPIC-001'
    }
}
