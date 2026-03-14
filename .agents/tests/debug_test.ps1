
$testPaths = @(
    "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/",
    "/Users/paulaan/PycharmProjects/agent-os/.agents/tests/"
)
Invoke-Pester -Path $testPaths -Output Detailed



