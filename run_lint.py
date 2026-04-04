import subprocess
import sys

def run_lint():
    for f in [
        "/mnt/e/OS Twin/os-twin/dashboard/models.py",
        "/mnt/e/OS Twin/os-twin/dashboard/api.py",
        "/mnt/e/OS Twin/os-twin/dashboard/routes/home.py",
        "/mnt/e/OS Twin/os-twin/dashboard/tests/test_home_api.py"
    ]:
        print(f"Linting {f}")
        try:
            with open(f) as file:
                compile(file.read(), f, "exec")
        except SyntaxError as e:
            print(f"SyntaxError in {f}: {e}")

if __name__ == "__main__":
    run_lint()
