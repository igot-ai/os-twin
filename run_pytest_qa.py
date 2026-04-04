import os
import sys
from pathlib import Path

project_root = Path("/mnt/e/OS Twin/os-twin")
sys.path.insert(0, str(project_root))

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([str(project_root / "dashboard/tests/test_conversations.py")]))
