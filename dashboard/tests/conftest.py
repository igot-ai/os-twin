import os
import pytest
from pathlib import Path

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
