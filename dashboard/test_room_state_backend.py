import subprocess
import json
import os

results = {}

# Run backend tests
for test_file in ["tests/test_skills_logic_v3.py", "tests/test_skills_logic_v2.py", "tests/test_skills_search_limit.py"]:
    res = subprocess.run(["pytest", test_file], capture_output=True, text=True)
    results[test_file] = {
        "stdout": res.stdout,
        "stderr": res.stderr,
        "code": res.returncode
    }

# Search for frontend tests related to Skill Library
# Based on my previous grep, I'll look for vitest tests.
# The user asked to check if there are any frontend tests for the Skill Library and run them if they exist.
# I'll try to find any test file that imports SkillLibrary or SkillsPanel.

frontend_tests = []
try:
    # Use grep to find test files containing "Skill" or "SkillLibrary" or "SkillsPanel"
    # Wait, I'll just check specific locations I found earlier.
    # nextjs/src/components/panels/SkillLibrary.tsx
    # nextjs/src/components/panels/SkillsPanel.tsx
    # nextjs/src/components/shared/SkillCard.tsx
    
    # I'll check all .test.tsx files in nextjs/src
    for root, dirs, files in os.walk("/Users/paulaan/PycharmProjects/agent-os/dashboard/nextjs/src"):
        for file in files:
            if file.endswith(".test.tsx") or file.endswith(".test.ts"):
                full_path = os.path.join(root, file)
                with open(full_path, "r") as f:
                    content = f.read()
                    if "Skill" in content:
                        frontend_tests.append(full_path)

    if frontend_tests:
        # Run vitest for those specific files
        # We need to run it from the nextjs directory
        os.chdir("/Users/paulaan/PycharmProjects/agent-os/dashboard/nextjs")
        res = subprocess.run(["npm", "test", "--", *frontend_tests], capture_output=True, text=True)
        results["frontend"] = {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "code": res.returncode,
            "tests": frontend_tests
        }
    else:
        results["frontend"] = {"message": "No frontend tests found for Skill Library.", "tests": []}
except Exception as e:
    results["frontend"] = {"error": str(e)}

print(json.dumps(results))
