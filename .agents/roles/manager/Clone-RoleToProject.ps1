<#
.SYNOPSIS
    Clone-RoleToProject.ps1 — Clone a role to project-local for override.
.DESCRIPTION
    Clones an installed role into $ProjectDir/.ostwin/roles/{role}/ for local modification.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RoleName,

    [string]$ProjectDir = $PWD,

    [string[]]$SubcommandFilter
)

Import-Module (Join-Path $PSScriptRoot "SharedUtils.psm1") -Force

# Resolve source role dir (using shared resolution)
# We want to find the role to clone FROM, which should be in AGENT_DIR or HOME.
# But we must NOT clone the project-local one itself if it's already there (unless it's the only source).
# Actually, the requirement says "clones any installed role".

$sourceDir = Resolve-RoleDir -RoleName $RoleName -ProjectDir $ProjectDir

if ($null -eq $sourceDir) {
    Write-Error "Source role '$RoleName' not found."
    exit 1
}

$targetDir = Join-Path $ProjectDir ".ostwin" "roles" $RoleName

# If source is same as target, we are trying to clone a role into itself.
if ((Get-Item $sourceDir).FullName -eq (Get-Item $targetDir -ErrorAction SilentlyContinue).FullName) {
    # We should look for the NEXT source in priority if we want to "re-clone" or "re-base".
    # For now, let's assume we want to clone from AGENT_DIR or HOME if project-local already exists.
    
    # Simple hack for this script: temporarily ignore project-local to find the "installed" source.
    # But Resolve-RoleDir doesn't support "exclude-path".
    # Let's just manually search the other two.
    
    $AgentDir = $null
    $SearchDir = $PSScriptRoot
    while ($SearchDir -ne (Split-Path $SearchDir -Qualifier)) {
        if (Test-Path (Join-Path $SearchDir "config.json") -PathType Leaf) { $AgentDir = $SearchDir; break }
        $SearchDir = Split-Path $SearchDir -Parent
    }

    $sourceDir = $null
    if ($null -ne $AgentDir) {
        $path = Join-Path $AgentDir "roles" $RoleName
        if (Test-Path $path -PathType Container) { $sourceDir = (Get-Item $path).FullName }
    }
    
    if ($null -eq $sourceDir) {
        $path = Join-Path $HOME ".ostwin" "roles" $RoleName
        if (Test-Path $path -PathType Container) { $sourceDir = (Get-Item $path).FullName }
    }
}

if ($null -eq $sourceDir) {
    Write-Error "No installed version of role '$RoleName' found to clone."
    exit 1
}

if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$filesToCopy = @()
if ($SubcommandFilter -and $SubcommandFilter.Count -gt 0) {
    Write-Host "Applying subcommand filter: $($SubcommandFilter -join ', ')"
    
    $manifestPath = Join-Path $sourceDir "subcommands.json"
    if (Test-Path $manifestPath) {
        $manifest = Get-Content $manifestPath | ConvertFrom-Json
        $filesToCopy += "subcommands.json"
        if (Test-Path (Join-Path $sourceDir "role.json")) { $filesToCopy += "role.json" }
        
        foreach ($subName in $SubcommandFilter) {
            $sub = $manifest.subcommands | Where-Object { $_.name -eq $subName }
            if ($sub) {
                $entrypoint = $sub.entrypoint
                # entrypoint might be "cli.py::main", take the file part
                $fileName = $entrypoint.Split('::')[0]
                $filesToCopy += $fileName
            } else {
                Write-Warning "Subcommand '$subName' not found in manifest."
            }
        }
        $filesToCopy = $filesToCopy | Select-Object -Unique
        
        foreach ($f in $filesToCopy) {
            $srcFile = Join-Path $sourceDir $f
            if (Test-Path $srcFile) {
                Copy-Item -Path $srcFile -Destination $targetDir -Force
            }
        }
    } else {
        Write-Warning "No subcommands.json found in $sourceDir. Filter ignored, copying all."
        Copy-Item -Path (Join-Path $sourceDir "*") -Destination $targetDir -Recurse -Force
    }
} else {
    Write-Host "Cloning $sourceDir to $targetDir"
    Copy-Item -Path (Join-Path $sourceDir "*") -Destination $targetDir -Recurse -Force
}

# Git SHA or file hash
$sourceSha = "unknown"
if (Test-Path (Join-Path $sourceDir ".git")) {
    try {
        $sourceSha = (git -C $sourceDir rev-parse HEAD 2>$null)
    } catch {}
}
if ($sourceSha -eq "unknown") {
    # Fallback to a hash of the directory or manifest if git fails
    $sourceSha = "hash-$((Get-FileHash (Join-Path $sourceDir ( (ls $sourceDir | select -first 1).Name ))).Hash)"
}

# Write clone manifest
$cloneManifest = @{
    source_path = $sourceDir
    source_sha  = $sourceSha
    cloned_at   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    filter      = if ($SubcommandFilter) { $SubcommandFilter } else { $null }
}

$cloneManifest | ConvertTo-Json | Out-File (Join-Path $targetDir ".clone-manifest.json") -Encoding utf8

Write-Host "✓ Role '$RoleName' cloned to $targetDir"
