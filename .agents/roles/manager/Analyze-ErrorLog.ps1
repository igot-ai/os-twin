[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$RoomDir,

    [Parameter(Mandatory=$true)]
    [string]$RoleName,

    [switch]$UseAI
)

# --- Path resolution ---
$scriptDir = $PSScriptRoot
# Try to find agent dir by looking for .agents marker or assuming relative structure
$agentsDir = (Resolve-Path (Join-Path $scriptDir ".." "..")).Path

# --- 1. Read channel.jsonl for latest error messages ---
$channelPath = Join-Path $RoomDir "channel.jsonl"
if (-not (Test-Path $channelPath)) {
    # If not in RoomDir, check if RoomDir is relative to current dir
    if (-not [System.IO.Path]::IsPathRooted($RoomDir)) {
        $resolved = Resolve-Path (Join-Path (Get-Location) $RoomDir "channel.jsonl") -ErrorAction SilentlyContinue
        if ($resolved) { $channelPath = $resolved.Path }
    }
}

if (-not (Test-Path $channelPath)) {
    $result = @{
        classification = "unknown"
        confidence = 0.1
        evidence = "channel.jsonl not found at $channelPath"
        recommended_action = "escalate"
    }
    $result | ConvertTo-Json -Compress
    return
}

$events = Get-Content $channelPath | ForEach-Object { 
    try { ConvertFrom-Json $_ } catch { $null } 
} | Where-Object { $null -ne $_ }

# Filter events with type: error or type: failed
$errors = $events | Where-Object { $_.type -eq "error" -or $_.type -eq "failed" }

if ($errors.Count -eq 0) {
    $result = @{
        classification = "unknown"
        confidence = 0.5
        evidence = "No events with type 'error' or 'failed' found in channel.jsonl"
        recommended_action = "escalate"
    }
    $result | ConvertTo-Json -Compress
    return
}

$latestError = $errors[-1]
$errorMessage = if ($latestError.body) { $latestError.body } else { $latestError.message }
if (-not $errorMessage) {
    # Fallback to entire object string representation if no body/message
    $errorMessage = $latestError | Out-String
}

# --- 2. Load subcommands.json ---
$possiblePaths = @(
    (Join-Path $RoomDir ".." "roles" $RoleName "subcommands.json"),
    (Join-Path $agentsDir "roles" $RoleName "subcommands.json")
)

$subcommandsManifest = $null
foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        try {
            $subcommandsManifest = Get-Content $path -Raw | ConvertFrom-Json
            break
        } catch { }
    }
}

# --- 3. Classification logic ---
$classification = "unknown"
$confidence = 0.5
$evidence = ""
$subcommand = $null
$recommended_action = "escalate"

# Heuristics based on regex/keywords
if ($errorMessage -match "ModuleNotFoundError" -or $errorMessage -match "command not found" -or $errorMessage -match "pip install" -or $errorMessage -match "npm install") {
    $classification = "environment-error"
    $confidence = 0.9
    $evidence = "Found environment-related keywords: $($Matches[0])"
    $recommended_action = "fix-environment"
}
elseif ($errorMessage -match "JSONDecodeError" -or $errorMessage -match "schema validation" -or $errorMessage -match "parsing" -or $errorMessage -match "unexpected token") {
    $classification = "input-error"
    $confidence = 0.8
    $evidence = "Found input/parsing-related keywords: $($Matches[0])"
    $recommended_action = "replan"
}
elseif ($errorMessage -match "unknown subcommand" -or $errorMessage -match "not implemented") {
    $classification = "subcommand-missing"
    $confidence = 0.95
    $evidence = "Error message explicitly states unknown or not implemented: $($Matches[0])"
    $recommended_action = "clone-and-redesign"
}
else {
    # Check for subcommand-missing by looking at manifest
    if ($subcommandsManifest -and $subcommandsManifest.subcommands) {
        # Try to find a subcommand mentioned in the error that is NOT in manifest
        if ($errorMessage -match "subcommand ['""]?(\w+)['""]? not found") {
            $attemptedSub = $Matches[1]
            $found = $false
            foreach ($sub in $subcommandsManifest.subcommands) {
                if ($sub.name -eq $attemptedSub) {
                    $found = $true
                    break
                }
            }
            if (-not $found) {
                $classification = "subcommand-missing"
                $confidence = 0.9
                $evidence = "Attempted subcommand '$attemptedSub' is not in manifest"
                $subcommand = $attemptedSub
                $recommended_action = "clone-and-redesign"
            }
        }
    }
    
    # Check for subcommand-bug via entrypoints
    if ($classification -eq "unknown" -and $subcommandsManifest) {
        # Check subcommands first
        if ($subcommandsManifest.subcommands) {
            foreach ($sub in $subcommandsManifest.subcommands) {
                if ($sub.entrypoint) {
                    $filename = ($sub.entrypoint -split "::")[0]
                    if ($filename -and $errorMessage -match [regex]::Escape($filename)) {
                        $classification = "subcommand-bug"
                        $confidence = 0.85
                        $evidence = "Traceback references entrypoint file '$filename' for subcommand '$($sub.name)'"
                        $subcommand = $sub.name
                        $recommended_action = "clone-and-redesign"
                        break
                    }
                }
            }
        }
        
        # Check top-level entrypoint if still unknown
        if ($classification -eq "unknown" -and $subcommandsManifest.entrypoint) {
             $topEntrypoints = if ($subcommandsManifest.entrypoint -is [System.Collections.IEnumerable] -and $subcommandsManifest.entrypoint -isnot [string]) {
                $subcommandsManifest.entrypoint
            } else {
                @($subcommandsManifest.entrypoint)
            }
            foreach ($entry in $topEntrypoints) {
                $filename = ($entry -split "::")[0]
                if ($filename -and $errorMessage -match [regex]::Escape($filename)) {
                    $classification = "subcommand-bug"
                    $confidence = 0.85
                    $evidence = "Traceback references top-level entrypoint file: $filename"
                    $recommended_action = "clone-and-redesign"
                    break
                }
            }
        }
    }
}

# --- Optional AI classification ---
if ($UseAI -and ($confidence -lt 0.5 -or $classification -eq "unknown")) {
    $aiEndpoint = $env:OSTWIN_AI_ENDPOINT
    if ($aiEndpoint) {
        # In a real scenario, call LLM here.
        $evidence += " (AI-assisted classification requested but not implemented in this version)"
    }
}

# --- Final Output ---
$result = [Ordered]@{
    classification = $classification
    confidence = $confidence
    evidence = $evidence
}

if ($subcommand) { $result.subcommand = $subcommand }
$result.recommended_action = $recommended_action

$result | ConvertTo-Json -Compress
