<#
.SYNOPSIS
    Composes a full system prompt from role definition, skills, and war-room context.

.DESCRIPTION
    Reads a role definition (via Get-RoleDefinition), loads the ROLE.md prompt template,
    injects skill context files, war-room goals, and task context to produce
    a complete system prompt ready for the agent.

    Part of Epic 4 — Extensible Role Engine.

.PARAMETER RoleName
    Role name (engineer, qa, architect, etc.).
.PARAMETER RolePath
    Direct path to role directory (overrides RoleName).
.PARAMETER RoomDir
    Optional. War-room directory for context injection.
.PARAMETER TaskRef
    Optional. Task/Epic reference for context.
.PARAMETER TaskBody
    Optional. Latest task/fix body text.
.PARAMETER ExtraContext
    Optional. Additional context to append.

.OUTPUTS
    [string] The fully composed system prompt.

.EXAMPLE
    $prompt = ./Build-SystemPrompt.ps1 -RoleName "engineer" -RoomDir "./war-rooms/room-001"
#>
[CmdletBinding()]
param(
    [string]$RoleName = '',
    [string]$RolePath = '',
    [string]$RoomDir = '',
    [string]$TaskRef = '',
    [string]$TaskBody = '',
    [string]$ExtraContext = ''
)

$getRoleDef = Join-Path $PSScriptRoot "Get-RoleDefinition.ps1"

# --- Load role definition ---
$roleArgs = @{}
if ($RolePath) { $roleArgs['RolePath'] = $RolePath }
elseif ($RoleName) { $roleArgs['RoleName'] = $RoleName }
else {
    Write-Error "Either -RoleName or -RolePath must be specified."
    exit 1
}

$role = & $getRoleDef @roleArgs

# --- Start building the prompt ---
$sections = [System.Collections.Generic.List[string]]::new()

# Section 1: Role prompt template
if ($role.PromptTemplate) {
    $sections.Add($role.PromptTemplate)
}
else {
    $sections.Add("# $($role.Name)`n`nYou are a $($role.Description).")
}

# Section 2: Capabilities
if ($role.Capabilities -and $role.Capabilities.Count -gt 0) {
    $capList = ($role.Capabilities | ForEach-Object { "- $_" }) -join "`n"
    $sections.Add(@"

## Your Capabilities

$capList
"@)
}

# Section 3: Quality gates
if ($role.QualityGates -and $role.QualityGates.Count -gt 0) {
    $gateList = ($role.QualityGates | ForEach-Object { "- $_" }) -join "`n"
    $sections.Add(@"

## Quality Gates

You must satisfy these quality gates before marking work as done:

$gateList
"@)
}

# Section 4: Skills context
$resolveSkills = Join-Path $PSScriptRoot "Resolve-RoleSkills.ps1"
if (Test-Path $resolveSkills) {
    try {
        $skillsDir = Join-Path (Split-Path (Split-Path $PSScriptRoot)) "skills"
        
        # Testing override
        if ($ExtraContext -match 'FORCE_SKILLS_DIR=(.+)') {
            $skillsDir = $Matches[1].Trim()
        }

        $resolved = & $resolveSkills -RoleName $role.Name -RolePath $role.RolePath -SkillsBaseDir $skillsDir
        
        if ($resolved -and $resolved.Count -gt 0) {
            $sections.Add("`n## Skills`n")
            foreach ($skill in $resolved) {
                if (Test-Path $skill.Path) {
                    $rawContent = Get-Content $skill.Path -Raw
                    $content = $rawContent
                    
                    # Preflight check for tags/trust_level (EPIC-001)
                    $preflight = "warn"
                    try {
                        $configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG } else { Join-Path (Split-Path (Split-Path $PSScriptRoot)) "config.json" }
                        if (Test-Path $configPath) {
                            $fullConfig = Get-Content $configPath -Raw | ConvertFrom-Json
                            if ($fullConfig.manager.preflight_skill_check) { $preflight = $fullConfig.manager.preflight_skill_check }
                        }
                    } catch {}

                    # Strip YAML frontmatter if present and check metadata
                    if ($rawContent -match '(?s)^---\s*\n(.*?)\n---\s*\n(.*)$') {
                        $frontmatter = $Matches[1]
                        $content = $Matches[2]

                        if ($preflight -eq "warn") {
                            if ($frontmatter -notmatch 'tags\s*:' -or $frontmatter -notmatch 'trust_level\s*:') {
                                Write-Warning "Skill '$($skill.Name)' is missing required metadata (tags or trust_level) in SKILL.md frontmatter."
                            }
                        }
                    }
                    else {
                        if ($preflight -eq "warn") {
                            Write-Warning "Skill '$($skill.Name)' is missing YAML frontmatter in SKILL.md."
                        }
                    }
                    
                    $sections.Add(@"
### Skill: $($skill.Name) ($($skill.Tier))

$content
"@)
                }
            }
        }
    }
    catch {
        if ($_.ToString() -match "Skill Not Found") {
            Write-Error $_
            exit 1
        }
        Write-Warning "Failed to resolve skills: $_"
    }
}

# Section 5: War-room context
if ($RoomDir -and (Test-Path $RoomDir)) {
    # Task brief
    $briefFile = Join-Path $RoomDir "brief.md"
    if (Test-Path $briefFile) {
        $briefContent = Get-Content $briefFile -Raw
        $sections.Add(@"

---

## Task Assignment

$briefContent
"@)
    }

    # Goals from config.json
    $configFile = Join-Path $RoomDir "config.json"
    if (Test-Path $configFile) {
        try {
            $roomConfig = Get-Content $configFile -Raw | ConvertFrom-Json

            $goalSection = "`n## Goals`n"

            if ($roomConfig.goals.definition_of_done -and $roomConfig.goals.definition_of_done.Count -gt 0) {
                $goalSection += "`n### Definition of Done`n"
                foreach ($dod in $roomConfig.goals.definition_of_done) {
                    $goalSection += "- [ ] $dod`n"
                }
            }

            if ($roomConfig.goals.acceptance_criteria -and $roomConfig.goals.acceptance_criteria.Count -gt 0) {
                $goalSection += "`n### Acceptance Criteria`n"
                foreach ($ac in $roomConfig.goals.acceptance_criteria) {
                    $goalSection += "- [ ] $ac`n"
                }
            }

            if ($roomConfig.goals.quality_requirements) {
                $qr = $roomConfig.goals.quality_requirements
                $goalSection += "`n### Quality Requirements`n"
                $goalSection += "- Test coverage minimum: $($qr.test_coverage_min)%`n"
                $goalSection += "- Lint clean: $($qr.lint_clean)`n"
                $goalSection += "- Security scan pass: $($qr.security_scan_pass)`n"
            }

            $sections.Add($goalSection)
        }
        catch { }
    }

    # TASKS.md for epics
    $tasksFile = Join-Path $RoomDir "TASKS.md"
    if (Test-Path $tasksFile) {
        $tasksContent = Get-Content $tasksFile -Raw
        $sections.Add(@"

## Sub-Tasks (TASKS.md)

$tasksContent
"@)
    }

    # Previous QA feedback (for fix cycles)
    $channelDir = Join-Path (Split-Path $PSScriptRoot) ".." "channel"
    $readMessages = Join-Path $channelDir "Read-Messages.ps1"
    if (Test-Path $readMessages) {
        try {
            $failMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fail" -Last 1 -AsObject 2>$null
            if ($failMsgs -and $failMsgs.Count -gt 0) {
                $sections.Add(@"

## Previous QA Feedback (FIX THIS)

$($failMsgs[-1].body)
"@)
            }

            $fixMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fix" -Last 1 -AsObject 2>$null
            if ($fixMsgs -and $fixMsgs.Count -gt 0) {
                $sections.Add(@"

## Fix Instructions

$($fixMsgs[-1].body)
"@)
            }
        }
        catch { }
    }
}

# Section 6: Overrides
if ($TaskRef) {
    $sections.Add("`n## Task Reference: $TaskRef")
}

if ($TaskBody) {
    $sections.Add(@"

## Current Instruction

$TaskBody
"@)
}

if ($ExtraContext) {
    $sections.Add(@"

## Additional Context

$ExtraContext
"@)
}

# --- Compose final prompt ---
$finalPrompt = $sections -join "`n"

# --- Token Size Warning ---
$maxBytes = 102400 # Default fallback
try {
    $configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG } else { Join-Path (Split-Path (Split-Path $PSScriptRoot)) "config.json" }
    if (Test-Path $configPath) {
        $fullConfig = Get-Content $configPath -Raw | ConvertFrom-Json
        $roleNameLower = $role.Name.ToLower()
        if ($fullConfig.$roleNameLower.max_prompt_bytes) {
            $maxBytes = $fullConfig.$roleNameLower.max_prompt_bytes
        }
    }
} catch {}

$promptSize = [System.Text.Encoding]::UTF8.GetByteCount($finalPrompt)
if ($promptSize -gt $maxBytes) {
    Write-Warning "System prompt size ($promptSize bytes) exceeds threshold ($maxBytes bytes) for role '$($role.Name)'."
}

Write-Output $finalPrompt
