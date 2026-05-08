param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$RoleName,

    [Parameter(Position=1, Mandatory=$true)]
    [string]$AgentsDir,

    [string]$Description = '',

    [string[]]$Capabilities = @(),

    [string[]]$Skills = @(),

    [string]$Model = 'google-vertex/gemini-3-flash-preview',

    [int]$Timeout = 600,

    [string]$PromptContent = ''
)

$ErrorActionPreference = "Stop"

Write-Host "Creating missing role: $RoleName..."

$safeName = $RoleName -replace '[^a-zA-Z0-9\-]', '-' -replace '-+', '-' -replace '^-|-$', ''

# ── Phase 1: Fast programmatic scaffolding via New-DynamicRole.ps1 ──
$newDynamicRole = Join-Path $AgentsDir "roles" "_base" "New-DynamicRole.ps1"
$roleDir = $null

if (Test-Path $newDynamicRole) {
    Write-Host "  [1/4] Scaffolding role structure..."

    $scaffoldArgs = @{
        RoleName  = $RoleName
        AgentsDir = $AgentsDir
        Model     = $Model
        Timeout   = $Timeout
    }
    if ($Description)    { $scaffoldArgs['Description'] = $Description }
    if ($Capabilities.Count -gt 0) { $scaffoldArgs['Capabilities'] = $Capabilities }
    if ($Skills.Count -gt 0)       { $scaffoldArgs['Skills'] = $Skills }

    try {
        $roleDir = & $newDynamicRole @scaffoldArgs
        if ($roleDir -and (Test-Path $roleDir)) {
            Write-Host "  Role directory created at $roleDir"
        }
    } catch {
        Write-Warning "Fast scaffolding failed: $($_.Exception.Message). Falling back to full LLM agent..."
    }
} else {
    Write-Warning "New-DynamicRole.ps1 not found. Falling back to full LLM agent..."
}

if (-not $roleDir -or -not (Test-Path $roleDir)) {
    Write-Host "  Falling back to full LLM agent for role creation..."
    $OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $env:HOME ".ostwin" }
    $agentBin = if ($env:OSTWIN_AGENT_CMD) { $env:OSTWIN_AGENT_CMD } else { Join-Path $OstwinHome ".agents" "bin" "agent" }
    if (-not (Test-Path $agentBin)) {
        Write-Error "Agent binary not found at: $agentBin`nRun the installer or set `$OSTWIN_AGENT_CMD."
        exit 1
    }
    $ManagerPrompt = "We need a new agent role called '$RoleName'. Please use the create-role skill to scaffold it. Create role.json and ROLE.md in the appropriate role directory. Ensure the role is registered in registry.json. Keep the role definition simple and functional."
    $McpConfig = Join-Path $AgentsDir "mcp/config.json"
    & $agentBin -a manager -n $ManagerPrompt --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config $McpConfig
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Manager agent exited with code $LASTEXITCODE while creating role '$RoleName'."
        exit $LASTEXITCODE
    }
    Write-Host "  Done."
    exit 0
}

# ── Phase 2: Write dummy ROLE.md with proper frontmatter format ──
$roleMdPath = Join-Path $roleDir "ROLE.md"

$needsRoleMd = $false
if (-not (Test-Path $roleMdPath)) {
    $needsRoleMd = $true
} else {
    $existingMd = Get-Content $roleMdPath -Raw
    if ($existingMd -notmatch '(?s)^---') { $needsRoleMd = $true }
}

if ($needsRoleMd) {
    Write-Host "  [2/4] Writing ROLE.md stub..."

    $roleDescription = if ($Description) { $Description } else { "You are a $safeName specialist agent working within a war-room team." }

    $skillRefs = ""
    if ($Skills.Count -gt 0) {
        $skillRefs = "`n## Equipped Skills`n`n"
        foreach ($skill in $Skills) {
            $skillRefs += "- $skill`n"
        }
    }

    $dummyRoleMd = @"
---
name: $safeName
description: $roleDescription
tags: [$safeName]
trust_level: dynamic
---

# $safeName

$roleDescription

## Your Responsibilities

When assigned an Epic (EPIC-XXX), you own the full planning and implementation cycle.
When assigned a Task (TASK-XXX), implement it directly.

### Phase 0 — Context (ALWAYS DO THIS FIRST)
Before writing any code, load context from both layers:
```
search_memory(query="<terms from your brief>")
memory_tree()
knowledge_query("project-docs", "What are the conventions for <area>?", mode="summarized")
```

### Phase 1 — Planning
1. Read the brief and understand the goal
2. Break into concrete, independently testable sub-tasks
3. Create TASKS.md with your plan (if Epic)
4. Save TASKS.md before proceeding

### Phase 2 — Implementation
1. Work through each sub-task sequentially
2. After completing each, check it off in TASKS.md
3. Write tests as you go

### Phase 3 — Reporting
1. Ensure all checkboxes in TASKS.md are checked
2. MANDATORY: Save to memory:
   ```
   save_memory(
     content="<key code, interfaces, decisions>",
     name="<descriptive name>",
     path="code/<module>",
     tags=["<relevant>", "<tags>"]
   )
   ```
3. Post a done message with:
   - Summary of changes made
   - Files modified/created
   - How to test
$skillRefs
## When Fixing QA Feedback

1. Read the fix message carefully
2. Address every point raised by QA
3. Do not introduce new issues while fixing
4. Post a new done message explaining what was fixed

## Communication

Use the channel MCP tools to:
- Report progress: `report_progress(percent, message)`
- Post completion: `post_message(type="done", body="...")`

## Quality Standards

- Code must compile/parse without errors
- Include inline comments for non-obvious logic
- Follow existing project conventions and patterns
- Handle edge cases mentioned in the task description
- MANDATORY: Save key code and decisions to memory after every significant action
"@

    $dummyRoleMd | Out-File -FilePath $roleMdPath -Encoding utf8 -Force
    Write-Host "  ROLE.md stub written to $roleMdPath"
} else {
    Write-Host "  [2/4] ROLE.md already exists with proper format."
}

# ── Phase 3: Invoke manager agent to refine ROLE.md ──
Write-Host "  [3/4] Invoking manager agent to refine ROLE.md..."

$invokeAgent = Join-Path $AgentsDir "roles" "_base" "Invoke-Agent.ps1"

if (Test-Path $invokeAgent) {
    # Create temp room for the LLM call (same pattern as Build-PlanningDAG.ps1)
    $projectRoot = (Resolve-Path (Join-Path $AgentsDir "..") -ErrorAction SilentlyContinue).Path
    $warRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   elseif ($projectRoot) { Join-Path $projectRoot ".war-rooms" }
                   else { Join-Path $env:HOME ".war-rooms" }
    $tempRoom = Join-Path $warRoomsDir "room-role-creation"
    if (-not (Test-Path $tempRoom)) {
        New-Item -ItemType Directory -Path $tempRoom -Force | Out-Null
    }

    # Collect available skills for the prompt
    $skillsDir = Join-Path $AgentsDir "skills"
    $availableSkills = @()
    if (Test-Path $skillsDir) {
        $availableSkills = Get-ChildItem -Path $skillsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne '__pycache__' } |
            ForEach-Object { $_.Name }
    }
    $skillsListStr = if ($availableSkills.Count -gt 0) { $availableSkills -join ', ' } else { "none" }

    # Collect reference ROLE.md snippets
    $refRolesDir = Join-Path $AgentsDir "roles"
    $refExamples = @()
    foreach ($refRole in @("engineer", "qa")) {
        $refPath = Join-Path $refRolesDir $refRole "ROLE.md"
        if (Test-Path $refPath) {
            $refContent = Get-Content $refPath -Raw
            if ($refContent.Length -gt 2000) {
                $refContent = $refContent.Substring(0, 2000) + "`n... [TRUNCATED]"
            }
            $refExamples += "- $refRole"
        }
    }

    $roleDescription = if ($Description) { $Description } else { "You are a $safeName specialist agent working within a war-room team." }

    $refinePrompt = @"
You are creating a new agent role called '$safeName'.

Description: $roleDescription

I have attached a stub ROLE.md file for this role. Your task is to rewrite it into a proper, detailed ROLE.md that follows the same format and structure as the existing core roles (engineer, qa, manager, reporter).

The ROLE.md MUST include:
1. YAML frontmatter (--- delimiters) with: name, description, tags, trust_level
2. A detailed # heading with the role name and a specific description of what this role does
3. Phase-based workflow:
   - Phase 0 — Context: load memory/knowledge via MCP tools (search_memory, memory_tree, knowledge_query)
   - Phase 1+ — Role-specific phases that make sense for a $safeName
4. Communication section using channel MCP tools (post_message, read_messages, report_progress)
5. Quality Standards section
6. MANDATORY save_memory() calls with concrete examples after every significant action
7. When Fixing QA Feedback section

Available skills in this system: $skillsListStr
$($Skills.Count -gt 0 ? "This role uses these skills: $($Skills -join ', ')" : "")

IMPORTANT: Write the improved ROLE.md to the same file path: $roleMdPath
The file is attached — read it, then overwrite it with the improved version.
"@

    try {
        $result = & $invokeAgent -RoomDir $tempRoom -RoleName "manager" `
            -Prompt $refinePrompt `
            -Files @($roleMdPath) `
            -Model "google-vertex/gemini-3.1-pro-preview" `
            -TimeoutSeconds 120

        if ($result.ExitCode -eq 0) {
            Write-Host "  Manager agent completed — ROLE.md refined"
        } else {
            Write-Warning "  Manager agent exited with code $($result.ExitCode) — keeping stub ROLE.md"
        }
    } catch {
        Write-Warning "  Manager agent error: $($_.Exception.Message) — keeping stub ROLE.md"
    } finally {
        if (Test-Path $tempRoom) {
            Remove-Item $tempRoom -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Warning "  Invoke-Agent.ps1 not found — skipping ROLE.md refinement (stub will be used)"
}

# ── Phase 4: Register in registry.json if not already present ──
Write-Host "  [4/4] Registering in registry.json..."
$registryPath = Join-Path $AgentsDir "roles" "registry.json"
if (Test-Path $registryPath) {
    $registry = Get-Content $registryPath -Raw | ConvertFrom-Json
    $existing = $registry.roles | Where-Object { $_.name -eq $safeName }
    if (-not $existing) {
        $roleRelDir = if ($roleDir -match 'contributes[\\/]roles') {
            "contributes/roles/$safeName"
        } else {
            "roles/$safeName"
        }
        $pascalName = ($safeName -split '-' | ForEach-Object { $_.Substring(0,1).ToUpper() + $_.Substring(1) }) -join ''
        $newEntry = [ordered]@{
            name                = $safeName
            description         = if ($Description) { $Description } else { "$safeName specialist agent" }
            runner              = "$roleRelDir/Start-$pascalName.ps1"
            definition          = "$roleRelDir/role.json"
            prompt              = "$roleRelDir/ROLE.md"
            default_assignment  = $false
            instance_support    = $true
            supported_task_types = @("task", "epic")
            capabilities        = if ($Capabilities.Count -gt 0) { @($Capabilities) } else { @("code-generation", "file-editing", "shell-execution") }
            quality_gates       = @()
            default_model       = $Model
        }
        $registry.roles += $newEntry
        $registry | ConvertTo-Json -Depth 10 | Out-File -FilePath $registryPath -Encoding utf8 -Force
        Write-Host "  Registered '$safeName' in registry.json"
    } else {
        Write-Host "  '$safeName' already in registry.json"
    }
}

Write-Host "  Done."
