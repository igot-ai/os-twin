import subprocess

res = subprocess.run(["pwsh", "-File", "/Users/paulaan/PycharmProjects/agent-os/.agents/debug_test.ps1"], capture_output=True, text=True)
with open("/Users/paulaan/PycharmProjects/agent-os/debug_test_output.txt", "w") as f:
    f.write(res.stdout)
    f.write(res.stderr)
