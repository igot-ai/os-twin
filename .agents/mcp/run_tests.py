import subprocess
import sys

def run_pytest(test_file):
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", test_file], capture_output=True, text=True)
        return result.stdout + "\n" + result.stderr
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    print(run_pytest("/mnt/e/OS Twin/os-twin/.agents/mcp/test_knowledge.py"))
