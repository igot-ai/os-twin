"""Tests for dashboard/deploy_preview.py."""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

os.environ["OSTWIN_API_KEY"] = "DEBUG"

from dashboard import deploy_preview


class TestResolveWorkingDir:
    """Tests for resolve_working_dir function."""

    def test_absolute_path_stays_absolute(self, tmp_path):
        plan_id = "test-plan-abs"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        working_dir = tmp_path / "my-absolute-project"
        working_dir.mkdir()
        
        meta = {
            "plan_id": plan_id,
            "working_dir": str(working_dir),
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == working_dir.resolve()
        assert result.is_absolute()

    def test_dot_resolves_to_project_root(self, tmp_path):
        plan_id = "test-plan-dot"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        
        meta = {
            "plan_id": plan_id,
            "working_dir": ".",
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            with patch("dashboard.api_utils.PROJECT_ROOT", tmp_path):
                result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == tmp_path.resolve()

    def test_dot_slash_resolves_to_project_root(self, tmp_path):
        plan_id = "test-plan-dotslash"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        
        meta = {
            "plan_id": plan_id,
            "working_dir": "./",
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            with patch("dashboard.api_utils.PROJECT_ROOT", tmp_path):
                result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == tmp_path.resolve()

    def test_projects_prefix_resolves_under_project_root(self, tmp_path):
        plan_id = "test-plan-projects"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        
        meta = {
            "plan_id": plan_id,
            "working_dir": "projects/my-app",
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            with patch("dashboard.api_utils.PROJECT_ROOT", tmp_path):
                result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == (tmp_path / "projects" / "my-app").resolve()

    def test_projects_backslash_prefix_resolves_under_project_root(self, tmp_path):
        plan_id = "test-plan-projects-backslash"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        
        meta = {
            "plan_id": plan_id,
            "working_dir": "projects\\my-app",
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            with patch("dashboard.api_utils.PROJECT_ROOT", tmp_path):
                result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == (tmp_path / "projects" / "my-app").resolve()

    def test_other_relative_resolves_under_projects(self, tmp_path):
        plan_id = "test-plan-other-rel"
        plans_dir = tmp_path / ".agents" / "plans"
        plans_dir.mkdir(parents=True)
        
        meta = {
            "plan_id": plan_id,
            "working_dir": "my-app",
        }
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with patch("dashboard.api_utils.PLANS_DIR", plans_dir):
            with patch("dashboard.api_utils.PROJECT_ROOT", tmp_path):
                result = deploy_preview.resolve_working_dir(plan_id, plans_dir)
        
        assert result == (tmp_path / "projects" / "my-app").resolve()

    def test_raises_file_not_found_if_meta_missing(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        
        with pytest.raises(FileNotFoundError, match="Plan meta not found"):
            deploy_preview.resolve_working_dir("nonexistent", plans_dir)

    def test_raises_key_error_if_working_dir_missing(self, tmp_path):
        plan_id = "test-plan"
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        
        meta = {"plan_id": plan_id}
        (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        
        with pytest.raises(KeyError, match="working_dir not set"):
            deploy_preview.resolve_working_dir(plan_id, plans_dir)


class TestCheckPathAvailability:
    """Tests for check_path_availability function."""

    def test_existing_writable_directory(self, tmp_path):
        result = deploy_preview.check_path_availability(tmp_path)
        assert result["ok"] is True
        assert result["exists"] is True
        assert result["writable"] is True
        assert result["is_file"] is False
        assert result["creatable"] is True
        assert result["resolved_path"] == str(tmp_path.resolve())
        assert result["error"] is None

    def test_path_points_to_file(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        
        result = deploy_preview.check_path_availability(file_path)
        assert result["ok"] is False
        assert result["exists"] is True
        assert result["is_file"] is True
        assert "file, not a directory" in result["error"]

    def test_nonexistent_path_with_existing_parent(self, tmp_path):
        new_path = tmp_path / "new_directory"
        
        result = deploy_preview.check_path_availability(new_path)
        assert result["ok"] is True
        assert result["exists"] is False
        assert result["writable"] is True
        assert result["creatable"] is True
        assert new_path.exists() is False

    def test_nonexistent_path_with_missing_parent_not_created(self, tmp_path):
        missing_parent = tmp_path / "missing_parent"
        new_path = missing_parent / "new_directory"
        
        assert missing_parent.exists() is False
        
        result = deploy_preview.check_path_availability(new_path)
        assert result["ok"] is True
        assert result["exists"] is False
        assert missing_parent.exists() is False

    def test_deeply_nested_missing_path_not_created(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "project"
        
        result = deploy_preview.check_path_availability(deep_path)
        assert result["exists"] is False
        assert (tmp_path / "a").exists() is False

    def test_returns_all_required_keys(self, tmp_path):
        result = deploy_preview.check_path_availability(tmp_path)
        required_keys = {"ok", "exists", "is_file", "writable", "creatable", "resolved_path", "error"}
        assert required_keys.issubset(result.keys())

    def test_non_writable_existing_directory(self, tmp_path):
        if platform.system() == "Windows":
            pytest.skip("Permission test unreliable on Windows")
        
        import stat
        dir_path = tmp_path / "readonly"
        dir_path.mkdir()
        
        original_mode = dir_path.stat().st_mode
        dir_path.chmod(stat.S_IRUSR | stat.S_IXUSR)
        
        try:
            result = deploy_preview.check_path_availability(dir_path)
            assert result["ok"] is False
            assert "not writable" in result["error"].lower()
        finally:
            dir_path.chmod(original_mode)


class TestDetectPackageManager:
    """Tests for _detect_package_manager function."""

    def test_pnpm_lock_detected(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "pnpm"

    def test_bun_lock_detected(self, tmp_path):
        (tmp_path / "bun.lock").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "bun"

    def test_bun_lockb_detected(self, tmp_path):
        (tmp_path / "bun.lockb").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "bun"

    def test_yarn_lock_detected(self, tmp_path):
        (tmp_path / "yarn.lock").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "yarn"

    def test_npm_lock_detected(self, tmp_path):
        (tmp_path / "package-lock.json").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "npm"

    def test_npm_fallback_when_no_lockfile(self, tmp_path):
        assert deploy_preview._detect_package_manager(tmp_path) == "npm"

    def test_pnpm_priority_over_others(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").touch()
        (tmp_path / "package-lock.json").touch()
        (tmp_path / "yarn.lock").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "pnpm"

    def test_yarn_priority_over_npm(self, tmp_path):
        (tmp_path / "yarn.lock").touch()
        (tmp_path / "package-lock.json").touch()
        assert deploy_preview._detect_package_manager(tmp_path) == "yarn"


class TestDetectPreviewCommand:
    """Tests for detect_preview_command function."""

    def test_detects_pnpm_dev_script(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "pnpm-lock.yaml").touch()
        
        with patch("dashboard.deploy_preview._find_executable", return_value="/usr/bin/pnpm"):
            cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "pnpm:dev"
        assert argv == ["/usr/bin/pnpm", "run", "dev"]

    def test_detects_npm_preview_script(self, tmp_path):
        pkg = {"scripts": {"preview": "vite preview"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "package-lock.json").touch()
        
        with patch("dashboard.deploy_preview._find_executable", return_value="/usr/bin/npm"):
            cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "npm:preview"
        assert argv == ["/usr/bin/npm", "run", "preview"]

    def test_detects_yarn_start_script(self, tmp_path):
        pkg = {"scripts": {"start": "node server.js"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "yarn.lock").touch()
        
        with patch("dashboard.deploy_preview._find_executable", return_value="/usr/bin/yarn"):
            cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "yarn:start"

    def test_priority_dev_over_preview_and_start(self, tmp_path):
        pkg = {"scripts": {"dev": "vite dev", "preview": "vite preview", "start": "node server"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        with patch("dashboard.deploy_preview._find_executable", return_value="/usr/bin/npm"):
            cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "npm:dev"

    def test_falls_back_to_static_index_html_in_dist(self, tmp_path):
        (tmp_path / "dist" / "index.html").parent.mkdir(parents=True)
        (tmp_path / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert "http.server" in cmd
        assert method == "static:http.server"
        assert argv is not None
        assert "{port}" in " ".join(argv)
        assert "--directory" in argv
        assert "dist" in argv

    def test_static_prefers_root_over_dist(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        (tmp_path / "dist" / "index.html").parent.mkdir(parents=True)
        (tmp_path / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert "dist" not in cmd or "." in cmd

    def test_static_ignores_node_modules(self, tmp_path):
        (tmp_path / "node_modules" / "some-package" / "index.html").parent.mkdir(parents=True)
        (tmp_path / "node_modules" / "some-package" / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "not_configured"

    def test_static_ignores_git_and_agents(self, tmp_path):
        (tmp_path / ".git" / "index.html").parent.mkdir(parents=True)
        (tmp_path / ".git" / "index.html").write_text("<html></html>", encoding="utf-8")
        (tmp_path / ".agents" / "index.html").parent.mkdir(parents=True)
        (tmp_path / ".agents" / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert method == "not_configured"

    def test_static_with_path_containing_spaces(self, tmp_path):
        space_dir = tmp_path / "my app"
        space_dir.mkdir()
        (space_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(space_dir)
        
        assert argv is not None
        assert "--directory" in argv
        dir_idx = argv.index("--directory")
        assert dir_idx + 1 < len(argv)

    def test_static_uses_sys_executable(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert argv[0] == sys.executable

    def test_static_includes_bind_127_0_0_1(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        
        assert "--bind" in argv
        bind_idx = argv.index("--bind")
        assert argv[bind_idx + 1] == "127.0.0.1"

    def test_returns_not_configured_when_nothing_found(self, tmp_path):
        cmd, method, argv = deploy_preview.detect_preview_command(tmp_path)
        assert cmd is None
        assert method == "not_configured"
        assert argv is None


class TestFindFreePort:
    """Tests for find_free_port function."""

    def test_finds_available_port(self):
        port = deploy_preview.find_free_port(start_port=35000, max_attempts=100)
        assert 35000 <= port < 35100

    def test_returns_first_available_port(self):
        port1 = deploy_preview.find_free_port(start_port=35100)
        port2 = deploy_preview.find_free_port(start_port=35100)
        assert port1 == port2

    def test_raises_when_no_port_available(self):
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = OSError("Address already in use")
            mock_socket.return_value.__enter__.return_value = mock_sock
            
            with pytest.raises(OSError, match="No free port found"):
                deploy_preview.find_free_port(start_port=3000, max_attempts=10)


class TestIsProcessAlive:
    """Tests for is_process_alive function."""

    def test_returns_false_for_none_pid(self):
        assert deploy_preview.is_process_alive(None) is False

    def test_detects_alive_process(self):
        current_pid = os.getpid()
        assert deploy_preview.is_process_alive(current_pid) is True

    def test_detects_dead_process(self):
        fake_pid = 999999999
        assert deploy_preview.is_process_alive(fake_pid) is False


class TestPreviewStatePersistence:
    """Tests for preview state read/write functions."""

    def test_write_and_read_state(self, tmp_path):
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        
        deploy_preview.write_preview_state(tmp_path, state)
        result = deploy_preview.read_preview_state(tmp_path)
        
        assert result == state

    def test_read_returns_none_for_missing_file(self, tmp_path):
        result = deploy_preview.read_preview_state(tmp_path)
        assert result is None

    def test_read_handles_corrupt_json(self, tmp_path):
        state_path = deploy_preview.get_preview_state_path(tmp_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not valid json {{{", encoding="utf-8")
        
        result = deploy_preview.read_preview_state(tmp_path)
        assert result is None

    def test_state_path_location(self, tmp_path):
        path = deploy_preview.get_preview_state_path(tmp_path)
        assert path == tmp_path / ".agents" / "deploy" / "preview.json"

    def test_log_path_location(self, tmp_path):
        path = deploy_preview.get_preview_log_path(tmp_path)
        assert path == tmp_path / ".agents" / "logs" / "preview.log"

    def test_uses_utf8_encoding(self, tmp_path):
        state = {"test": "value with unicode: \u00e9\u00e8\u00ea"}
        deploy_preview.write_preview_state(tmp_path, state)
        
        state_path = deploy_preview.get_preview_state_path(tmp_path)
        raw = state_path.read_text(encoding="utf-8")
        result = deploy_preview.read_preview_state(tmp_path)
        assert result["test"] == "value with unicode: \u00e9\u00e8\u00ea"


class TestGetPreviewStatus:
    """Tests for get_preview_status function."""

    def test_returns_not_configured_when_no_state_no_command(self, tmp_path):
        status = deploy_preview.get_preview_status(tmp_path)
        assert status["status"] == "not_configured"
        assert status["detection_method"] == "not_configured"

    def test_returns_stopped_when_command_found(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        status = deploy_preview.get_preview_status(tmp_path)
        assert status["status"] == "stopped"
        assert status["command"] == "npm run dev"
        assert status["detection_method"] == "npm:dev"

    def test_returns_running_when_pid_alive(self, tmp_path):
        state = {
            "pid": os.getpid(),
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            status = deploy_preview.get_preview_status(tmp_path)
        
        assert status["status"] == "running"
        assert status["local_url"] == "http://127.0.0.1:3000"

    def test_returns_stopped_when_pid_dead_and_updates_state(self, tmp_path):
        state = {
            "pid": 999999999,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        status = deploy_preview.get_preview_status(tmp_path)
        assert status["status"] == "stopped"
        assert status["pid"] is None
        
        updated_state = deploy_preview.read_preview_state(tmp_path)
        assert updated_state["pid"] is None
        assert updated_state["updated_at"] is not None

    def test_includes_public_url_from_tunnel(self, tmp_path):
        state = {
            "pid": os.getpid(),
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            with patch("dashboard.tunnel.get_tunnel_url", return_value="https://abc123.ngrok.io"):
                status = deploy_preview.get_preview_status(tmp_path)
        
        assert status["public_url"] == "https://abc123.ngrok.io"

    def test_includes_all_required_fields(self, tmp_path):
        status = deploy_preview.get_preview_status(tmp_path)
        
        required_fields = [
            "status", "pid", "port", "local_url", "public_url",
            "command", "detection_method", "started_at", "updated_at",
            "working_dir", "log_file", "error"
        ]
        for field in required_fields:
            assert field in status, f"Missing field: {field}"

    def test_working_dir_included(self, tmp_path):
        status = deploy_preview.get_preview_status(tmp_path)
        assert status["working_dir"] == str(tmp_path)


class TestStartPreview:
    """Tests for start_preview function."""

    def test_raises_path_check_error_for_invalid_path(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("test", encoding="utf-8")
        
        with pytest.raises(deploy_preview.PathCheckError, match="file, not a directory"):
            deploy_preview.start_preview(file_path)

    def test_raises_config_error_when_no_command(self, tmp_path):
        with pytest.raises(deploy_preview.PreviewConfigError, match="No preview command"):
            deploy_preview.start_preview(tmp_path)

    def test_starts_npm_preview(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    status = deploy_preview.start_preview(tmp_path)
        
        assert status["status"] == "running"
        assert status["port"] == 3100
        mock_popen.assert_called_once()
        
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["cwd"] == str(tmp_path)
        assert call_kwargs["env"]["PORT"] == "3100"

    def test_starts_static_server(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            with patch("dashboard.deploy_preview.find_free_port", return_value=3200):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    status = deploy_preview.start_preview(tmp_path)
        
        assert status["port"] == 3200
        call_args = mock_popen.call_args[0]
        call_kwargs = mock_popen.call_args[1]
        
        assert call_args[0][0] == sys.executable
        assert "-m" in call_args[0]
        assert "http.server" in call_args[0]

    def test_idempotent_returns_existing_if_running(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                status = deploy_preview.start_preview(tmp_path)
        
        assert status["pid"] == 12345
        mock_popen.assert_not_called()

    def test_uses_specified_port(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("dashboard.deploy_preview.find_free_port") as mock_find_port:
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    status = deploy_preview.start_preview(tmp_path, port=4500)
        
        assert status["port"] == 4500
        mock_find_port.assert_not_called()

    def test_sets_port_env_var(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 11111
        
        captured_env = {}
        
        def capture_popen(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return mock_proc
        
        with patch("subprocess.Popen", side_effect=capture_popen):
            with patch("dashboard.deploy_preview.find_free_port", return_value=3800):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    deploy_preview.start_preview(tmp_path)
        
        assert captured_env.get("PORT") == "3800"

    def test_log_file_closed_after_start(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        opened_files = []
        original_open = open
        
        def track_open(*args, **kwargs):
            f = original_open(*args, **kwargs)
            opened_files.append(f)
            return f
        
        with patch("builtins.open", side_effect=track_open):
            with patch("subprocess.Popen", return_value=mock_proc):
                with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                    with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                        deploy_preview.start_preview(tmp_path)
        
        for f in opened_files:
            assert f.closed, "Log file should be closed after start"

    def test_windows_start_new_process_group(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        # CREATE_NEW_PROCESS_GROUP only exists on Windows; set a mock value
        mock_flag = 256
        with patch("platform.system", return_value="Windows"):
            with patch.object(subprocess, "CREATE_NEW_PROCESS_GROUP", mock_flag, create=True):
                with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                    with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                            deploy_preview.start_preview(tmp_path)
        
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs.get("creationflags") == mock_flag

    def test_unix_start_new_session(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                    with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                        deploy_preview.start_preview(tmp_path)
        
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs.get("start_new_session") is True


class TestStopPreview:
    """Tests for stop_preview function."""

    def test_stops_running_process(self, tmp_path):
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            if platform.system() == "Windows":
                with patch("subprocess.run") as mock_run:
                    status = deploy_preview.stop_preview(tmp_path)
                    call_args = mock_run.call_args[0][0]
                    assert "taskkill" in call_args
                    assert "/F" in call_args
                    assert "/T" in call_args
                    assert "/PID" in call_args
            else:
                with patch("os.getpgid", return_value=12345):
                    with patch("os.killpg"):
                        status = deploy_preview.stop_preview(tmp_path)
        
        assert status["status"] == "stopped"

    def test_windows_uses_taskkill_with_tree_flag(self, tmp_path):
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("platform.system", return_value="Windows"):
            with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                with patch("subprocess.run") as mock_run:
                    deploy_preview.stop_preview(tmp_path)
                    
                    call_args = mock_run.call_args[0][0]
                    assert "/T" in call_args

    def test_handles_no_existing_state(self, tmp_path):
        status = deploy_preview.stop_preview(tmp_path)
        assert status["status"] == "not_configured"

    def test_handles_already_stopped_process(self, tmp_path):
        state = {
            "pid": 999999999,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        status = deploy_preview.stop_preview(tmp_path)
        assert status["status"] == "stopped"

    def test_handles_process_kill_error(self, tmp_path):
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
            if platform.system() == "Windows":
                with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
                    status = deploy_preview.stop_preview(tmp_path)
            else:
                with patch("os.killpg", side_effect=ProcessLookupError("No such process")):
                    with patch("os.getpgid", return_value=12345):
                        status = deploy_preview.stop_preview(tmp_path)
        
        assert status["status"] == "stopped"

    def test_updates_updated_at_on_stop(self, tmp_path):
        state = {
            "pid": 999999999,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
            "started_at": "2024-01-01T00:00:00Z",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        deploy_preview.stop_preview(tmp_path)
        
        updated = deploy_preview.read_preview_state(tmp_path)
        assert updated["updated_at"] is not None


class TestRestartPreview:
    """Tests for restart_preview function."""

    def test_restart_stops_and_starts(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        state = {
            "pid": 12345,
            "port": 3000,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        mock_proc = MagicMock()
        mock_proc.pid = 67890
        
        def is_alive_side_effect(pid):
            if pid == 12345:
                return False
            if pid == 67890:
                return True
            return False
        
        with patch("dashboard.deploy_preview.is_process_alive", side_effect=is_alive_side_effect):
            with patch("subprocess.Popen", return_value=mock_proc):
                with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                    status = deploy_preview.restart_preview(tmp_path)
        
        assert status["status"] == "running"
        assert status["pid"] == 67890

    def test_restart_reuses_port(self, tmp_path):
        pkg = {"scripts": {"dev": "vite"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        state = {
            "pid": 12345,
            "port": 3500,
            "command": "npm run dev",
            "detection_method": "npm:dev",
        }
        deploy_preview.write_preview_state(tmp_path, state)
        
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=False):
            with patch("subprocess.Popen", return_value=mock_proc):
                with patch("dashboard.deploy_preview.find_free_port", return_value=3100):
                    status = deploy_preview.restart_preview(tmp_path)
        
        assert status["port"] == 3500


class TestIntegration:
    """Integration-style tests for the full workflow."""

    def test_full_lifecycle(self, tmp_path):
        pkg = {"scripts": {"dev": "node server.js"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        
        status = deploy_preview.get_preview_status(tmp_path)
        assert status["status"] == "stopped"
        assert status["detection_method"] == "npm:dev"
        
        mock_proc = MagicMock()
        mock_proc.pid = 22222
        
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("dashboard.deploy_preview.find_free_port", return_value=3333):
                with patch("dashboard.deploy_preview.is_process_alive", return_value=True):
                    status = deploy_preview.start_preview(tmp_path)
        
        assert status["status"] == "running"
        assert status["port"] == 3333
        
        state = deploy_preview.read_preview_state(tmp_path)
        assert state["pid"] == 22222
        assert state["port"] == 3333
        assert state["updated_at"] is not None
        
        with patch("dashboard.deploy_preview.is_process_alive", return_value=False):
            status = deploy_preview.stop_preview(tmp_path)
        
        assert status["status"] == "stopped"
        
        state = deploy_preview.read_preview_state(tmp_path)
        assert state["pid"] is None
