import subprocess
import sys
import os

os.environ['PYTHONPATH'] = '/mnt/e/OS Twin/os-twin'
res = subprocess.run(['python3', '-m', 'pytest', '/mnt/e/OS Twin/os-twin/dashboard/tests/test_conversations.py'], capture_output=True, text=True)
with open('/mnt/e/OS Twin/os-twin/final_test_results.txt', 'w') as f:
    f.write(res.stdout)
    f.write(res.stderr)
print(res.stdout)
