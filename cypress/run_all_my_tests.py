import subprocess
import os

test_paths = [
    "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/*.Tests.ps1",
    "/Users/paulaan/PycharmProjects/agent-os/.agents/tests/*.Tests.ps1"
]
# Join paths with comma for PowerShell
paths_str = ",".join([f"'{p}'" for p in test_paths])
cmd = ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {paths_str} -Output Detailed"]
print(f"Running: {' '.join(cmd)}")
res = subprocess.run(cmd, capture_output=True, text=True)
with open("/Users/paulaan/PycharmProjects/agent-os/all_tests_results.txt", "w") as f:
    f.write(res.stdout)
    f.write(res.stderr)
print("Done.")
