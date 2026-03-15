# Agent OS — Remove-WarRoom Pester Tests

BeforeAll {
    $script:NewWarRoom = Join-Path $PSScriptRoot "New-WarRoom.ps1"
    $script:RemoveWarRoom = Join-Path $PSScriptRoot "Remove-WarRoom.ps1"
}

Describe "Remove-WarRoom" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null
    }

    Context "Basic teardown" {
        BeforeEach {
            & $script:NewWarRoom -RoomId "room-del" -TaskRef "TASK-DEL" `
                                 -TaskDescription "To be deleted" -WarRoomsDir $script:warRoomsDir
        }

        It "removes the war-room directory" {
            $roomDir = Join-Path $script:warRoomsDir "room-del"
            Test-Path $roomDir | Should -BeTrue

            & $script:RemoveWarRoom -RoomId "room-del" -WarRoomsDir $script:warRoomsDir

            Test-Path $roomDir | Should -BeFalse
        }

        It "outputs teardown confirmation" {
            $output = & $script:RemoveWarRoom -RoomId "room-del" -WarRoomsDir $script:warRoomsDir
            ($output -join "`n") | Should -Match "TEARDOWN.*room-del.*removed"
        }
    }

    Context "Error handling" {
        It "fails when room doesn't exist" {
            $output = & $script:RemoveWarRoom -RoomId "nonexistent" -WarRoomsDir $script:warRoomsDir 2>&1
            $output | Should -Match "not found"
        }
    }

    Context "Archive mode" {
        BeforeEach {
            & $script:NewWarRoom -RoomId "room-arch" -TaskRef "EPIC-ARCH" `
                                 -TaskDescription "To be archived" `
                                 -WarRoomsDir $script:warRoomsDir `
                                 -DefinitionOfDone @("Goal 1", "Goal 2")

            # Add some audit entries
            $roomDir = Join-Path $script:warRoomsDir "room-arch"
            "2026-01-01T00:00:00Z STATUS pending -> engineering" |
                Out-File -Append -FilePath (Join-Path $roomDir "audit.log")
        }

        It "archives channel.jsonl before removal" {
            & $script:RemoveWarRoom -RoomId "room-arch" -Archive -WarRoomsDir $script:warRoomsDir

            $archiveDir = Join-Path $script:warRoomsDir ".archives"
            Test-Path $archiveDir | Should -BeTrue

            $archiveFiles = Get-ChildItem $archiveDir -Filter "room-arch-*.jsonl"
            $archiveFiles.Count | Should -Be 1
        }

        It "archives config.json before removal" {
            & $script:RemoveWarRoom -RoomId "room-arch" -Archive -WarRoomsDir $script:warRoomsDir

            $archiveDir = Join-Path $script:warRoomsDir ".archives"
            $configFiles = Get-ChildItem $archiveDir -Filter "room-arch-*-config.json"
            $configFiles.Count | Should -Be 1

            # Verify archived config has goals
            $config = Get-Content $configFiles[0].FullName -Raw | ConvertFrom-Json
            $config.goals.definition_of_done.Count | Should -Be 2
        }

        It "archives audit.log before removal" {
            & $script:RemoveWarRoom -RoomId "room-arch" -Archive -WarRoomsDir $script:warRoomsDir

            $archiveDir = Join-Path $script:warRoomsDir ".archives"
            $auditFiles = Get-ChildItem $archiveDir -Filter "room-arch-*-audit.log"
            $auditFiles.Count | Should -Be 1
        }

        It "archives goal-verification.json when it exists" {
            # Create a goal verification file
            $roomDir = Join-Path $script:warRoomsDir "room-arch"
            @{ goals = @(@{ goal = "Goal 1"; status = "met" }) } |
                ConvertTo-Json -Depth 5 |
                Out-File (Join-Path $roomDir "goal-verification.json") -Encoding utf8

            & $script:RemoveWarRoom -RoomId "room-arch" -Archive -WarRoomsDir $script:warRoomsDir

            $archiveDir = Join-Path $script:warRoomsDir ".archives"
            $goalFiles = Get-ChildItem $archiveDir -Filter "room-arch-*-goals.json"
            $goalFiles.Count | Should -Be 1
        }

        It "removes the room directory after archiving" {
            & $script:RemoveWarRoom -RoomId "room-arch" -Archive -WarRoomsDir $script:warRoomsDir

            $roomDir = Join-Path $script:warRoomsDir "room-arch"
            Test-Path $roomDir | Should -BeFalse
        }
    }

    Context "Without archive" {
        BeforeEach {
            & $script:NewWarRoom -RoomId "room-noarch" -TaskRef "TASK-NA" `
                                 -TaskDescription "No archive" -WarRoomsDir $script:warRoomsDir
        }

        It "does not create archive directory" {
            & $script:RemoveWarRoom -RoomId "room-noarch" -WarRoomsDir $script:warRoomsDir

            $archiveDir = Join-Path $script:warRoomsDir ".archives"
            Test-Path $archiveDir | Should -BeFalse
        }
    }

    Context "Force mode" {
        BeforeEach {
            & $script:NewWarRoom -RoomId "room-force" -TaskRef "TASK-FORCE" `
                                 -TaskDescription "Force kill" -WarRoomsDir $script:warRoomsDir
        }

        It "removes the room without waiting for graceful shutdown" {
            & $script:RemoveWarRoom -RoomId "room-force" -Force -WarRoomsDir $script:warRoomsDir
            Test-Path (Join-Path $script:warRoomsDir "room-force") | Should -BeFalse
        }
    }
}
