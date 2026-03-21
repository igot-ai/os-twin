"""Tests for CLI role-aware skill isolation.

These tests validate:
1. The Settings.get_project_agent_skills_dir monkey-patch correctly
   returns AGENT_OS_SKILLS_DIR when set, and falls back otherwise.
2. Two concurrent processes with different AGENT_OS_SKILLS_DIR values
   get isolated skill directories.
3. The cloned cli.py (wrapped by .agents/bin/agent) stays in sync with deepagents_cli version.
4. chat.py correctly inherits the monkey-patch from cli.py.

Run: python -m pytest bin/tests/test_cli_role_isolation.py -v
"""

import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Fixture: ensure the monkey-patch is installed (importing cli does it)
# ---------------------------------------------------------------------------

# Add bin/ to path so we can import cli
_BIN_DIR = Path(__file__).resolve().parent.parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


@pytest.fixture(autouse=True)
def _clean_env():
    """Remove AGENT_OS_* env vars before/after each test."""
    keys = ["AGENT_OS_ROLE", "AGENT_OS_SKILLS_DIR", "AGENT_OS_ROOM_DIR"]
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    yield
    for k in keys:
        if saved[k] is not None:
            os.environ[k] = saved[k]
        else:
            os.environ.pop(k, None)


# ===========================================================================
# 1. Settings monkey-patch tests (unit)
# ===========================================================================

class TestSettingsMonkeyPatch:
    """Verify the monkey-patch on Settings.get_project_agent_skills_dir."""

    def test_returns_skills_dir_when_env_set_and_dir_exists(self, tmp_path):
        """AGENT_OS_SKILLS_DIR set + exists → returns that path."""
        skills_dir = tmp_path / "engineer-skills"
        skills_dir.mkdir()

        os.environ["AGENT_OS_SKILLS_DIR"] = str(skills_dir)

        # Re-import to ensure patch is active
        import cli  # noqa: F401
        from deepagents_cli.config import Settings

        s = Settings.from_environment()
        result = s.get_project_agent_skills_dir()

        assert result == skills_dir

    def test_falls_back_when_env_not_set(self):
        """No AGENT_OS_SKILLS_DIR → falls back to original."""
        import cli  # noqa: F401
        from deepagents_cli.config import Settings

        s = Settings.from_environment()
        result = s.get_project_agent_skills_dir()

        # Should return the original project skills dir (based on project_root)
        # or None if not in a project
        if s.project_root:
            assert result == s.project_root / ".agents" / "skills"
        else:
            assert result is None

    def test_falls_back_when_dir_does_not_exist(self):
        """AGENT_OS_SKILLS_DIR set but dir missing → falls back."""
        os.environ["AGENT_OS_SKILLS_DIR"] = "/tmp/nonexistent-dir-xyz-12345"

        import cli  # noqa: F401
        from deepagents_cli.config import Settings

        s = Settings.from_environment()
        result = s.get_project_agent_skills_dir()

        # Should NOT return the nonexistent path
        if result is not None:
            assert str(result) != "/tmp/nonexistent-dir-xyz-12345"

    def test_different_env_values_return_different_paths(self, tmp_path):
        """Changing AGENT_OS_SKILLS_DIR changes the returned path."""
        import cli  # noqa: F401
        from deepagents_cli.config import Settings

        dir1 = tmp_path / "role-a"
        dir2 = tmp_path / "role-b"
        dir1.mkdir()
        dir2.mkdir()

        s = Settings.from_environment()

        os.environ["AGENT_OS_SKILLS_DIR"] = str(dir1)
        result1 = s.get_project_agent_skills_dir()

        os.environ["AGENT_OS_SKILLS_DIR"] = str(dir2)
        result2 = s.get_project_agent_skills_dir()

        assert result1 == dir1
        assert result2 == dir2
        assert result1 != result2


# ===========================================================================
# 2. Process-level isolation test (integration)
# ===========================================================================

class TestProcessIsolation:
    """Verify two concurrent processes see different skill dirs."""

    def test_concurrent_processes_see_isolated_skills(self, tmp_path):
        """Simulates two Invoke-Agent calls with different roles."""
        dir_engineer = tmp_path / "engineer-skills"
        dir_qa = tmp_path / "qa-skills"
        dir_engineer.mkdir()
        dir_qa.mkdir()

        # Write a test script that imports cli and prints the skill dir
        test_script = tmp_path / "probe.py"
        test_script.write_text(
            "import sys, os\n"
            f"sys.path.insert(0, '{_BIN_DIR}')\n"
            "import cli\n"
            "from deepagents_cli.config import Settings\n"
            "s = Settings.from_environment()\n"
            "result = s.get_project_agent_skills_dir()\n"
            "print(result)\n"
        )

        env_base = {**os.environ}
        env_base.pop("AGENT_OS_SKILLS_DIR", None)

        # Launch two processes in parallel with different AGENT_OS_SKILLS_DIR
        env1 = {**env_base, "AGENT_OS_SKILLS_DIR": str(dir_engineer), "AGENT_OS_ROLE": "engineer"}
        env2 = {**env_base, "AGENT_OS_SKILLS_DIR": str(dir_qa), "AGENT_OS_ROLE": "qa"}

        p1 = subprocess.Popen(
            [sys.executable, str(test_script)],
            env=env1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            [sys.executable, str(test_script)],
            env=env2,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        out1, err1 = p1.communicate(timeout=30)
        out2, err2 = p2.communicate(timeout=30)

        assert p1.returncode == 0, f"Process 1 failed: {err1.decode()}"
        assert p2.returncode == 0, f"Process 2 failed: {err2.decode()}"

        result1 = out1.decode().strip()
        result2 = out2.decode().strip()

        assert result1 == str(dir_engineer), f"Engineer got: {result1}"
        assert result2 == str(dir_qa), f"QA got: {result2}"


# ===========================================================================
# 3. Version compatibility guard
# ===========================================================================

class TestVersionCompatibility:
    """Guard tests to detect when deepagents_cli changes break our overrides."""

    def test_settings_has_get_project_agent_skills_dir(self):
        """Settings class still has the method we monkey-patch."""
        from deepagents_cli.config import Settings
        assert hasattr(Settings, "get_project_agent_skills_dir"), (
            "BREAKING: deepagents_cli removed Settings.get_project_agent_skills_dir"
        )

    def test_settings_has_get_project_skills_dir(self):
        """Settings class still has the secondary skills lookup."""
        from deepagents_cli.config import Settings
        assert hasattr(Settings, "get_project_skills_dir"), (
            "BREAKING: deepagents_cli removed Settings.get_project_skills_dir"
        )

    def test_settings_has_get_built_in_skills_dir(self):
        """Settings class still has built_in skills lookup."""
        from deepagents_cli.config import Settings
        assert hasattr(Settings, "get_built_in_skills_dir"), (
            "BREAKING: deepagents_cli removed Settings.get_built_in_skills_dir"
        )

    def test_create_cli_agent_exists(self):
        """create_cli_agent function is still importable."""
        from deepagents_cli.agent import create_cli_agent
        assert callable(create_cli_agent), (
            "BREAKING: deepagents_cli.agent.create_cli_agent is not callable"
        )

    def test_create_cli_agent_accepts_enable_skills(self):
        """create_cli_agent still has enable_skills parameter."""
        import inspect
        from deepagents_cli.agent import create_cli_agent

        sig = inspect.signature(create_cli_agent)
        assert "enable_skills" in sig.parameters, (
            "BREAKING: create_cli_agent no longer has enable_skills param"
        )

    def test_skills_middleware_importable(self):
        """SkillsMiddleware is still importable from deepagents."""
        from deepagents.middleware import SkillsMiddleware
        assert SkillsMiddleware is not None, (
            "BREAKING: deepagents.middleware.SkillsMiddleware removed"
        )

    def test_run_textual_cli_async_importable_from_cli(self):
        """chat.py can still import run_textual_cli_async from cli."""
        from cli import run_textual_cli_async
        assert callable(run_textual_cli_async), (
            "BREAKING: cli.run_textual_cli_async not importable"
        )

    def test_deepagents_cli_version_tracked(self):
        """Record the current deepagents-cli version for change detection."""
        from deepagents_cli._version import __version__
        # This test always passes — it just prints the version for CI logs.
        # When it changes, review cli.py (agent wrapper) for API drift.
        print(f"\n  deepagents-cli version: {__version__}")

    def test_settings_from_environment_returns_instance(self):
        """Settings.from_environment() still works."""
        from deepagents_cli.config import Settings
        s = Settings.from_environment()
        assert isinstance(s, Settings)


# ===========================================================================
# 4. chat.py integration with cli.py
# ===========================================================================

class TestChatPyIntegration:
    """Verify chat.py inherits the Settings monkey-patch from cli.py."""

    def test_chat_imports_from_cli(self):
        """chat.py can import the key functions from cli.py."""
        from cli import run_textual_cli_async, _check_mcp_project_trust
        assert callable(run_textual_cli_async)
        assert callable(_check_mcp_project_trust)

    def test_chat_sees_patched_settings(self, tmp_path):
        """After cli is imported, Settings is patched for chat.py too."""
        skills_dir = tmp_path / "chat-skills"
        skills_dir.mkdir()

        os.environ["AGENT_OS_SKILLS_DIR"] = str(skills_dir)

        # Simulate what chat.py does: import from cli, then use Settings
        import cli  # noqa: F401
        from deepagents_cli.config import Settings
        s = Settings.from_environment()

        result = s.get_project_agent_skills_dir()
        assert result == skills_dir


# ===========================================================================
# 5. cli.py structure sanity checks
# ===========================================================================

class TestCliStructure:
    """Validate cli.py (behind .agents/bin/agent) has proper exports for downstream consumers."""

    def test_cli_main_is_callable(self):
        """cli_main exists and is callable."""
        from cli import cli_main
        assert callable(cli_main)

    def test_monkey_patch_installed_before_cli_main(self):
        """The monkey-patch is installed at module load time, not inside cli_main."""
        from deepagents_cli.config import Settings
        # The patched function should NOT be the original
        # (we stored the original as _original_get_project_agent_skills)
        from cli import _original_get_project_agent_skills
        assert Settings.get_project_agent_skills_dir is not _original_get_project_agent_skills, (
            "Monkey-patch was not installed — Settings still has original method"
        )

    def test_original_function_is_preserved(self):
        """The original function is saved for fallback."""
        from cli import _original_get_project_agent_skills
        assert callable(_original_get_project_agent_skills)

    def test_parse_args_exists(self):
        """parse_args is defined (checks cloned code is present)."""
        from cli import parse_args
        assert callable(parse_args)

    def test_run_textual_cli_async_exists(self):
        """run_textual_cli_async is defined (checks cloned code is present)."""
        from cli import run_textual_cli_async
        import asyncio
        assert asyncio.iscoroutinefunction(run_textual_cli_async)
