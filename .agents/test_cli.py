import subprocess
import json

try:
    result = subprocess.run(
        ["/mnt/e/OS Twin/os-twin/.agents/bin/memory", "knowledge", "search", "auth", "--max", "5"],
        capture_output=True,
        text=True,
        check=True
    )
    print("STDOUT:", result.stdout)
except subprocess.CalledProcessError as e:
    print("ERROR:")
    print("STDOUT:", e.stdout)
    print("STDERR:", e.stderr)
