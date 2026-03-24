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

# Section 4: Skills — NOT concatenated into the prompt.
# Skills are resolved and copied to AGENT_OS_SKILLS_DIR by Invoke-Agent.ps1.
# The agent CLI discovers them via that path at runtime.
# This keeps the system prompt focused on the role definition only.

# Section 4.5: Memory context and tools
$memoryEnabled = $false
try {
    $cfgPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
               else { Join-Path (Split-Path (Split-Path $PSScriptRoot)) "config.json" }
    if (Test-Path $cfgPath) {
        $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
        $memoryEnabled = [bool]($cfg.memory -and $cfg.memory.enabled)
    }
} catch {}

if ($memoryEnabled) {
    $sections.Add(@"

## Memory Tools

You have memory tools to persist knowledge across sessions:
- **memory_note(note, domains?, is_mistake?)**: Save a discovery, gotcha, or pattern. Tag with domains (e.g. ["api", "auth"]).
- **memory_drop(note_substring)**: Remove a previously saved note.
- **memory_recall(domains?, keyword?)**: Query the knowledge base for facts from past sessions.

### How to use memory effectively
1. **At task START**: Call ``memory_recall`` with domains relevant to your task. Check for known patterns, conventions, and past mistakes.
2. **Pay special attention to mistakes**: Facts from QA feedback represent hard-won lessons. Follow them carefully.
3. **Save discoveries immediately**: When you discover something non-obvious about the codebase, save it with ``memory_note`` right away.
4. **Tag domains accurately**: Good domain tags make facts discoverable in future sessions.

Save notes when you discover: non-obvious conventions, mistakes and correct approaches, environment/config gotchas, project-specific patterns.
Do NOT save: obvious things from the code, task-specific details that won't generalize, temporary state.
"@)

    $resolveMemory = Join-Path $PSScriptRoot "Resolve-Memory.ps1"
    if ($RoomDir -and (Test-Path $resolveMemory)) {
        try {
            $memorySection = & $resolveMemory -RoomDir $RoomDir -RoleName ($role.Name)
            if ($memorySection) {
                $sections.Add($memorySection)
            }
        }
        catch {
            Write-Warning "Memory retrieval failed: $($_.Exception.Message)"
        }
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
