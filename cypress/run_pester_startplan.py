import subprocess
import os

print("Running manual test for plan refinement...")
cmd = [
    "pwsh", "-c",
    ". /Users/paulaan/PycharmProjects/agent-os/.agents/plan/Start-Plan.ps1 -PlanFile /Users/paulaan/PycharmProjects/agent-os/.agents/plans/test-qa.md -ProjectDir /Users/paulaan/PycharmProjects/agent-os -DryRun"
]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
exit(res.returncode)
