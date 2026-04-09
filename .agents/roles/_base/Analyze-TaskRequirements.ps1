<#
.SYNOPSIS
    Analyzes a task description and returns recommended role, capabilities, and pipeline.
 
.PARAMETER TaskDescription
    The full task/epic description text.
.PARAMETER AgentsDir
    Path to the .agents directory.
.PARAMETER UseLLM
    If true, uses an LLM call for analysis. Otherwise uses fast keyword heuristics.
 
.OUTPUTS
    PSCustomObject: SuggestedRole, RequiredCapabilities, SuggestedPipeline, Confidence
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$TaskDescription,
 
    [string]$AgentsDir = '',
 
    [switch]$UseLLM
)
 
if (-not $AgentsDir) {
    $AgentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
}
 
$result = [PSCustomObject]@{
    SuggestedRole        = 'engineer'
    RequiredCapabilities = @()
    SuggestedPipeline    = @()
    Confidence           = 0.5
}
 
$desc = $TaskDescription.ToLower()
 
# --- Keyword-to-Capability mapping ---
$capabilityKeywords = @{
    'security' = @(
        'security', 'owasp', 'cve', 'vulnerability', 'xss', 'csrf', 'injection',
        'authentication', 'authorization', 'auth', 'jwt', 'oauth', 'encrypt', 'encryption',
        'secrets', 'penetration', 'pentest', 'firewall', 'ssl', 'tls', 'cors'
    )
    'database' = @(
        'database', 'schema', 'migration', 'sql', 'query', 'index', 'postgres', 'postgresql',
        'mysql', 'sqlite', 'mongodb', 'redis', 'orm', 'alembic', 'prisma',
        'deadlock', 'transaction', 'table', 'foreign key', 'normalization'
    )
    'infrastructure' = @(
        'docker', 'kubernetes', 'k8s', 'ci/cd', 'ci-cd', 'pipeline', 'deploy',
        'terraform', 'ansible', 'nginx', 'load balancer', 'scaling', 'monitoring',
        'grafana', 'prometheus', 'aws', 'gcp', 'azure', 'helm', 'container'
    )
    'architecture' = @(
        'architecture', 'system design', 'microservice', 'monolith', 'api design',
        'interface', 'contract', 'event-driven', 'message queue', 'grpc', 'graphql',
        'domain model', 'bounded context', 'cqrs', 'event sourcing'
    )
    'accessibility' = @(
        'accessibility', 'a11y', 'wcag', 'screen reader', 'aria', 'keyboard navigation',
        'color contrast', 'alt text', 'semantic html', 'focus management'
    )
    'frontend' = @(
        'react', 'vue', 'angular', 'svelte', 'css', 'tailwind', 'responsive',
        'component', 'ui', 'ux', 'dashboard', 'layout', 'animation', 'dom'
    )
    'backend' = @(
        'api', 'rest', 'endpoint', 'fastapi', 'express', 'django', 'flask',
        'middleware', 'route', 'controller', 'service layer', 'websocket'
    )
    'testing' = @(
        'test', 'cypress', 'jest', 'pytest', 'e2e', 'integration test', 'unit test',
        'coverage', 'tdd', 'bdd', 'playwright', 'selenium', 'mock', 'fixture'
    )
    'code-review' = @(
        'code review', 'pull request', 'pr review', 'review code', 'review pr',
        'coding style', 'code quality', 'linting', 'static analysis', 'code smell',
        'review the code', 'review this code', 'review my code', 'review our code'
    )
    'refactoring' = @(
        'refactor', 'refactoring', 'technical debt', 'tech debt', 'clean code',
        'code cleanup', 'simplify', 'extract method', 'rename', 'restructure',
        'dead code', 'duplication', 'dry principle'
    )
    'documentation' = @(
        'documentation', 'readme', 'api docs', 'docstring', 'jsdoc', 'javadoc',
        'swagger', 'openapi', 'changelog', 'wiki', 'inline comment', 'typedoc'
    )
    'bug-analysis' = @(
        'bug', 'debug', 'debugging', 'root cause', 'stack trace', 'error analysis',
        'exception', 'crash', 'regression', 'defect', 'issue', 'troubleshoot',
        'reproduce', 'bisect'
    )
    'requirements' = @(
        'requirement', 'user story', 'acceptance criteria', 'specification', 'spec',
        'use case', 'feature request', 'product requirement', 'prd', 'brd',
        'functional requirement', 'non-functional'
    )
    'code-generation' = @(
        'generate code', 'code generation', 'scaffold', 'boilerplate', 'template',
        'create module', 'stub', 'skeleton', 'auto-generate', 'codegen'
    )
    'test-planning' = @(
        'test plan', 'test strategy', 'test matrix', 'test coverage', 'playwright',
        'e2e plan', 'qa plan', 'test design', 'test case', 'test scenario'
    )
}
 
# --- Score each capability ---
$detectedCapabilities = @()
$capHits = @{}
$maxScore = 0

foreach ($cap in $capabilityKeywords.Keys) {
    $keywords = $capabilityKeywords[$cap]
    $hits = 0
    foreach ($kw in $keywords) {
        $matches = [regex]::Matches($desc, "\b$([regex]::Escape($kw))\b")
        $hits += $matches.Count
    }
    if ($hits -ge 1) {
        $detectedCapabilities += $cap
        $capHits[$cap] = $hits
        if ($hits -gt $maxScore) { $maxScore = $hits }
    }
}

$result.RequiredCapabilities = $detectedCapabilities

# --- Intent-aware primary capability selection ---
# When multiple capabilities are detected, check if the task's leading intent
# targets a specialist capability. Only boost specialist if it appears as the
# primary action (first verb phrase), not as secondary/incidental context.
$specialistIntentPatterns = @{
    'documentation'   = @('write documentation', 'create documentation', 'generate docs', 'update readme', 'document the', 'write docs', 'api docs for', 'add documentation')
    'code-review'     = @('review the code', 'review pr', 'review pull request', 'code review for', 'review this')
    'refactoring'     = @('refactor the', 'refactor this', 'clean up the code', 'reduce technical debt', 'restructure the')
    'bug-analysis'    = @('debug the', 'find the bug', 'fix the bug', 'root cause', 'troubleshoot the', 'investigate the crash')
    'requirements'    = @('write requirements', 'write a specification', 'write the specification', 'create user story', 'create a user story', 'define acceptance criteria', 'define the acceptance criteria', 'write specification', 'analyze requirements')
    'code-generation' = @('generate code for', 'scaffold a', 'create boilerplate', 'generate a module')
    'test-planning'   = @('write test plan', 'write a test plan', 'write the test plan', 'create test plan', 'create a test plan', 'create the test plan', 'design test strategy', 'design a test strategy', 'design the test strategy', 'plan the testing')
}
foreach ($cap in $detectedCapabilities) {
    if ($specialistIntentPatterns.ContainsKey($cap)) {
        $patterns = $specialistIntentPatterns[$cap]
        foreach ($pattern in $patterns) {
            if ($desc -match "^\s*$([regex]::Escape($pattern))" -or
                $desc -match "^[^.;,]{0,20}$([regex]::Escape($pattern))") {
                # The specialist capability is the leading intent — boost it
                $capHits[$cap] += 100
                break
            }
        }
    }
}

# --- Implementation intent: boost engineering capabilities when task is primarily about building ---
$implementVerbs = @(
    'implement', 'build', 'create', 'develop', 'add', 'set up', 'setup',
    'make', 'design and implement', 'construct', 'deploy'
)
$isImplementIntent = $false
foreach ($verb in $implementVerbs) {
    if ($desc -match "^\s*$([regex]::Escape($verb))\b") {
        $isImplementIntent = $true
        break
    }
}
if ($isImplementIntent) {
    # Boost whichever engineering capability was detected
    $engineeringCaps = @('backend', 'frontend', 'infrastructure', 'database')
    $boostedEngineering = $false
    foreach ($eCap in $engineeringCaps) {
        if ($eCap -in $detectedCapabilities) {
            $capHits[$eCap] += 100
            $boostedEngineering = $true
        }
    }
    # If no engineering capability was detected but we have implementation intent,
    # infer from context keywords that didn't match any capability
    if (-not $boostedEngineering) {
        $backendClues = @('login', 'oauth', 'auth', 'flow', 'service', 'server', 'handler', 'module', 'feature', 'functionality')
        $frontendClues = @('page', 'screen', 'form', 'button', 'modal', 'dialog', 'menu', 'navbar', 'sidebar')
        $hasBackendClue = $false
        $hasFrontendClue = $false
        foreach ($clue in $backendClues) {
            if ($desc -match "\b$([regex]::Escape($clue))\b") { $hasBackendClue = $true; break }
        }
        foreach ($clue in $frontendClues) {
            if ($desc -match "\b$([regex]::Escape($clue))\b") { $hasFrontendClue = $true; break }
        }
        if ($hasFrontendClue) {
            if ('frontend' -notin $detectedCapabilities) {
                $detectedCapabilities += 'frontend'
                $capHits['frontend'] = 0
            }
            $capHits['frontend'] += 100
        } elseif ($hasBackendClue) {
            if ('backend' -notin $detectedCapabilities) {
                $detectedCapabilities += 'backend'
                $capHits['backend'] = 0
            }
            $capHits['backend'] += 100
        }
        # Update RequiredCapabilities since we may have added new ones
        $result.RequiredCapabilities = $detectedCapabilities
    }
}

# --- Determine confidence ---
if ($detectedCapabilities.Count -gt 0) {
    $result.Confidence = [Math]::Min(0.9, 0.5 + ($detectedCapabilities.Count * 0.1))
}

# --- Suggest primary role based on dominant capability ---
$roleMapping = @{
    'security'        = 'security-scanner'
    'database'        = 'database-architect'
    'infrastructure'  = 'devops-agent'
    'architecture'    = 'architecture-advisor'
    'accessibility'   = 'accessibility-specialist'
    'frontend'        = 'engineer:fe'
    'backend'         = 'engineer:be'
    'testing'         = 'test-engineer'
    'code-review'     = 'code-reviewer'
    'refactoring'     = 'refactoring-agent'
    'documentation'   = 'documentation-agent'
    'bug-analysis'    = 'bug-hunter'
    'requirements'    = 'requirement-analyst'
    'code-generation' = 'code-generator'
    'test-planning'   = 'qa-test-planner'
}

if ($detectedCapabilities.Count -gt 0) {
    # Pick the role for the most-matched capability
    $primaryCap = $detectedCapabilities | Sort-Object { $capHits[$_] } -Descending | Select-Object -First 1
    if ($roleMapping.ContainsKey($primaryCap)) {
        $result.SuggestedRole = $roleMapping[$primaryCap]
    }
}
 
# --- Suggest pipeline ---
$pipelineStages = @($result.SuggestedRole)
foreach ($cap in $detectedCapabilities) {
    if ($cap -in @('security', 'database', 'architecture', 'infrastructure', 'accessibility', 'code-review', 'documentation', 'requirements', 'test-planning', 'refactoring', 'bug-analysis', 'code-generation')) {
        $reviewRole = $roleMapping[$cap]
        if ($reviewRole -ne $result.SuggestedRole) {
            $pipelineStages += $reviewRole
        }
    }
}
# --- MANDATORY: Always include testing and test-planning in pipeline ---
if ('testing' -notin $result.RequiredCapabilities) {
    $result.RequiredCapabilities += 'testing'
}
if ('test-planning' -notin $result.RequiredCapabilities) {
    $result.RequiredCapabilities += 'test-planning'
}
if ('test-engineer' -notin $pipelineStages) {
    $pipelineStages += 'test-engineer'
}
if ('qa-test-planner' -notin $pipelineStages) {
    $pipelineStages += 'qa-test-planner'
}
$result.SuggestedPipeline = $pipelineStages
 
Write-Output $result