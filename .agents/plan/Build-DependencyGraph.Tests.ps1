$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "Build-DependencyGraph.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Script $scriptPath not found"
}

# Remove dot sourcing
# . $scriptPath

function Invoke-Builder {
    param($Nodes)
    & $scriptPath -Nodes $Nodes
}

$testCount = 0
$passCount = 0
$failCount = 0

function Test-Assertion {
    param(
        [string]$Name,
        [scriptblock]$TestBlock
    )
    $script:testCount++
    try {
        $result = & $TestBlock
        if ($result) {
            Write-Host "[PASS] $Name" -ForegroundColor Green
            $script:passCount++
        } else {
            Write-Host "[FAIL] $Name - Expected true, got false" -ForegroundColor Red
            $script:failCount++
        }
    } catch {
        Write-Host "[FAIL] $Name - Exception thrown: $_" -ForegroundColor Red
        $script:failCount++
    }
}

function Test-Throws {
    param(
        [string]$Name,
        [scriptblock]$TestBlock,
        [string]$ExpectedMessagePattern
    )
    $script:testCount++
    $threw = $false
    try {
        & $TestBlock | Out-Null
    } catch {
        $threw = $true
        if ($_.Exception.Message -match $ExpectedMessagePattern) {
            Write-Host "[PASS] $Name" -ForegroundColor Green
            $script:passCount++
        } else {
            Write-Host "[FAIL] $Name - Exception message didn't match. Expected '$ExpectedMessagePattern', got '$($_.Exception.Message)'" -ForegroundColor Red
            $script:failCount++
        }
    }
    if (-not $threw) {
        Write-Host "[FAIL] $Name - Expected an exception but none was thrown." -ForegroundColor Red
        $script:failCount++
    }
}

Write-Host "Running tests for Build-DependencyGraph.ps1..." -ForegroundColor Cyan

# Test 1: Empty Input
Test-Assertion "Handles empty input" {
    $result = Invoke-Builder -Nodes @()
    $result.Count -eq 0
}

# Test 2: Validation - Missing ID
Test-Throws "Validates missing ID" {
    $nodes = @( @{ DependsOn = @('A') } )
    Invoke-Builder -Nodes $nodes
} "All nodes must have an 'Id' property"

# Test 3: Validation - Duplicate ID
Test-Throws "Validates duplicate ID" {
    $nodes = @( 
        @{ Id = 'A'; DependsOn = @() },
        @{ Id = 'A'; DependsOn = @() }
    )
    Invoke-Builder -Nodes $nodes
} "Duplicate node Id detected: 'A'"

# Test 4: Validation - Missing Dependency
Test-Throws "Validates missing dependency" {
    $nodes = @( 
        @{ Id = 'A'; DependsOn = @('B') }
    )
    Invoke-Builder -Nodes $nodes
} "Node 'A' depends on 'B', but 'B' was not found"

# Test 5: Linear sorting
Test-Assertion "Sorts linear dependencies correctly" {
    $nodes = @(
        @{ Id = 'TaskC'; DependsOn = @('TaskB') },
        @{ Id = 'TaskA'; DependsOn = @() },
        @{ Id = 'TaskB'; DependsOn = @('TaskA') }
    )
    $result = Invoke-Builder -Nodes $nodes
    ($result[0].Id -eq 'TaskA') -and ($result[1].Id -eq 'TaskB') -and ($result[2].Id -eq 'TaskC')
}

# Test 6: Multiple independent DAGs
Test-Assertion "Sorts multiple independent components" {
    $nodes = @(
        @{ Id = '1'; DependsOn = @() },
        @{ Id = '3'; DependsOn = @('2') },
        @{ Id = '2'; DependsOn = @('1') },
        @{ Id = 'B'; DependsOn = @('A') },
        @{ Id = 'A'; DependsOn = @() }
    )
    $result = Invoke-Builder -Nodes $nodes
    $result.Count -eq 5 -and `
    ([array]::IndexOf($result.Id, '1') -lt [array]::IndexOf($result.Id, '2')) -and `
    ([array]::IndexOf($result.Id, '2') -lt [array]::IndexOf($result.Id, '3')) -and `
    ([array]::IndexOf($result.Id, 'A') -lt [array]::IndexOf($result.Id, 'B'))
}

# Test 7: Cycle detection - simple
Test-Throws "Detects simple cycle" {
    $nodes = @(
        @{ Id = 'A'; DependsOn = @('B') },
        @{ Id = 'B'; DependsOn = @('A') }
    )
    Invoke-Builder -Nodes $nodes
} "Circular dependency detected involving nodes: A, B"

# Test 8: Cycle detection - larger
Test-Throws "Detects larger cycle" {
    $nodes = @(
        @{ Id = 'A'; DependsOn = @('B') },
        @{ Id = 'B'; DependsOn = @('C') },
        @{ Id = 'C'; DependsOn = @('D') },
        @{ Id = 'D'; DependsOn = @('A') },
        @{ Id = 'E'; DependsOn = @() }
    )
    Invoke-Builder -Nodes $nodes
} "Circular dependency detected involving nodes: A, B, C, D"

Write-Host "---------------------------------"
Write-Host "Tests run: $testCount"
Write-Host "Passed: $passCount" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "Failed: $failCount" -ForegroundColor Red
    exit 1
} else {
    Write-Host "All tests passed!" -ForegroundColor Green
    exit 0
}