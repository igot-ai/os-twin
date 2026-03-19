
import re
from pathlib import Path

content = (Path(__file__).parent / "plan-20260313-211747.md").read_text()
status_match = re.search(r"> Status:\s*(.*)", content)
created_match = re.search(r"> Created:\s*(.*)", content)

print(f"Status Match: {status_match.group(1) if status_match else 'None'}")
print(f"Created Match: {created_match.group(1) if created_match else 'None'}")
