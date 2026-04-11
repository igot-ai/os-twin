#Requires -Version 7.0
# Agent OS — Plan Parser Module
#
# Import:
#   Import-Module "$PSScriptRoot/PlanParser.psm1"
#
# Provides: Markdown plan parsing — extracts structured epic/task objects
# from a plan markdown file using regex patterns.
#
# This module is the SINGLE SOURCE OF TRUTH for plan-parsing logic.
# Previously duplicated in Start-Plan.ps1 (top-level parse + New-PlanWarRooms).

function ConvertFrom-PlanMarkdown {
    <#
    .SYNOPSIS
        Parses a plan markdown file and returns structured epic/task objects.
    .DESCRIPTION
        Extracts epics (## EPIC-NNN - Description) and standalone tasks
        (- [ ] TASK-NNN - Description) from markdown content. For each epic,
        extracts metadata directives (Role, Objective, Working_dir, Pipeline,
        Capabilities, Lifecycle), Definition of Done, Acceptance Criteria,
        description body, and dependency declarations.
    .PARAMETER Content
        Raw markdown content of the plan file.
    .OUTPUTS
        System.Collections.Generic.List[PSObject] — list of parsed epic/task entries.
    #>
    [CmdletBinding()]
    [OutputType([System.Collections.Generic.List[PSObject]])]
    param(
        [Parameter(Mandatory)]
        [string]$Content
    )

    # --- Regex patterns for plan structure ---
    $epicPattern        = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-\u2014\u2013?]\s*(.+)$'
    $taskPattern        = '(?m)^\s*[-*]\s+\[[ x]\]\s+(TASK-\d+)\s*[-\u2014\u2013]\s*(.+)$'
    $dodPattern         = '(?s)#### Definition of Done\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $acPattern          = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $depsPattern        = '(?m)^\s*depends_on:\s*\[([^\]]*)\]\s*$'
    $rolesPattern       = '(?m)^Roles?:\s*(.+)$'
    $objectivePattern   = '(?m)^Objective:\s*(.+)$'
    $workingDirPattern  = '(?m)^Working_dir:\s*(.+)$'
    $pipelinePattern    = '(?m)^Pipeline:\s*(.+)$'
    $capabilitiesPattern = '(?m)^Capabilities:\s*(.+)$'
    $descPattern        = '(?s)^#{2,3}\s+EPIC-\d+\s*[-\u2014\u2013?]\s*.+?\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $lifecyclePattern   = '(?ism)^Lifecycle:[^\S\r\n]*\r?\n[^\S\r\n]*```[a-z]*\r?\n(.*?)\r?\n[^\S\r\n]*```'

    $parsed = [System.Collections.Generic.List[PSObject]]::new()
    $roomIndex = 1

    # --- Extract epics ---
    $epicMatches = [regex]::Matches($Content, $epicPattern)

    foreach ($em in $epicMatches) {
        $epicRef  = $em.Groups[1].Value
        $epicDesc = $em.Groups[2].Value.Trim()

        # Determine the epic section boundaries
        $epicStart = $em.Index
        $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1

        # EPIC-END: next EPIC header or next level-2 header
        $nextSectionMatch = [regex]::Matches($Content, '(?m)^##\s+') |
            Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1

        $epicEnd = $Content.Length
        if ($nextEpicMatch) {
            $epicEnd = $nextEpicMatch.Index
        } elseif ($nextSectionMatch) {
            $epicEnd = $nextSectionMatch.Index
        }

        $epicSection = $Content.Substring($epicStart, $epicEnd - $epicStart)

        # --- Extract Roles (comma-separated, stripping comments and placeholders) ---
        $roles = [System.Collections.Generic.List[string]]::new()
        $hasExplicitRoles = $false
        $roleMatches = [regex]::Matches($epicSection, $rolesPattern)
        if ($roleMatches.Count -gt 0) {
            $hasExplicitRoles = $true
        }
        foreach ($rm in $roleMatches) {
            $line = $rm.Groups[1].Value
            $line = $line -replace '\(.*$', ''     # strip inline comments
            $items = ($line -split ',') |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
            foreach ($item in $items) {
                if (-not $roles.Contains($item)) { $roles.Add($item) }
            }
        }
        if ($roles.Count -eq 0) { $roles.Add("engineer") }

        # --- Extract Objective ---
        $epicObjective = ""
        if ($epicSection -match $objectivePattern) {
            $epicObjective = $Matches[1].Trim()
        }

        # --- Extract per-epic working directory override ---
        $epicWorkingDir = ""
        if ($epicSection -match $workingDirPattern) {
            $epicWorkingDir = $Matches[1].Trim()
        }

        # --- Extract description body ---
        $descBody = ""
        if ($epicSection -match $descPattern) {
            $descBody = $Matches[1].Trim()
        }

        # --- Extract Pipeline directive ---
        $epicPipeline = ""
        if ($epicSection -match $pipelinePattern) {
            $epicPipeline = $Matches[1].Trim()
        }

        # --- Extract Capabilities directive ---
        $epicCapabilities = @()
        if ($epicSection -match $capabilitiesPattern) {
            $epicCapabilities = ($Matches[1].Trim() -split ',') |
                ForEach-Object { $_.Trim() } | Where-Object { $_ }
        }

        # --- Extract Lifecycle directive ---
        $epicLifecycle = ""
        if ($epicSection -match $lifecyclePattern) {
            $epicLifecycle = $Matches[1].Trim()
        }

        # --- Extract Definition of Done ---
        $dod = @()
        if ($epicSection -match $dodPattern) {
            $dodBlock = $Matches[1]
            $dod = [regex]::Matches($dodBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') |
                ForEach-Object { $_.Groups[1].Value.Trim() }
        }

        # --- Extract Acceptance Criteria ---
        $ac = @()
        if ($epicSection -match $acPattern) {
            $acBlock = $Matches[1]
            $ac = [regex]::Matches($acBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') |
                ForEach-Object { $_.Groups[1].Value.Trim() }
        }

        # --- Extract depends_on ---
        $depsOn = @()
        if ($epicSection -match $depsPattern) {
            $rawDeps = $Matches[1]
            if ($rawDeps.Trim()) {
                $depsOn = ($rawDeps -split ',') |
                    ForEach-Object { $_.Trim().Trim('"').Trim("'") } |
                    Where-Object { $_ }
            }
        }

        $parsed.Add([PSCustomObject]@{
            RoomId           = "room-$('{0:D3}' -f $roomIndex)"
            TaskRef          = $epicRef
            Description      = $epicDesc
            DescBody         = $descBody
            Objective        = $epicObjective
            DoD              = $dod
            AC               = $ac
            DependsOn        = $depsOn
            Type             = 'epic'
            Roles            = @($roles)
            HasExplicitRoles = $hasExplicitRoles
            EpicWorkingDir   = $epicWorkingDir
            Pipeline         = $epicPipeline
            Capabilities     = $epicCapabilities
            Lifecycle        = $epicLifecycle
        })
        $roomIndex++
    }

    # --- Extract standalone tasks (not inside any epic block) ---
    $taskMatches = [regex]::Matches($Content, $taskPattern)
    foreach ($tm in $taskMatches) {
        $isInsideEpic = $false
        foreach ($em in $epicMatches) {
            $epicStart = $em.Index
            $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1

            $nextSec = [regex]::Matches($Content, '(?m)^##\s+') |
                Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
            $epicEnd = $Content.Length
            if ($nextEpicMatch) { $epicEnd = $nextEpicMatch.Index }
            elseif ($nextSec) { $epicEnd = $nextSec.Index }

            if ($tm.Index -ge $epicStart -and $tm.Index -lt $epicEnd) {
                $isInsideEpic = $true
                break
            }
        }

        if (-not $isInsideEpic) {
            $taskRef = $tm.Groups[1].Value
            # Avoid duplicates if already parsed
            if (-not ($parsed | Where-Object { $_.TaskRef -eq $taskRef })) {
                $parsed.Add([PSCustomObject]@{
                    RoomId           = "room-$('{0:D3}' -f $roomIndex)"
                    TaskRef          = $taskRef
                    Description      = $tm.Groups[2].Value.Trim()
                    DescBody         = ""
                    Objective        = ""
                    DoD              = @()
                    AC               = @()
                    DependsOn        = @()
                    Type             = 'task'
                    Roles            = @("engineer")
                    HasExplicitRoles = $false
                    EpicWorkingDir   = ""
                    Pipeline         = ""
                    Capabilities     = @()
                    Lifecycle        = ""
                })
                $roomIndex++
            }
        }
    }

    return $parsed
}

Export-ModuleMember -Function ConvertFrom-PlanMarkdown
