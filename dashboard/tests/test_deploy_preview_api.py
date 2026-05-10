"""
test_deploy_preview_api.py — Tests for deploy preview API endpoints.

Tests:
1. Invalid working_dir blocks /api/run before subprocess.Popen
2. Valid creatable working_dir passes
3. Deploy endpoints call deploy_preview helpers
4. Runtime sanity returns warnings for missing ngrok/channels
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from fastapi.testclient import TestClient

os.environ["OSTWIN_API_KEY"] = "DEBUG"

from dashboard.api import app
from dashboard import deploy_preview


client = TestClient(app)
HEADERS = {"X-API-Key": "DEBUG"}


class TestRunPathValidation:
    """Tests for /api/run path validation."""

    def test_invalid_working_dir_file_blocks_run(self, tmp_path, monkeypatch):
        """Invalid working_dir (points to file) should block /api/run before subprocess.Popen."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("test content")
        
        plan_id = "test-invalid-path"
        plan_content = f"""# Plan: Test Invalid Path

## Config

working_dir: {file_path}

---

## Goal

Test that invalid paths are blocked.

### EPIC-001 — Test Epic

#### Tasks

- [ ] TASK-001 — Test task

depends_on: []
"""
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        try:
            resp = client.post("/api/run", json={
                "plan": plan_content,
                "plan_id": plan_id,
            }, headers=HEADERS)
            
            assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
            data = resp.json()
            assert "detail" in data
            assert "Invalid working_dir" in data["detail"] or "file" in data["detail"].lower()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_valid_creatable_working_dir_passes(self, tmp_path, monkeypatch):
        """Valid creatable working_dir should pass path check."""
        new_dir = tmp_path / "new_project_dir"
        assert not new_dir.exists()
        
        plan_id = "test-valid-path"
        plan_content = f"""# Plan: Test Valid Path

## Config

working_dir: {new_dir}

---

## Goal

Test that valid paths are accepted.

### EPIC-001 — Test Epic

#### Tasks

- [ ] TASK-001 — Test task

depends_on: []
"""
        
        from dashboard.api_utils import PLANS_DIR, AGENTS_DIR
        from dashboard import global_state
        
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        roles_file = PLANS_DIR / f"{plan_id}.roles.json"
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        mock_init_result = MagicMock()
        mock_init_result.returncode = 0
        mock_init_result.stderr = ""
        
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            with patch("subprocess.run", return_value=mock_init_result) as mock_run:
                with patch.object(global_state, "store", None):
                    resp = client.post("/api/run", json={
                        "plan": plan_content,
                        "plan_id": plan_id,
                    }, headers=HEADERS)
        
        try:
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            
            assert data["status"] == "launched"
            assert "working_dir" in data
            assert "launch_log" in data
            assert "preflight" in data
            assert "runtime_sanity" in data
            
            assert data["preflight"]["path_check"]["ok"] is True
            
            mock_popen.assert_called_once()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)
            roles_file.unlink(missing_ok=True)

    def test_nonexistent_parent_directory_blocked(self, tmp_path):
        """Path with non-writable ancestor should be blocked."""
        if sys.platform == "win32":
            pytest.skip("Permission tests unreliable on Windows")
        
        import stat
        readonly_dir = tmp_path / "readonly_parent"
        readonly_dir.mkdir()
        
        original_mode = readonly_dir.stat().st_mode
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        
        try:
            blocked_path = readonly_dir / "cannot_create"
            
            plan_id = "test-blocked-path"
            plan_content = f"""# Plan: Test Blocked Path

## Config

working_dir: {blocked_path}

---

## Goal

Test blocked path.

### EPIC-001 — Test

depends_on: []
"""
            
            from dashboard.api_utils import PLANS_DIR
            plan_file = PLANS_DIR / f"{plan_id}.md"
            meta_file = PLANS_DIR / f"{plan_id}.meta.json"
            
            try:
                resp = client.post("/api/run", json={
                    "plan": plan_content,
                    "plan_id": plan_id,
                }, headers=HEADERS)
                
                assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
            finally:
                plan_file.unlink(missing_ok=True)
                meta_file.unlink(missing_ok=True)
        finally:
            readonly_dir.chmod(original_mode)


class TestDeployEndpoints:
    """Tests for deploy preview API endpoints."""

    def test_get_deploy_status_calls_helper(self, tmp_path, monkeypatch):
        """GET /api/plans/{plan_id}/deploy/status should call get_preview_status."""
        plan_id = "test-deploy-status"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        plan_file.write_text(f"# Plan: Deploy Status Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(tmp_path),
        }))
        
        mock_status = {
            "status": "stopped",
            "pid": None,
            "port": None,
            "local_url": None,
            "public_url": None,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        
        with patch("dashboard.deploy_preview.get_preview_status", return_value=mock_status) as mock_get:
            resp = client.get(f"/api/plans/{plan_id}/deploy/status", headers=HEADERS)
        
        try:
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "stopped"
            assert data["plan_id"] == plan_id
            mock_get.assert_called_once()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_start_deploy_calls_helper(self, tmp_path, monkeypatch):
        """POST /api/plans/{plan_id}/deploy/start should call start_preview."""
        plan_id = "test-deploy-start"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        plan_file.write_text(f"# Plan: Deploy Start Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(tmp_path),
        }))
        
        mock_status = {
            "status": "running",
            "pid": 12345,
            "port": 3000,
            "local_url": "http://127.0.0.1:3000",
            "public_url": None,
        }
        
        with patch("dashboard.deploy_preview.start_preview", return_value=mock_status) as mock_start:
            resp = client.post(f"/api/plans/{plan_id}/deploy/start", headers=HEADERS)
        
        try:
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert data["plan_id"] == plan_id
            mock_start.assert_called_once()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_stop_deploy_calls_helper(self, tmp_path, monkeypatch):
        """POST /api/plans/{plan_id}/deploy/stop should call stop_preview."""
        plan_id = "test-deploy-stop"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        plan_file.write_text(f"# Plan: Deploy Stop Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(tmp_path),
        }))
        
        mock_status = {
            "status": "stopped",
            "pid": None,
            "port": None,
        }
        
        with patch("dashboard.deploy_preview.stop_preview", return_value=mock_status) as mock_stop:
            resp = client.post(f"/api/plans/{plan_id}/deploy/stop", headers=HEADERS)
        
        try:
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "stopped"
            assert data["plan_id"] == plan_id
            mock_stop.assert_called_once()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_restart_deploy_calls_helper(self, tmp_path, monkeypatch):
        """POST /api/plans/{plan_id}/deploy/restart should call restart_preview."""
        plan_id = "test-deploy-restart"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        plan_file.write_text(f"# Plan: Deploy Restart Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(tmp_path),
        }))
        
        mock_status = {
            "status": "running",
            "pid": 67890,
            "port": 3001,
            "local_url": "http://127.0.0.1:3001",
        }
        
        with patch("dashboard.deploy_preview.restart_preview", return_value=mock_status) as mock_restart:
            resp = client.post(f"/api/plans/{plan_id}/deploy/restart", headers=HEADERS)
        
        try:
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert data["plan_id"] == plan_id
            mock_restart.assert_called_once()
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_deploy_start_invalid_path_returns_400(self, tmp_path):
        """POST /api/plans/{plan_id}/deploy/start with invalid path should return 400."""
        plan_id = "test-deploy-invalid"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        invalid_path = tmp_path / "a_file.txt"
        invalid_path.write_text("not a directory")
        
        plan_file.write_text(f"# Plan: Deploy Invalid Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(invalid_path),
        }))
        
        try:
            resp = client.post(f"/api/plans/{plan_id}/deploy/start", headers=HEADERS)
            assert resp.status_code == 400
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)


class TestRuntimeSanity:
    """Tests for /api/runtime/sanity endpoint."""

    def test_runtime_sanity_returns_warnings_for_missing_ngrok(self, monkeypatch):
        """Runtime sanity should return warnings for missing ngrok token."""
        monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
        
        with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
            resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "ok" in data
        assert "errors" in data
        assert "warnings" in data
        assert "checks" in data
        
        assert "ngrok" in data["checks"]
        assert data["checks"]["ngrok"]["token_configured"] is False
        
        ngrok_warnings = [w for w in data["warnings"] if "ngrok" in w.lower()]
        assert len(ngrok_warnings) > 0, "Should have warning for missing ngrok"
        
        assert data["ok"] is True, "Missing ngrok should not block (warnings, not errors)"

    def test_runtime_sanity_returns_warnings_for_disabled_channels(self, monkeypatch):
        """Runtime sanity should return warnings for disabled notification channels."""
        with patch("dashboard.notify.get_config", return_value={"bot_token": None, "authorized_chats": []}):
            with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
                resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "channels" in data["checks"]
        
        channel_warnings = [w for w in data["warnings"] if "channel" in w.lower() or "telegram" in w.lower()]
        assert len(channel_warnings) > 0, "Should have warning for disabled channels"
        
        assert data["ok"] is True, "Disabled channels should not block (warnings, not errors)"

    def test_runtime_sanity_with_plan_id_checks_working_dir(self, tmp_path, monkeypatch):
        """Runtime sanity with plan_id should check working_dir availability."""
        plan_id = "test-sanity-working-dir"
        
        from dashboard.api_utils import PLANS_DIR
        plan_file = PLANS_DIR / f"{plan_id}.md"
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        
        plan_file.write_text(f"# Plan: Sanity Working Dir Test\n\n### EPIC-001 — Test\n")
        meta_file.write_text(json.dumps({
            "plan_id": plan_id,
            "working_dir": str(tmp_path),
        }))
        
        try:
            with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
                resp = client.get(f"/api/runtime/sanity?plan_id={plan_id}", headers=HEADERS)
            
            assert resp.status_code == 200
            data = resp.json()
            
            assert "working_dir" in data["checks"]
            assert data["checks"]["working_dir"]["ok"] is True
        finally:
            plan_file.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)

    def test_runtime_sanity_missing_provider_is_error(self, monkeypatch):
        """Runtime sanity should return error if no LLM provider configured."""
        mock_resolver = MagicMock()
        mock_resolver.get_master_settings.return_value = MagicMock(
            providers=MagicMock(
                model_dump=MagicMock(return_value={})
            )
        )
        
        with patch("dashboard.lib.settings.get_settings_resolver", return_value=mock_resolver):
            with patch("dashboard.tunnel.get_tunnel_url", return_value=None):
                resp = client.get("/api/runtime/sanity", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        
        provider_errors = [e for e in data["errors"] if "provider" in e.lower()]
        assert len(provider_errors) > 0, "Should have error for missing provider"
        
        assert data["ok"] is False, "Missing provider should be blocking error"


class TestPathCheckEndpoint:
    """Tests for POST /api/plans/path/check endpoint."""

    def test_path_check_valid_directory(self, tmp_path):
        """Path check should return ok for valid directory."""
        resp = client.post("/api/plans/path/check", json={
            "path": str(tmp_path)
        }, headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["exists"] is True
        assert data["writable"] is True

    def test_path_check_creatable_directory(self, tmp_path):
        """Path check should return ok for creatable (non-existent) directory."""
        new_path = tmp_path / "new_project"
        
        resp = client.post("/api/plans/path/check", json={
            "path": str(new_path)
        }, headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["exists"] is False
        assert data["creatable"] is True

    def test_path_check_file_blocked(self, tmp_path):
        """Path check should return error for path pointing to file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        
        resp = client.post("/api/plans/path/check", json={
            "path": str(file_path)
        }, headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["is_file"] is True
        assert "file" in data["error"].lower()
