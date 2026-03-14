import subprocess
import os

cmd = ["pwsh", "-c", "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/Expand-Plan.ps1 -PlanFile /Users/paulaan/PycharmProjects/agent-os/.agents/plans/test-repro.md -AgentCmd /Users/paulaan/.local/share/uv/tools/deepagents-cli/bin/deepagents"]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
