import os
import sys
from pathlib import Path
import pytest

# Add project root to PYTHONPATH for imports like `from dashboard.api import app`
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

@pytest.fixture(autouse=True)
def isolated_test_env(tmp_path):
    """
    Provide an isolated environment for all tests.
    Sets necessary environment variables so tests do not
    pollute the global state or real zvec datasets.
    """
    # Isolate zvec to prevent 'zvec init failed' due to concurrency
    zvec_dir = tmp_path / ".zvec"
    os.environ["OSTWIN_ZVEC_DIR"] = str(zvec_dir)
    os.environ["OSTWIN_PROJECT_DIR"] = str(tmp_path / "project")
    
    # Fake API Key for tests that use authentication
    os.environ["OSTWIN_AUTH_KEY"] = "test-key"
    os.environ["OSTWIN_API_KEY"] = "test-key"
    
    yield
