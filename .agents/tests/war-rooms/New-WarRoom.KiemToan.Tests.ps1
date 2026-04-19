#Requires -Version 7.0
#Requires -Modules Pester
# ============================================================
# New-WarRoom.KiemToan.Tests.ps1
# Integration tests for the Vietnamese Audit Plan (DVCTT v3.0)
# Verifies that New-WarRoom.ps1 correctly:
#  - Extracts ### Tasks from TaskDescription into TASKS.md
#  - Excludes ### Tasks from brief.md
#  - Preserves non-task sections (Mục tiêu, tables, DoD, AC)
#  - Handles Vietnamese UTF-8 content correctly
#  - Maintains correct behavior for all 3 EPICs
# ============================================================

BeforeAll {
    $script:NewWarRoom = Resolve-Path "$PSScriptRoot/../../war-rooms/New-WarRoom.ps1"
    $script:FixturesDir = "$PSScriptRoot/fixtures"

    # Set up a shared temp war-rooms directory for this test run
    $script:warRoomsDir = Join-Path $TestDrive "kiemtoan-warrooms-$(Get-Random)"
    New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

    # Load EPIC fixtures (TaskDescription content for each EPIC)
    . "$script:FixturesDir/kiemtoan_plan.ps1"

    # Create all three rooms upfront so every Context can access them
    & $script:NewWarRoom `
        -RoomId "room-001" `
        -TaskRef "EPIC-001" `
        -TaskDescription $Script:Epic001_TaskDescription `
        -DefinitionOfDone $Script:Epic001_DoD `
        -WarRoomsDir $script:warRoomsDir

    & $script:NewWarRoom `
        -RoomId "room-002" `
        -TaskRef "EPIC-002" `
        -TaskDescription $Script:Epic002_TaskDescription `
        -DefinitionOfDone $Script:Epic002_DoD `
        -WarRoomsDir $script:warRoomsDir

    & $script:NewWarRoom `
        -RoomId "room-003" `
        -TaskRef "EPIC-003" `
        -TaskDescription $Script:Epic003_TaskDescription `
        -DefinitionOfDone $Script:Epic003_DoD `
        -AcceptanceCriteria $Script:Epic003_AC `
        -WarRoomsDir $script:warRoomsDir
}

Describe "KiemToan Plan v3.0 — New-WarRoom parsing" {

    # ──────────────────────────────────────────────
    # EPIC-001: Quét & Phân loại Kho /audit-docs
    # ──────────────────────────────────────────────
    Context "EPIC-001 (room-001) — Scanner & Classification" {
        BeforeAll {
            $script:brief001 = Get-Content (Join-Path $script:warRoomsDir "room-001" "brief.md") -Raw
            $script:tasks001 = Get-Content (Join-Path $script:warRoomsDir "room-001" "TASKS.md") -Raw
        }

        It "room-001: brief.md is created" {
            Join-Path $script:warRoomsDir "room-001" "brief.md" | Should -Exist
        }

        It "room-001: TASKS.md is created for EPIC type" {
            Join-Path $script:warRoomsDir "room-001" "TASKS.md" | Should -Exist
        }

        It "room-001: brief.md contains EPIC-001 header" {
            $script:brief001 | Should -Match "EPIC-001"
        }

        It "room-001: brief.md contains Vietnamese objective (Mục tiêu)" {
            $script:brief001 | Should -Match "Mục tiêu"
        }

        It "room-001: brief.md does NOT contain ### Tasks heading" {
            $script:brief001 | Should -Not -Match "### Tasks"
        }

        It "room-001: brief.md does NOT contain TASK-1.1 checklist item" {
            $script:brief001 | Should -Not -Match "TASK-1\.1"
        }

        It "room-001: brief.md does NOT contain TASK-1.6 checklist item" {
            $script:brief001 | Should -Not -Match "TASK-1\.6"
        }

        It "room-001: brief.md contains Definition of Done section (from params)" {
            $script:brief001 | Should -Match "## Definition of Done"
        }

        It "room-001: brief.md DoD mentions 4 nhóm SAV" {
            $script:brief001 | Should -Match "4 nhóm SAV"
        }

        It "room-001: brief.md preserves Vietnamese UTF-8 characters" {
            $script:brief001 | Should -Match "tài liệu"
            $script:brief001 | Should -Match "phân loại"
        }

        It "room-001: TASKS.md contains TASK-1.1 (Scanner)" {
            $script:tasks001 | Should -Match "TASK-1\.1"
        }

        It "room-001: TASKS.md contains TASK-1.2 (SAV Classification)" {
            $script:tasks001 | Should -Match "TASK-1\.2"
        }

        It "room-001: TASKS.md contains TASK-1.3 (SAV Appendix mapping)" {
            $script:tasks001 | Should -Match "TASK-1\.3"
        }

        It "room-001: TASKS.md contains TASK-1.4 (LLM Fact Extraction)" {
            $script:tasks001 | Should -Match "TASK-1\.4"
        }

        It "room-001: TASKS.md contains TASK-1.5 (Cross-reference)" {
            $script:tasks001 | Should -Match "TASK-1\.5"
        }

        It "room-001: TASKS.md contains TASK-1.6 (Capability Map)" {
            $script:tasks001 | Should -Match "TASK-1\.6"
        }

        It "room-001: TASKS.md does NOT contain Definition of Done" {
            $script:tasks001 | Should -Not -Match "Definition of Done"
        }

        It "room-001: TASKS.md does NOT contain Coverage chunking DoD item" {
            $script:tasks001 | Should -Not -Match "Coverage chunking"
        }

        It "room-001: TASKS.md references EPIC-001" {
            $script:tasks001 | Should -Match "EPIC-001"
        }

        It "room-001: TASKS.md preserves Vietnamese task descriptions" {
            $script:tasks001 | Should -Match "Scanner đệ quy"
            $script:tasks001 | Should -Match "Phân loại"
        }
    }

    # ──────────────────────────────────────────────
    # EPIC-002: ETL & Data Aggregation
    # ──────────────────────────────────────────────
    Context "EPIC-002 (room-002) — ETL Pipeline" {
        BeforeAll {
            $script:brief002 = Get-Content (Join-Path $script:warRoomsDir "room-002" "brief.md") -Raw
            $script:tasks002 = Get-Content (Join-Path $script:warRoomsDir "room-002" "TASKS.md") -Raw
        }

        It "room-002: brief.md is created" {
            Join-Path $script:warRoomsDir "room-002" "brief.md" | Should -Exist
        }

        It "room-002: TASKS.md is created" {
            Join-Path $script:warRoomsDir "room-002" "TASKS.md" | Should -Exist
        }

        It "room-002: brief.md contains EPIC-002 header" {
            $script:brief002 | Should -Match "EPIC-002"
        }

        It "room-002: brief.md contains ETL Mục tiêu (description)" {
            $script:brief002 | Should -Match "ETL pipeline idempotent"
        }

        It "room-002: brief.md preserves data source table (Kho dữ liệu)" {
            $script:brief002 | Should -Match "Kho dữ liệu"
            $script:brief002 | Should -Match "pl02_plans"
        }

        It "room-002: brief.md does NOT contain ### Tasks heading" {
            $script:brief002 | Should -Not -Match "### Tasks"
        }

        It "room-002: brief.md does NOT contain TASK-2.1" {
            $script:brief002 | Should -Not -Match "TASK-2\.1"
        }

        It "room-002: brief.md does NOT contain TASK-2.6 (KPI Views)" {
            $script:brief002 | Should -Not -Match "TASK-2\.6"
        }

        It "room-002: brief.md contains Definition of Done (from params)" {
            $script:brief002 | Should -Match "## Definition of Done"
        }

        It "room-002: brief.md DoD mentions idempotent pipeline" {
            $script:brief002 | Should -Match "idempotent"
        }

        It "room-002: TASKS.md contains TASK-2.1 (File Discovery)" {
            $script:tasks002 | Should -Match "TASK-2\.1"
        }

        It "room-002: TASKS.md contains TASK-2.2 (Schema Inference)" {
            $script:tasks002 | Should -Match "TASK-2\.2"
        }

        It "room-002: TASKS.md contains TASK-2.3 (Data Validators)" {
            $script:tasks002 | Should -Match "TASK-2\.3"
        }

        It "room-002: TASKS.md contains TASK-2.4 (Merge-cell handler)" {
            $script:tasks002 | Should -Match "TASK-2\.4"
        }

        It "room-002: TASKS.md contains TASK-2.5 (Idempotent ETL)" {
            $script:tasks002 | Should -Match "TASK-2\.5"
        }

        It "room-002: TASKS.md contains TASK-2.6 (KPI Views)" {
            $script:tasks002 | Should -Match "TASK-2\.6"
        }

        It "room-002: TASKS.md does NOT contain Definition of Done" {
            $script:tasks002 | Should -Not -Match "Definition of Done"
        }

        It "room-002: TASKS.md references EPIC-002" {
            $script:tasks002 | Should -Match "EPIC-002"
        }

        It "room-002: TASKS.md preserves Vietnamese task names" {
            $script:tasks002 | Should -Match "Schema Inference"
            $script:tasks002 | Should -Match "Idempotent ETL"
        }
    }

    # ──────────────────────────────────────────────
    # EPIC-003: Dashboard & SAV Report Export
    # ──────────────────────────────────────────────
    Context "EPIC-003 (room-003) — Dashboard & SAV Export" {
        BeforeAll {
            $script:brief003 = Get-Content (Join-Path $script:warRoomsDir "room-003" "brief.md") -Raw
            $script:tasks003 = Get-Content (Join-Path $script:warRoomsDir "room-003" "TASKS.md") -Raw
        }

        It "room-003: brief.md is created" {
            Join-Path $script:warRoomsDir "room-003" "brief.md" | Should -Exist
        }

        It "room-003: TASKS.md is created" {
            Join-Path $script:warRoomsDir "room-003" "TASKS.md" | Should -Exist
        }

        It "room-003: brief.md contains EPIC-003 reference" {
            $script:brief003 | Should -Match "EPIC-003"
        }

        It "room-003: brief.md does NOT contain ### Tasks heading" {
            $script:brief003 | Should -Not -Match "### Tasks"
        }

        It "room-003: brief.md does NOT contain TASK-3.1" {
            $script:brief003 | Should -Not -Match "TASK-3\.1"
        }

        It "room-003: brief.md does NOT contain TASK-3.8 (E2E test)" {
            $script:brief003 | Should -Not -Match "TASK-3\.8"
        }

        It "room-003: brief.md contains Definition of Done section" {
            $script:brief003 | Should -Match "## Definition of Done"
        }

        It "room-003: brief.md contains Acceptance Criteria section" {
            $script:brief003 | Should -Match "## Acceptance Criteria"
        }

        It "room-003: brief.md AC mentions báo cáo về năng lực" {
            $script:brief003 | Should -Match "năng lực"
        }

        It "room-003: TASKS.md contains TASK-3.1 (Compliance Matrix)" {
            $script:tasks003 | Should -Match "TASK-3\.1"
        }

        It "room-003: TASKS.md contains TASK-3.2 (Time Period Filter)" {
            $script:tasks003 | Should -Match "TASK-3\.2"
        }

        It "room-003: TASKS.md contains TASK-3.3 (5 Dashboard Views)" {
            $script:tasks003 | Should -Match "TASK-3\.3"
        }

        It "room-003: TASKS.md contains TASK-3.4 (Click-to-Source)" {
            $script:tasks003 | Should -Match "TASK-3\.4"
        }

        It "room-003: TASKS.md contains TASK-3.5 (Justification Form)" {
            $script:tasks003 | Should -Match "TASK-3\.5"
        }

        It "room-003: TASKS.md contains TASK-3.6 (Export Engine)" {
            $script:tasks003 | Should -Match "TASK-3\.6"
        }

        It "room-003: TASKS.md contains TASK-3.7 (RBAC)" {
            $script:tasks003 | Should -Match "TASK-3\.7"
        }

        It "room-003: TASKS.md contains TASK-3.8 (E2E Test)" {
            $script:tasks003 | Should -Match "TASK-3\.8"
        }

        It "room-003: TASKS.md does NOT contain Definition of Done" {
            $script:tasks003 | Should -Not -Match "Definition of Done"
        }

        It "room-003: TASKS.md does NOT contain Acceptance Criteria" {
            $script:tasks003 | Should -Not -Match "Acceptance Criteria"
        }

        It "room-003: TASKS.md preserves traffic-light formula content" {
            $script:tasks003 | Should -Match "GREEN"
            $script:tasks003 | Should -Match "YELLOW"
        }

        It "room-003: TASKS.md references EPIC-003" {
            $script:tasks003 | Should -Match "EPIC-003"
        }
    }

    # ──────────────────────────────────────────────
    # Cross-room: No file contamination between rooms
    # ──────────────────────────────────────────────
    Context "Cross-room isolation" {
        It "room-001 TASKS.md does not contain EPIC-002 tasks" {
            $t = Get-Content (Join-Path $script:warRoomsDir "room-001" "TASKS.md") -Raw
            $t | Should -Not -Match "TASK-2\."
        }

        It "room-002 TASKS.md does not contain EPIC-001 tasks" {
            $t = Get-Content (Join-Path $script:warRoomsDir "room-002" "TASKS.md") -Raw
            $t | Should -Not -Match "TASK-1\."
        }

        It "room-003 TASKS.md does not contain EPIC-001 tasks" {
            $t = Get-Content (Join-Path $script:warRoomsDir "room-003" "TASKS.md") -Raw
            $t | Should -Not -Match "TASK-1\."
        }

        It "room-001 brief.md does not contain room-002 ETL content" {
            $b = Get-Content (Join-Path $script:warRoomsDir "room-001" "brief.md") -Raw
            $b | Should -Not -Match "ETL pipeline"
        }

        It "all three rooms have their status files" {
            foreach ($room in @("room-001", "room-002", "room-003")) {
                Join-Path $script:warRoomsDir $room "status" | Should -Exist
            }
        }

        It "all three rooms have their task-ref files" {
            @("room-001", "room-002", "room-003") | ForEach-Object {
                Join-Path $script:warRoomsDir $_ "task-ref" | Should -Exist
            }
        }

        It "task-ref files contain correct EPIC references" {
            Get-Content (Join-Path $script:warRoomsDir "room-001" "task-ref") | Should -Be "EPIC-001"
            Get-Content (Join-Path $script:warRoomsDir "room-002" "task-ref") | Should -Be "EPIC-002"
            Get-Content (Join-Path $script:warRoomsDir "room-003" "task-ref") | Should -Be "EPIC-003"
        }
    }
}
