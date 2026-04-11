# Pester configuration for agent-os test suite
# Usage: Invoke-Pester -Configuration (& ./.pester.ps1)

$config = New-PesterConfiguration
$config.Run.Path = './tests'
$config.Run.PassThru = $true
$config.Output.Verbosity = 'Detailed'
$config.TestResult.Enabled = $true
$config.TestResult.OutputPath = './tests/results.xml'
$config.TestResult.OutputFormat = 'NUnitXml'
$config.CodeCoverage.Enabled = $false  # Enable when ready
$config.CodeCoverage.Path = @(
    '.agents/lib/*.psm1',
    '.agents/war-rooms/*.ps1',
    '.agents/plan/*.ps1'
)
$config.Filter.ExcludeTag = @('Integration', 'Slow')

return $config
