<#
.SYNOPSIS
    Agent OS — Memory CLI (PowerShell port of bin/memory)

.DESCRIPTION
    Shell wrapper so agents can use shared memory via their shell tool
    even when MCP is disabled (no_mcp: true).

.PARAMETER Command
    Memory command: publish, query, search, context, list, help.

.PARAMETER Arguments
    Remaining arguments for the subcommand.

.EXAMPLE
    .\memory.ps1 publish artifact "Created users table" --tags db,users --room room-001 --ref EPIC-001
    .\memory.ps1 query --tags auth,db
    .\memory.ps1 search "authentication flow"
    .\memory.ps1 context room-002 --keywords auth,users
    .\memory.ps1 list --kind decision
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path $PSCommandPath -Parent
$AgentsBaseDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$McpDir = Join-Path $AgentsBaseDir "mcp"
$MemoryCli = Join-Path $McpDir "memory-cli.py"

# ─── Resolve Python ──────────────────────────────────────────────────────────

$PythonCmd = $null
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }

foreach ($candidate in @(
    (Join-Path $AgentsBaseDir ".venv" "Scripts" "python.exe"),
    (Join-Path $AgentsBaseDir ".venv" "bin" "python"),
    (Join-Path $HomeDir ".ostwin" ".venv" "Scripts" "python.exe"),
    (Join-Path $HomeDir ".ostwin" ".venv" "bin" "python")
)) {
    if (Test-Path $candidate) { $PythonCmd = $candidate; break }
}
if (-not $PythonCmd) {
    if (Get-Command python3 -ErrorAction SilentlyContinue) { $PythonCmd = "python3" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $PythonCmd = "python" }
    else {
        Write-Error "[memory] Python not found."
        exit 1
    }
}

# ─── Resolve AGENT_OS_ROOT ───────────────────────────────────────────────────

if (-not $env:AGENT_OS_ROOT) {
    if ($env:AGENT_OS_ROOM_DIR) {
        # AGENT_OS_ROOM_DIR is <project>/.war-rooms/room-XXX → project root is ../..
        $env:AGENT_OS_ROOT = (Resolve-Path (Join-Path $env:AGENT_OS_ROOM_DIR ".." "..")).Path
    }
    else {
        # Script is at <project>/.agents/bin/memory.ps1 → project root is ../..
        $env:AGENT_OS_ROOT = (Resolve-Path (Join-Path $AgentsBaseDir "..")).Path
    }
}

# ─── Handle --global and --root flags ────────────────────────────────────────

$filteredArgs = @()
$i = 0
while ($i -lt ($Arguments ?? @()).Count) {
    $arg = $Arguments[$i]
    if ($arg -eq "--global") {
        $env:AGENT_OS_ROOT = (Resolve-Path (Join-Path $AgentsBaseDir "..")).Path
    }
    elseif ($arg -eq "--root") {
        $i++
        if ($i -lt $Arguments.Count) {
            $env:AGENT_OS_ROOT = (Resolve-Path $Arguments[$i] -ErrorAction Stop).Path
        }
        else {
            Write-Error "[ERROR] --root requires a directory path"
            exit 1
        }
    }
    else {
        $filteredArgs += $arg
    }
    $i++
}

# ─── Build JSON from shell args ─────────────────────────────────────────────

function Build-Json {
    param([string[]]$Args)

    $data = @{}
    $i = 0
    while ($i -lt $Args.Count) {
        $a = $Args[$i]
        switch ($a) {
            "--tags"         { $i++; $data["tags"] = ($Args[$i] -split ',') | ForEach-Object { $_.Trim() }; $i++ }
            "--kind"         { $i++; $data["kind"] = $Args[$i]; $i++ }
            "--room"         { $i++; $data["room_id"] = $Args[$i]; $i++ }
            "--ref"          { $i++; $data["ref"] = $Args[$i]; $i++ }
            "--role"         { $i++; $data["author_role"] = $Args[$i]; $i++ }
            "--detail"       { $i++; $data["detail"] = $Args[$i]; $i++ }
            "--supersedes"   { $i++; $data["supersedes"] = $Args[$i]; $i++ }
            "--exclude-room" { $i++; $data["exclude_room"] = $Args[$i]; $i++ }
            "--last"         { $i++; $data["last_n"] = [int]$Args[$i]; $i++ }
            "--max"          { $i++; $data["max_results"] = [int]$Args[$i]; $i++ }
            "--keywords"     { $i++; $data["brief_keywords"] = ($Args[$i] -split ',') | ForEach-Object { $_.Trim() }; $i++ }
            "--max-entries"  { $i++; $data["max_entries"] = [int]$Args[$i]; $i++ }
            default {
                # Positional args
                if (-not $data.ContainsKey("kind"))    { $data["kind"] = $a }
                elseif (-not $data.ContainsKey("summary")) { $data["summary"] = $a }
                elseif (-not $data.ContainsKey("text"))    { $data["text"] = $a }
                elseif (-not $data.ContainsKey("room_id")) { $data["room_id"] = $a }
                $i++
            }
        }
    }
    return ($data | ConvertTo-Json -Compress -Depth 5)
}

# ─── Command dispatch ────────────────────────────────────────────────────────

switch ($Command) {
    "publish" {
        $kind = if ($filteredArgs.Count -gt 0) { $filteredArgs[0] } else { "" }
        $summary = if ($filteredArgs.Count -gt 1) { $filteredArgs[1] } else { "" }
        $restArgs = if ($filteredArgs.Count -gt 2) { $filteredArgs[2..($filteredArgs.Count - 1)] } else { @() }

        # Auto-detect room and role from env vars
        $extraArgs = @()
        $hasRoom = $restArgs -contains "--room"
        $hasRole = $restArgs -contains "--role"

        if ($env:AGENT_OS_ROOM_DIR -and -not $hasRoom) {
            $roomId = Split-Path $env:AGENT_OS_ROOM_DIR -Leaf
            $extraArgs += @("--room", $roomId)
        }
        if ($env:AGENT_OS_ROLE -and -not $hasRole) {
            $extraArgs += @("--role", $env:AGENT_OS_ROLE)
        }

        $allArgs = @($kind, $summary) + $extraArgs + $restArgs
        $json = Build-Json -Args $allArgs
        & $PythonCmd $MemoryCli publish $json
        exit $LASTEXITCODE
    }

    "query" {
        $json = Build-Json -Args $filteredArgs
        & $PythonCmd $MemoryCli query $json
        exit $LASTEXITCODE
    }

    "search" {
        $text = if ($filteredArgs.Count -gt 0) { $filteredArgs[0] } else { "" }
        $restArgs = if ($filteredArgs.Count -gt 1) { $filteredArgs[1..($filteredArgs.Count - 1)] } else { @() }
        $allArgs = @($text) + $restArgs
        $json = Build-Json -Args $allArgs

        # Rename 'kind' key to 'text' if it was set as positional
        $jsonObj = $json | ConvertFrom-Json
        if ($jsonObj.PSObject.Properties['kind'] -and -not $jsonObj.PSObject.Properties['text']) {
            $val = $jsonObj.kind
            $jsonObj.PSObject.Properties.Remove('kind')
            $jsonObj | Add-Member -NotePropertyName 'text' -NotePropertyValue $val
        }
        $json = $jsonObj | ConvertTo-Json -Compress -Depth 5

        & $PythonCmd $MemoryCli search $json
        exit $LASTEXITCODE
    }

    "context" {
        $room = if ($filteredArgs.Count -gt 0) { $filteredArgs[0] } else { "" }
        $restArgs = if ($filteredArgs.Count -gt 1) { $filteredArgs[1..($filteredArgs.Count - 1)] } else { @() }
        $json = Build-Json -Args $restArgs

        $jsonObj = $json | ConvertFrom-Json
        $jsonObj | Add-Member -NotePropertyName 'room_id' -NotePropertyValue $room -Force
        $json = $jsonObj | ConvertTo-Json -Compress -Depth 5

        & $PythonCmd $MemoryCli get_context $json
        exit $LASTEXITCODE
    }

    "list" {
        $json = Build-Json -Args $filteredArgs
        & $PythonCmd $MemoryCli list $json
        exit $LASTEXITCODE
    }

    { $_ -in @("help", "--help", "-h") } {
        Write-Host @"
Usage: memory.ps1 <command> [args]

Commands:
  publish <kind> <summary> [options]   Publish a memory entry
    Kinds: code, artifact, decision, interface, convention, warning
    Options:
      --global               Publish to global project ledger
      --root PATH            Specify a custom project root directory
      --tags tag1,tag2       Tags for discovery
      --room room-id         War-room ID (auto-detected from `$env:AGENT_OS_ROOM_DIR)
      --ref EPIC-001         Epic/task reference
      --role engineer        Author role (auto-detected from `$env:AGENT_OS_ROLE)
      --detail "..."         Code snippets, file contents, JSON shapes
      --supersedes mem-id    ID of entry this replaces

  query [options]                      Query memory with filters
      --tags tag1,tag2       Filter by tags (OR match)
      --kind artifact        Filter by kind
      --room room-id         Filter by room
      --ref EPIC-001         Filter by reference
      --role engineer        Filter by author role
      --exclude-room room-id Exclude a room
      --last N               Last N entries only

  search <text> [options]              Full-text search
      --kind artifact        Filter by kind
      --exclude-room room-id Exclude a room
      --max N                Max results (default 10)

  context <room-id> [options]          Get cross-room context for a room
      --keywords auth,db     Filter by keywords
      --max-entries N        Max entries (default 15)

  list [options]                       List all memory entries
      --kind artifact        Filter by kind

Environment (auto-detected by agents):
  AGENT_OS_ROOM_DIR   Auto-sets --room
  AGENT_OS_ROLE       Auto-sets --role
  AGENT_OS_ROOT       Project root for memory storage
"@
    }

    default {
        Write-Error "Unknown command: $Command. Run 'memory.ps1 help' for usage."
        exit 1
    }
}
