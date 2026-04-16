"""Tests for dashboard/env_watcher.py — .env hot-reload logic."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

import dashboard.env_watcher as ew


@pytest.fixture
def env_file(tmp_path):
    """Create a temporary .env file and point the watcher at it."""
    f = tmp_path / ".env"
    f.write_text(
        "# Comment line\n"
        "ALPHA=one\n"
        "BRAVO=two\n"
        "# CHARLIE=three\n"
    )
    return f


@pytest.fixture(autouse=True)
def reset_watcher_state():
    """Reset module-level state between tests."""
    orig_keys = ew._loaded_keys.copy()
    orig_mtime = ew._last_mtime
    ew._loaded_keys.clear()
    ew._last_mtime = 0.0
    yield
    ew._loaded_keys.clear()
    ew._loaded_keys.update(orig_keys)
    ew._last_mtime = orig_mtime


class TestParseEnvFile:
    def test_parses_active_keys(self, env_file):
        result = ew._parse_env_file(env_file)
        assert result == {"ALPHA": "one", "BRAVO": "two"}

    def test_ignores_comments(self, env_file):
        result = ew._parse_env_file(env_file)
        assert "CHARLIE" not in result

    def test_handles_missing_file(self, tmp_path):
        result = ew._parse_env_file(tmp_path / "nonexistent")
        assert result == {}

    def test_strips_quotes(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('KEY1="quoted"\nKEY2=\'single\'\nKEY3=plain\n')
        result = ew._parse_env_file(f)
        assert result == {"KEY1": "quoted", "KEY2": "single", "KEY3": "plain"}

    def test_handles_empty_file(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("")
        result = ew._parse_env_file(f)
        assert result == {}


class TestReloadEnvFile:
    def test_adds_new_keys(self, env_file, monkeypatch):
        monkeypatch.delenv("ALPHA", raising=False)
        monkeypatch.delenv("BRAVO", raising=False)

        result = ew.reload_env_file(path=env_file)

        assert "ALPHA" in result["added"]
        assert "BRAVO" in result["added"]
        assert os.environ["ALPHA"] == "one"
        assert os.environ["BRAVO"] == "two"

    def test_detects_changed_keys(self, env_file, monkeypatch):
        # Simulate a previous load
        monkeypatch.setenv("ALPHA", "old_value")
        ew._loaded_keys.add("ALPHA")

        result = ew.reload_env_file(path=env_file)

        assert "ALPHA" in result["changed"]
        assert os.environ["ALPHA"] == "one"

    def test_removes_deleted_keys(self, env_file, monkeypatch):
        # Simulate a key that was loaded before but is now gone
        monkeypatch.setenv("DELETED_KEY", "was_here")
        ew._loaded_keys.add("DELETED_KEY")

        result = ew.reload_env_file(path=env_file)

        assert "DELETED_KEY" in result["removed"]
        assert "DELETED_KEY" not in os.environ

    def test_removes_commented_out_keys(self, tmp_path, monkeypatch):
        """A key that was active and is now commented out should be removed."""
        f = tmp_path / ".env"
        f.write_text("ACTIVE=yes\n")
        ew.reload_env_file(path=f)
        assert os.environ.get("ACTIVE") == "yes"

        # Now comment it out
        f.write_text("# ACTIVE=yes\n")
        result = ew.reload_env_file(path=f)

        assert "ACTIVE" in result["removed"]
        assert "ACTIVE" not in os.environ

    def test_no_changes_returns_empty_lists(self, env_file, monkeypatch):
        # First load
        ew.reload_env_file(path=env_file)
        # Second load — nothing changed
        result = ew.reload_env_file(path=env_file)

        assert result["added"] == []
        assert result["changed"] == []
        assert result["removed"] == []

    def test_updates_last_mtime(self, env_file):
        assert ew._last_mtime == 0.0
        ew.reload_env_file(path=env_file)
        assert ew._last_mtime > 0.0

    def test_warns_on_restart_required_keys(self, tmp_path, monkeypatch, caplog):
        f = tmp_path / ".env"
        f.write_text("DASHBOARD_PORT=9999\n")
        monkeypatch.setenv("DASHBOARD_PORT", "3366")
        ew._loaded_keys.add("DASHBOARD_PORT")

        import logging
        with caplog.at_level(logging.WARNING, logger="dashboard.env_watcher"):
            ew.reload_env_file(path=f)

        assert any("restart" in r.message.lower() for r in caplog.records)


class TestWatchEnvFile:
    @pytest.mark.asyncio
    async def test_watch_detects_mtime_change(self, tmp_path, monkeypatch):
        """watch_env_file should call reload when mtime changes."""
        f = tmp_path / ".env"
        f.write_text("KEY=initial\n")

        # Patch module-level path and interval for fast testing
        monkeypatch.setattr(ew, "_ENV_FILE", f)
        monkeypatch.setattr(ew, "_POLL_INTERVAL", 0.1)

        import asyncio

        # Start watcher
        task = asyncio.create_task(ew.watch_env_file())

        # Wait for initial seed
        await asyncio.sleep(0.2)
        assert os.environ.get("KEY") == "initial" or "KEY" in ew._loaded_keys

        # Mutate the file
        f.write_text("KEY=updated\nNEW=hello\n")

        # Wait for detection
        await asyncio.sleep(0.5)

        assert os.environ.get("KEY") == "updated"
        assert os.environ.get("NEW") == "hello"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
