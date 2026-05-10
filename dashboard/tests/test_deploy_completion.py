"""
test_deploy_completion.py — Tests for auto-deploy on plan completion.

Tests:
1. Completion triggers deploy once
2. Already running preview is not duplicated
3. not_configured deploy does not crash polling
4. Notification payload includes local/public URLs when present
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

os.environ["OSTWIN_API_KEY"] = "DEBUG"

from dashboard import deploy_completion
from dashboard.deploy_completion import (
    read_progress_json,
    is_plan_completed,
    get_deploy_completion_state,
    mark_deploy_attempted,
    auto_start_deploy_preview,
    broadcast_deploy_event,
    send_deploy_notification,
    handle_plan_completion,
)


class TestReadProgressJson:
    """Tests for read_progress_json function."""

    def test_reads_valid_progress(self, tmp_path):
        progress_data = {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "blocked": 0,
            "active": 0,
            "pending": 0,
            "pct_complete": 100.0,
            "rooms": [],
        }
        (tmp_path / "progress.json").write_text(json.dumps(progress_data))
        
        result = read_progress_json(tmp_path)
        
        assert result is not None
        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["pct_complete"] == 100.0

    def test_returns_none_for_missing_file(self, tmp_path):
        result = read_progress_json(tmp_path)
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        (tmp_path / "progress.json").write_text("not valid json {{{")
        result = read_progress_json(tmp_path)
        assert result is None


class TestIsPlanCompleted:
    """Tests for is_plan_completed function."""

    def test_all_passed_is_completed(self):
        progress = {
            "total": 5,
            "passed": 5,
            "failed": 0,
            "blocked": 0,
        }
        assert is_plan_completed(progress) is True

    def test_partial_passed_not_completed(self):
        progress = {
            "total": 5,
            "passed": 3,
            "failed": 0,
            "blocked": 0,
        }
        assert is_plan_completed(progress) is False

    def test_failed_blocks_completion(self):
        progress = {
            "total": 5,
            "passed": 4,
            "failed": 1,
            "blocked": 0,
        }
        assert is_plan_completed(progress) is False

    def test_blocked_blocks_completion(self):
        progress = {
            "total": 5,
            "passed": 4,
            "failed": 0,
            "blocked": 1,
        }
        assert is_plan_completed(progress) is False

    def test_zero_total_not_completed(self):
        progress = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
        }
        assert is_plan_completed(progress) is False


class TestDeployCompletionState:
    """Tests for completion state tracking."""

    def test_get_state_returns_defaults_when_no_state(self, tmp_path):
        state = get_deploy_completion_state(tmp_path)
        
        assert state["deploy_attempted_for_completion"] is False
        assert state["deploy_attempted_at"] is None

    def test_get_state_reads_existing_state(self, tmp_path):
        from dashboard.deploy_preview import write_preview_state
        
        now = datetime.now(timezone.utc).isoformat()
        write_preview_state(tmp_path, {
            "deploy_attempted_for_completion": True,
            "deploy_attempted_at": now,
            "pid": 12345,
        })
        
        state = get_deploy_completion_state(tmp_path)
        
        assert state["deploy_attempted_for_completion"] is True
        assert state["deploy_attempted_at"] == now

    def test_mark_deploy_attempted_persists(self, tmp_path):
        mark_deploy_attempted(tmp_path)
        
        state = get_deploy_completion_state(tmp_path)
        
        assert state["deploy_attempted_for_completion"] is True
        assert state["deploy_attempted_at"] is not None


class TestAutoStartDeployPreview:
    """Tests for auto_start_deploy_preview function."""

    @pytest.mark.asyncio
    async def test_completion_triggers_deploy_once(self, tmp_path):
        """Completion should trigger deploy exactly once."""
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    result1 = await auto_start_deploy_preview("test-plan", tmp_path)
        
        assert result1["deploy_started"] is True
        assert result1["already_attempted"] is False
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            result2 = await auto_start_deploy_preview("test-plan", tmp_path)
        
        assert result2["deploy_started"] is False
        assert result2["already_attempted"] is True

    @pytest.mark.asyncio
    async def test_already_running_preview_not_duplicated(self, tmp_path):
        """If preview is already running, should return existing status without new process."""
        from dashboard.deploy_preview import write_preview_state
        
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        
        write_preview_state(tmp_path, {
            "pid": os.getpid(),
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                result = await auto_start_deploy_preview("test-plan", tmp_path)
        
        assert result["deploy_status"]["status"] == "running"
        mock_popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_configured_deploy_does_not_crash(self, tmp_path):
        """not_configured deploy should return gracefully, not crash."""
        result = await auto_start_deploy_preview("test-plan", tmp_path)
        
        assert result["deploy_started"] is False
        assert result["deploy_status"]["status"] == "not_configured"
        assert result["error"] is not None
        
        state = get_deploy_completion_state(tmp_path)
        assert state["deploy_attempted_for_completion"] is True


class TestBroadcastDeployEvent:
    """Tests for broadcast_deploy_event function."""

    @pytest.mark.asyncio
    async def test_broadcasts_deploy_updated_event(self):
        """Should broadcast deploy_updated event with correct payload."""
        mock_broadcaster = AsyncMock()
        
        deploy_status = {
            "status": "running",
            "local_url": "http://127.0.0.1:3000",
            "public_url": "https://abc.ngrok.io",
            "port": 3000,
            "pid": 12345,
        }
        
        await broadcast_deploy_event(mock_broadcaster, "test-plan", deploy_status)
        
        mock_broadcaster.broadcast.assert_called_once()
        call_args = mock_broadcaster.broadcast.call_args
        
        assert call_args[0][0] == "deploy_updated"
        
        event_data = call_args[0][1]
        assert event_data["plan_id"] == "test-plan"
        assert event_data["deploy_status"] == "running"
        assert event_data["local_url"] == "http://127.0.0.1:3000"
        assert event_data["public_url"] == "https://abc.ngrok.io"

    @pytest.mark.asyncio
    async def test_no_broadcast_when_broadcaster_is_none(self):
        """Should not crash when broadcaster is None."""
        deploy_status = {"status": "running"}
        
        await broadcast_deploy_event(None, "test-plan", deploy_status)


class TestSendDeployNotification:
    """Tests for send_deploy_notification function."""

    @pytest.mark.asyncio
    async def test_notification_includes_local_and_public_urls(self):
        """Notification should include local and public URLs when present."""
        with patch("dashboard.notify.send_message", new_callable=AsyncMock, return_value=True) as mock_send:
            result = await send_deploy_notification(
                plan_id="test-plan-123",
                plan_title="My Test Plan",
                deploy_status={
                    "status": "running",
                    "local_url": "http://127.0.0.1:3000",
                    "public_url": "https://xyz.ngrok-free.app",
                },
                dashboard_base_url="https://xyz.ngrok-free.app",
            )
        
        assert result is True
        mock_send.assert_called_once()
        
        message = mock_send.call_args[0][0]
        assert "My Test Plan" in message
        assert "http://127.0.0.1:3000" in message
        assert "https://xyz.ngrok-free.app" in message
        assert "test-plan-123" in message

    @pytest.mark.asyncio
    async def test_notification_handles_not_configured_status(self):
        """Should send appropriate message when deploy not configured."""
        with patch("dashboard.notify.send_message", new_callable=AsyncMock, return_value=True) as mock_send:
            result = await send_deploy_notification(
                plan_id="test-plan",
                plan_title="Test Plan",
                deploy_status={
                    "status": "not_configured",
                    "error": "No preview command found",
                },
            )
        
        assert result is True
        message = mock_send.call_args[0][0]
        assert "not configured" in message.lower()

    @pytest.mark.asyncio
    async def test_notification_handles_error_status(self):
        """Should send appropriate message when deploy has error."""
        with patch("dashboard.notify.send_message", new_callable=AsyncMock, return_value=True) as mock_send:
            result = await send_deploy_notification(
                plan_id="test-plan",
                plan_title="Test Plan",
                deploy_status={
                    "status": "error",
                    "error": "Port allocation failed",
                },
            )
        
        assert result is True
        message = mock_send.call_args[0][0]
        assert "failed" in message.lower() or "error" in message.lower()

    @pytest.mark.asyncio
    async def test_notification_handles_missing_urls(self):
        """Should handle gracefully when URLs are missing."""
        with patch("dashboard.notify.send_message", new_callable=AsyncMock, return_value=True) as mock_send:
            result = await send_deploy_notification(
                plan_id="test-plan",
                plan_title="Test Plan",
                deploy_status={
                    "status": "running",
                    "local_url": None,
                    "public_url": None,
                },
            )
        
        assert result is True
        message = mock_send.call_args[0][0]
        assert "Test Plan" in message


class TestHandlePlanCompletion:
    """Tests for handle_plan_completion orchestration."""

    @pytest.mark.asyncio
    async def test_full_completion_flow(self, tmp_path):
        """Test the complete completion handling flow."""
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        
        mock_broadcaster = AsyncMock()
        
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("dashboard.deploy_preview.find_free_port", return_value=3200):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    with patch("dashboard.notify.send_message", new_callable=AsyncMock, return_value=True):
                        with patch("dashboard.tunnel.get_tunnel_url", return_value="https://test.ngrok.io"):
                            result = await handle_plan_completion(
                                plan_id="test-plan-456",
                                working_dir=tmp_path,
                                plan_title="Integration Test Plan",
                                broadcaster=mock_broadcaster,
                                dashboard_base_url="https://test.ngrok.io",
                            )
        
        assert result["plan_id"] == "test-plan-456"
        assert result["deploy_result"]["deploy_started"] is True
        assert result["notification_sent"] is True
        
        mock_broadcaster.broadcast.assert_called()

    @pytest.mark.asyncio
    async def test_idempotent_second_call(self, tmp_path):
        """Second call should be idempotent."""
        from dashboard.deploy_preview import write_preview_state
        
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        
        write_preview_state(tmp_path, {
            "deploy_attempted_for_completion": True,
            "deploy_attempted_at": datetime.now(timezone.utc).isoformat(),
        })
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=False):
            result = await handle_plan_completion(
                plan_id="test-plan",
                working_dir=tmp_path,
                plan_title="Test",
                broadcaster=None,
            )
        
        assert result["deploy_result"]["already_attempted"] is True
        assert result["deploy_result"]["deploy_started"] is False
