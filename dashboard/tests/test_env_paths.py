import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.paths import ostwin_home, ostwin_path


def test_env_watcher_uses_ostwin_home_path(tmp_path, monkeypatch):
    """env_watcher should watch OSTWIN_HOME/.env, not hardcoded user home."""
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "custom-ostwin"))

    # Clear module cache
    sys.modules.pop("dashboard.env_watcher", None)

    from dashboard.env_watcher import _ENV_FILE

    expected = tmp_path / "custom-ostwin" / ".env"
    assert _ENV_FILE == expected


def test_api_load_dotenv_override_when_ostwin_home_set(tmp_path, monkeypatch):
    """When OSTWIN_HOME is set, .env values should override existing env vars."""
    custom_home = tmp_path / "ostwin-install"
    custom_home.mkdir()
    env_file = custom_home / ".env"
    env_file.write_text("TEST_API_KEY=temp-install-key\n")

    # Set existing env var
    monkeypatch.setenv("TEST_API_KEY", "stale-shell-key")
    monkeypatch.setenv("OSTWIN_HOME", str(custom_home))

    # Clear module cache and reload api.py bootstrap
    sys.modules.pop("dashboard.api", None)

    # Import api.py which runs the bootstrap
    import dashboard.api

    # Should have been overridden by .env
    assert os.environ["TEST_API_KEY"] == "temp-install-key"


def test_api_no_override_when_ostwin_home_not_set(tmp_path, monkeypatch):
    """When OSTWIN_HOME is NOT set, .env values should NOT override existing env vars."""
    custom_home = tmp_path / "user-home-ostwin"
    custom_home.mkdir()
    env_file = custom_home / ".env"
    env_file.write_text("TEST_SHELL_KEY=dot-env-value\n")

    # Set existing env var
    monkeypatch.setenv("TEST_SHELL_KEY", "shell-value")
    # Do NOT set OSTWIN_HOME
    monkeypatch.delenv("OSTWIN_HOME", raising=False)

    # Patch Path.home() to return our custom home
    with patch("dashboard.api.Path.home", return_value=custom_home):
        sys.modules.pop("dashboard.api", None)
        import dashboard.api

        # Should NOT have been overridden
        assert os.environ["TEST_SHELL_KEY"] == "shell-value"


def test_read_room_handles_utf8_markdown(tmp_path):
    """read_room should handle brief.md with Vietnamese/Unicode text on Windows."""
    from dashboard.api_utils import read_room

    room_dir = tmp_path / "room-001"
    room_dir.mkdir()

    # Create status file
    (room_dir / "status").write_text("running", encoding="utf-8")

    # Create brief.md with Vietnamese text
    vietnamese_text = "# Kế hoạch\n\nMô tả công việc với tiếng Việt: Xin chào thế giới!"
    (room_dir / "brief.md").write_text(vietnamese_text, encoding="utf-8")

    result = read_room(room_dir)

    assert result["status"] == "running"
    assert "tiếng Việt" in result["task_description"]
    assert "Xin chào" in result["task_description"]


def test_read_room_handles_unicode_in_jsonl(tmp_path):
    """read_room should handle channel.jsonl with Unicode messages."""
    from dashboard.api_utils import read_room

    room_dir = tmp_path / "room-002"
    room_dir.mkdir()

    (room_dir / "status").write_text("active", encoding="utf-8")

    # Create channel.jsonl with Unicode
    jsonl_content = '{"from": "engineer", "to": "manager", "body": "Tin nhắn với ký tự đặc biệt: ⬡ 🎉", "ts": "2024-01-01T00:00:00Z"}\n'
    (room_dir / "channel.jsonl").write_text(jsonl_content, encoding="utf-8")

    result = read_room(room_dir)

    assert result["message_count"] == 1
    assert result["last_activity"] == "2024-01-01T00:00:00Z"


def test_read_room_includes_metadata_with_unicode(tmp_path):
    """read_room with include_metadata should handle Unicode in all files."""
    from dashboard.api_utils import read_room

    room_dir = tmp_path / "room-003"
    room_dir.mkdir()

    (room_dir / "status").write_text("done", encoding="utf-8")

    # lifecycle.json with Unicode
    lifecycle = {"state": "completed", "note": "Hoàn thành ✓"}
    (room_dir / "lifecycle.json").write_text(
        __import__("json").dumps(lifecycle), encoding="utf-8"
    )

    # config.json with Unicode
    config = {"role": "engineer", "description": "Kỹ sư phát triển"}
    (room_dir / "config.json").write_text(
        __import__("json").dumps(config), encoding="utf-8"
    )

    # audit.log with Unicode
    (room_dir / "audit.log").write_text(
        "2024-01-01: Bắt đầu công việc\n", encoding="utf-8"
    )

    result = read_room(room_dir, include_metadata=True)

    assert result["lifecycle"]["note"] == "Hoàn thành ✓"
    assert result["config"]["description"] == "Kỹ sư phát triển"
    assert "Bắt đầu" in result["audit_tail"][0]


def test_read_channel_handles_unicode(tmp_path):
    """read_channel should handle Unicode in message bodies."""
    from dashboard.api_utils import read_channel

    room_dir = tmp_path / "room-004"
    room_dir.mkdir()

    messages = [
        '{"from": "a", "to": "b", "body": "Test message"}',
        '{"from": "c", "to": "d", "body": "Tin nhắn tiếng Việt"}',
        '{"from": "e", "to": "f", "body": "Emoji test: ⬡ 🎉 ✓"}',
    ]
    (room_dir / "channel.jsonl").write_text("\n".join(messages), encoding="utf-8")

    result = read_channel(room_dir)

    assert len(result) == 3
    assert "tiếng Việt" in result[1]["body"]
    assert "⬡" in result[2]["body"]
