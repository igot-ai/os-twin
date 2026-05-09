from pathlib import Path
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from dashboard.paths import bash_path, ostwin_home, ostwin_path


def test_ostwin_home_prefers_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "install"))

    assert ostwin_home() == tmp_path / "install"
    assert ostwin_path(".env") == tmp_path / "install" / ".env"


def test_bash_path_converts_windows_path_for_wsl():
    with patch("dashboard.paths.os.name", "nt"), patch(
        "dashboard.paths.shutil.which",
        return_value=r"C:\Windows\system32\bash.exe",
    ):
        assert bash_path(r"E:\os-twin\.agents\mcp\mcp-extension.sh") == (
            "/mnt/e/os-twin/.agents/mcp/mcp-extension.sh"
        )


def test_bash_path_leaves_existing_bash_path_on_windows():
    with patch("dashboard.paths.os.name", "nt"):
        assert bash_path("/mnt/e/os-twin/.agents") == "/mnt/e/os-twin/.agents"


def test_bash_path_converts_windows_path_for_git_bash():
    with patch("dashboard.paths.os.name", "nt"), patch(
        "dashboard.paths.shutil.which",
        return_value=r"C:\Program Files\Git\bin\bash.exe",
    ):
        assert bash_path(r"E:\os-twin\.agents\mcp\mcp-extension.sh") == (
            "/e/os-twin/.agents/mcp/mcp-extension.sh"
        )


def test_mcp_script_command_exports_env_inside_bash(tmp_path, monkeypatch):
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OSTWIN_PROJECT_DIR", str(tmp_path / "project"))
    sys.modules.pop("dashboard.routes.mcp", None)

    from dashboard.routes import mcp

    cmd, env = mcp._build_script_command(["sync"])

    assert cmd[:2] == ["bash", "-c"]
    assert "export OSTWIN_HOME=" in cmd[2]
    assert "export AGENT_DIR=" in cmd[2]
    assert "export PROJECT_DIR=" in cmd[2]
    assert "exec " in cmd[2]
    assert "sync" in cmd[2]
    assert env["PROJECT_DIR"] == bash_path(tmp_path / "project")


def test_mcp_script_command_quotes_paths_with_spaces(tmp_path, monkeypatch):
    path_with_spaces = tmp_path / "my project" / "has spaces"
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECT_DIR", str(path_with_spaces))
    sys.modules.pop("dashboard.routes.mcp", None)

    from dashboard.routes import mcp

    cmd, env = mcp._build_script_command(["install", "my-package"])

    assert cmd[:2] == ["bash", "-c"]
    bash_command = cmd[2]
    assert "export OSTWIN_HOME=" in bash_command
    assert "export PROJECT_DIR=" in bash_command
    assert "exec" in bash_command
    assert "'" in bash_command  # shlex.quote uses single quotes


def test_run_script_uses_build_script_command(tmp_path, monkeypatch):
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path / "project"))
    sys.modules.pop("dashboard.routes.mcp", None)

    from dashboard.routes import mcp

    cmd, env = mcp._build_script_command(["list"])

    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_process

        result = asyncio.run(mcp._run_script(["list"]))

        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        assert call_args[0][0] == "bash"
        assert call_args[0][1] == "-c"
        assert "export OSTWIN_HOME=" in call_args[0][2]
        assert "env" in call_args[1]
        assert "PROJECT_DIR" in call_args[1]["env"]


def test_mcp_project_dir_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("OSTWIN_HOME", str(tmp_path / "home"))
    sys.modules.pop("dashboard.routes.mcp", None)
    sys.modules.pop("dashboard.api_utils", None)

    from dashboard.routes import mcp
    from dashboard.api_utils import PROJECT_ROOT

    assert mcp._mcp_project_dir() == PROJECT_ROOT

    monkeypatch.setenv("OSTWIN_PROJECT_DIR", str(tmp_path / "ostwin-project"))
    sys.modules.pop("dashboard.routes.mcp", None)
    from dashboard.routes import mcp as mcp2

    assert mcp2._mcp_project_dir() == tmp_path / "ostwin-project"

    monkeypatch.setenv("PROJECT_DIR", str(tmp_path / "direct-project"))
    sys.modules.pop("dashboard.routes.mcp", None)
    from dashboard.routes import mcp as mcp3

    assert mcp3._mcp_project_dir() == tmp_path / "direct-project"
