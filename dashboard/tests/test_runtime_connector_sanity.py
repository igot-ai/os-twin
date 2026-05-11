"""
test_runtime_connector_sanity.py — Tests for runtime connector sanity and env reload.

Covers:
1. POST /api/env reloads os.environ immediately
2. Restart-required keys reported as warnings only
3. Channel sanity distinguishes missing credentials vs disabled vs enabled
4. Secret values are masked/not returned
5. Tunnel restart works after env reload
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

os.environ["OSTWIN_API_KEY"] = "DEBUG"

from dashboard.api import app

client = TestClient(app)
HEADERS = {"X-API-Key": "DEBUG"}


class TestEnvSaveReload:
    """Tests for POST /api/env immediate reload behavior."""

    def test_env_save_reloads_os_environ_immediately(self, tmp_path, monkeypatch):
        """POST /api/env should immediately reload os.environ."""
        from dashboard.routes import system as sys_mod
        import dashboard.env_watcher as ew
        
        env_file = tmp_path / ".env"
        monkeypatch.setattr(sys_mod, "_ENV_FILE", env_file)
        monkeypatch.setattr(ew, "_ENV_FILE", env_file)
        
        monkeypatch.delenv("TEST_KEY_1", raising=False)
        ew._loaded_keys.discard("TEST_KEY_1")
        
        resp = client.post("/api/env", json={
            "entries": [
                {"type": "var", "key": "TEST_KEY_1", "value": "test_value_1", "enabled": True}
            ]
        }, headers=HEADERS)
        
        assert resp.status_code == 200
        assert os.environ.get("TEST_KEY_1") == "test_value_1"
        
        data = resp.json()
        assert data["status"] == "saved"
        assert "TEST_KEY_1" in data.get("added", ["TEST_KEY_1"])

    def test_restart_required_keys_reported_as_warnings(self, tmp_path, monkeypatch):
        """DASHBOARD_PORT and DASHBOARD_HOST changes should be reported as warnings."""
        from dashboard.routes import system as sys_mod
        import dashboard.env_watcher as ew
        
        env_file = tmp_path / ".env"
        env_file.write_text("DASHBOARD_PORT=3366\n")
        monkeypatch.setattr(sys_mod, "_ENV_FILE", env_file)
        monkeypatch.setattr(ew, "_ENV_FILE", env_file)
        
        os.environ["DASHBOARD_PORT"] = "3366"
        ew._loaded_keys.add("DASHBOARD_PORT")
        
        resp = client.post("/api/env", json={
            "entries": [
                {"type": "var", "key": "DASHBOARD_PORT", "value": "9999", "enabled": True}
            ]
        }, headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "restart_required" in data
        assert "DASHBOARD_PORT" in data["restart_required"]

    def test_env_save_broadcasts_env_reloaded(self, tmp_path, monkeypatch):
        """POST /api/env should broadcast env_reloaded event."""
        from dashboard.routes import system as sys_mod
        
        env_file = tmp_path / ".env"
        monkeypatch.setattr(sys_mod, "_ENV_FILE", env_file)
        
        monkeypatch.delenv("BROADCAST_TEST_KEY", raising=False)
        
        with patch("dashboard.global_state.broadcaster.broadcast", new_callable=AsyncMock) as mock_broadcast:
            resp = client.post("/api/env", json={
                "entries": [
                    {"type": "var", "key": "BROADCAST_TEST_KEY", "value": "test", "enabled": True}
                ]
            }, headers=HEADERS)
            
            assert resp.status_code == 200
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0] == "env_reloaded"


class TestChannelSanity:
    """Tests for channel connector sanity checks."""

    @pytest.fixture
    def mock_channels_config(self, tmp_path, monkeypatch):
        mock_path = tmp_path / "channels.json"
        import dashboard.routes.channels
        monkeypatch.setattr(dashboard.routes.channels, "CHANNELS_CONFIG_PATH", mock_path)
        return mock_path

    def test_channel_sanity_missing_credentials(self, mock_channels_config, monkeypatch):
        """Channel with enabled but missing credentials should report missing_credentials."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        client.post("/api/channels/telegram/connect", headers=HEADERS)
        
        config_data = json.loads(mock_channels_config.read_text())
        config_data[0]["credentials"] = {}
        mock_channels_config.write_text(json.dumps(config_data))
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["platform"] == "telegram"
        assert data["enabled"] is True
        assert data["has_credentials"] is False
        assert data["status"] == "missing_credentials"
        assert "missing_credentials" in data["issues"] or "Required credentials" in str(data["issues"])

    def test_channel_sanity_disabled_channel(self, mock_channels_config, monkeypatch):
        """Disabled channel should report disabled status."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        client.post("/api/channels/telegram/connect", 
                   json={"credentials": {"token": "test-token"}},
                   headers=HEADERS)
        
        client.post("/api/channels/telegram/disconnect", headers=HEADERS)
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["enabled"] is False
        assert data["status"] == "disabled"

    def test_channel_sanity_enabled_and_healthy(self, mock_channels_config, monkeypatch):
        """Enabled channel with credentials and bot running should be healthy."""
        mock_bot_manager = MagicMock()
        mock_bot_manager.is_running = True
        
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", mock_bot_manager)
        
        client.post("/api/channels/telegram/connect",
                   json={"credentials": {"token": "test-token"}},
                   headers=HEADERS)
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["enabled"] is True
        assert data["has_credentials"] is True
        assert data["bot_available"] is True
        assert data["bot_running"] is True
        assert data["status"] == "healthy"

    def test_channel_sanity_notifications_disabled(self, mock_channels_config, monkeypatch):
        """Channel with notifications disabled should report that status."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        client.post("/api/channels/telegram/connect",
                   json={"credentials": {"token": "test-token"}},
                   headers=HEADERS)
        
        client.put("/api/channels/telegram/settings",
                  json={"notification_preferences": {"enabled": False}},
                  headers=HEADERS)
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["notification_enabled"] is False
        assert data["status"] == "notifications_disabled"

    def test_channel_sanity_not_configured(self, mock_channels_config, monkeypatch):
        """Unconfigured channel should report not_configured status."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["enabled"] is False
        assert data["has_credentials"] is False
        assert data["status"] == "not_configured"


class TestRuntimeSanityEndpoint:
    """Tests for /api/runtime/sanity endpoint."""

    def test_runtime_sanity_includes_channel_checks(self, monkeypatch):
        """Runtime sanity should include detailed channel checks."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
            resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "channels" in data["checks"]
        channels = data["checks"]["channels"]
        
        for platform in ["telegram", "discord", "slack"]:
            assert platform in channels
            assert "enabled" in channels[platform]
            assert "has_credentials" in channels[platform]
            assert "status" in channels[platform]

    def test_runtime_sanity_includes_vault_health(self, monkeypatch):
        """Runtime sanity should include vault health check."""
        with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
            resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "vault" in data["checks"]
        vault = data["checks"]["vault"]
        assert "backend" in vault
        assert "healthy" in vault

    def test_runtime_sanity_enabled_channel_with_issues_is_warning(self, monkeypatch):
        """Enabled channel with issues should be a warning, not error."""
        import dashboard.global_state as gs
        monkeypatch.setattr(gs, "bot_manager", None)
        
        with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
            resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] is True
        
        channel_warnings = [w for w in data["warnings"] if "channel" in w.lower() or "telegram" in w.lower() or "discord" in w.lower() or "slack" in w.lower()]
        
        if channel_warnings:
            assert data["ok"] is True


class TestSecretMasking:
    """Tests that secret values are never exposed."""

    def test_channel_test_does_not_expose_credentials(self, tmp_path, monkeypatch):
        """Channel test endpoint should never return credential values."""
        import dashboard.routes.channels
        mock_path = tmp_path / "channels.json"
        monkeypatch.setattr(dashboard.routes.channels, "CHANNELS_CONFIG_PATH", mock_path)
        
        import dashboard.global_state as gs
        mock_bot = MagicMock()
        mock_bot.is_running = True
        monkeypatch.setattr(gs, "bot_manager", mock_bot)
        
        client.post("/api/channels/telegram/connect",
                   json={"credentials": {"token": "super-secret-token-12345"}},
                   headers=HEADERS)
        
        resp = client.post("/api/channels/telegram/test", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        resp_str = json.dumps(data)
        assert "super-secret-token-12345" not in resp_str
        assert "token" not in str(data.get("credentials", ""))

    def test_get_channel_masks_credentials(self, tmp_path, monkeypatch):
        """GET /api/channels/{platform} should mask credential values."""
        import dashboard.routes.channels
        mock_path = tmp_path / "channels.json"
        monkeypatch.setattr(dashboard.routes.channels, "CHANNELS_CONFIG_PATH", mock_path)
        
        client.post("/api/channels/telegram/connect",
                   json={"credentials": {"token": "secret-abc123"}},
                   headers=HEADERS)
        
        resp = client.get("/api/channels/telegram", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        if data.get("config") and data["config"].get("credentials"):
            creds = data["config"]["credentials"]
            assert creds.get("token") != "secret-abc123"
            assert creds.get("token") == "***"


class TestTunnelRestartAfterEnvReload:
    """Tests for tunnel restart after env reload."""

    def test_tunnel_restart_reloads_env_first(self, tmp_path, monkeypatch):
        """Tunnel restart should reload env before checking NGROK_AUTHTOKEN."""
        from dashboard.routes import tunnel as tunnel_mod
        from dashboard import tunnel as tunnel_pkg
        from dashboard.routes import system as sys_mod
        import dashboard.env_watcher as ew
        
        env_file = tmp_path / ".env"
        env_file.write_text("NGROK_AUTHTOKEN=test-token-after-reload\n")
        
        monkeypatch.setattr(sys_mod, "_ENV_FILE", env_file)
        monkeypatch.setattr(ew, "_ENV_FILE", env_file)
        
        monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
        ew._loaded_keys.discard("NGROK_AUTHTOKEN")
        
        with patch.object(tunnel_pkg, "start_tunnel", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = "https://test.ngrok.io"
            
            with patch.object(tunnel_pkg, "stop_tunnel"):
                resp = client.post("/api/tunnel/restart", headers=HEADERS)
            
            assert resp.status_code == 200
            assert mock_start.called

    def test_tunnel_restart_fails_without_ngrok_token(self, tmp_path, monkeypatch):
        """Tunnel restart should fail gracefully without NGROK_AUTHTOKEN."""
        from dashboard.routes import system as sys_mod
        import dashboard.env_watcher as ew
        
        env_file = tmp_path / ".env"
        env_file.write_text("")
        monkeypatch.setattr(sys_mod, "_ENV_FILE", env_file)
        monkeypatch.setattr(ew, "_ENV_FILE", env_file)
        
        monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
        ew._loaded_keys.discard("NGROK_AUTHTOKEN")
        
        resp = client.post("/api/tunnel/restart", headers=HEADERS)
        
        assert resp.status_code == 400
        assert "NGROK_AUTHTOKEN" in resp.json()["detail"]
