"""
deploy_preview.py — Local preview deploy support for completed plans.

Manages preview server lifecycle:
- Detects preview command from package.json or static fallback
- Finds free localhost port
- Starts/manages preview process
- Integrates with ngrok tunnel for public URL

State persisted to <working_dir>/.agents/deploy/preview.json
"""

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_START_PORT = 3000
MAX_PORT_ATTEMPTS = 100

PREVIEW_STATE_FILENAME = "preview.json"
PREVIEW_LOG_FILENAME = "preview.log"

STATIC_SEARCH_DIRS = ("", "dist", "build", "out", "public")
IGNORED_DIRS = frozenset({"node_modules", ".git", ".agents", ".next", "__pycache__", ".cache", "cache"})


class PathCheckError(Exception):
    """Raised when working directory path check fails."""
    pass


class PreviewConfigError(Exception):
    """Raised when preview cannot be configured."""
    pass


def resolve_working_dir(plan_id: str, plans_dir: Optional[Path] = None) -> Path:
    """Resolve working directory from plan meta.json.
    
    Args:
        plan_id: The plan ID to resolve
        plans_dir: Plans directory (defaults to global PLANS_DIR)
    
    Returns:
        Absolute Path to working directory
    
    Raises:
        FileNotFoundError: If plan or meta.json not found
        KeyError: If working_dir not in meta
    """
    from dashboard.api_utils import PLANS_DIR as DEFAULT_PLANS_DIR, PROJECT_ROOT
    
    plans = plans_dir or DEFAULT_PLANS_DIR
    meta_file = plans / f"{plan_id}.meta.json"
    
    if not meta_file.exists():
        raise FileNotFoundError(f"Plan meta not found: {meta_file}")
    
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    working_dir = meta.get("working_dir")
    
    if not working_dir:
        raise KeyError(f"working_dir not set in plan meta: {plan_id}")
    
    wd_path = Path(working_dir)
    
    if wd_path.is_absolute():
        return wd_path.resolve()
    
    wd_str = working_dir.replace("\\", "/").strip("./")
    
    if not wd_str or wd_str == ".":
        return PROJECT_ROOT.resolve()
    
    if wd_str.startswith("projects/"):
        return (PROJECT_ROOT / wd_str).resolve()
    
    return (PROJECT_ROOT / "projects" / wd_str).resolve()


def check_path_availability(path: Path) -> Dict[str, Any]:
    """Check if a path is suitable for preview deployment.
    
    Non-destructive: does not create any directories.
    Tests writability only on existing directories.
    
    Args:
        path: Directory path to check
    
    Returns:
        Dict with: ok, exists, is_file, writable, creatable, resolved_path, error
    """
    result = {
        "ok": False,
        "exists": False,
        "is_file": False,
        "writable": False,
        "creatable": False,
        "resolved_path": None,
        "error": None,
    }
    
    try:
        resolved = path.resolve()
        result["resolved_path"] = str(resolved)
        
        if resolved.exists():
            result["exists"] = True
            
            if resolved.is_file():
                result["is_file"] = True
                result["error"] = f"Path points to a file, not a directory: {resolved}"
                return result
            
            test_file = resolved / f".write_test_{os.getpid()}"
            try:
                test_file.touch()
                test_file.unlink()
                result["writable"] = True
                result["creatable"] = True
                result["ok"] = True
            except (OSError, PermissionError) as e:
                result["error"] = f"Directory not writable: {e}"
                return result
        else:
            current = resolved
            existing_ancestor = None
            
            while current != current.parent:
                if current.exists():
                    existing_ancestor = current
                    break
                current = current.parent
            
            if existing_ancestor is None:
                existing_ancestor = Path.cwd()
            
            if existing_ancestor.is_file():
                result["error"] = f"Ancestor path is a file: {existing_ancestor}"
                return result
            
            test_file = existing_ancestor / f".write_test_{os.getpid()}"
            try:
                test_file.touch()
                test_file.unlink()
                result["writable"] = True
                result["creatable"] = True
                result["ok"] = True
            except (OSError, PermissionError) as e:
                result["error"] = f"Cannot write to ancestor directory {existing_ancestor}: {e}"
                return result
    except Exception as e:
        result["error"] = str(e)
        return result
    
    return result


def _detect_package_manager(working_dir: Path) -> str:
    """Detect package manager from lockfiles.
    
    Order: pnpm-lock.yaml -> bun.lock/bun.lockb -> yarn.lock -> package-lock.json -> npm
    """
    if (working_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (working_dir / "bun.lock").exists() or (working_dir / "bun.lockb").exists():
        return "bun"
    if (working_dir / "yarn.lock").exists():
        return "yarn"
    if (working_dir / "package-lock.json").exists():
        return "npm"
    return "npm"


def _find_executable(name: str) -> Optional[str]:
    """Find executable path using shutil.which."""
    return shutil.which(name)


def _find_static_index_html(working_dir: Path) -> Optional[Path]:
    """Find index.html for static serving.
    
    Priority: root, dist, build, out, public, then filtered recursive search.
    Ignores node_modules, .git, .agents, .next, and cache folders.
    """
    for subdir in STATIC_SEARCH_DIRS:
        candidate = working_dir / subdir / "index.html" if subdir else working_dir / "index.html"
        if candidate.exists() and candidate.is_file():
            return candidate
    
    for candidate in _iter_html_files(working_dir):
        return candidate
    
    return None


def _iter_html_files(root: Path) -> List[Path]:
    """Iterate index.html files, ignoring common directories."""
    results = []
    try:
        for item in root.iterdir():
            if not item.is_dir():
                if item.name == "index.html":
                    results.append(item)
                continue
            
            if item.name.lower() in IGNORED_DIRS or item.name.startswith("."):
                continue
            
            results.extend(_iter_html_files(item))
    except (OSError, PermissionError):
        pass
    return results


def detect_preview_command(working_dir: Path) -> Tuple[Optional[str], str, Optional[List[str]]]:
    """Detect the preview command for a working directory.
    
    Detection order:
    1. package.json script "dev"
    2. package.json script "preview"
    3. package.json script "start"
    4. static index.html via python -m http.server
    5. None (not_configured)
    
    Args:
        working_dir: Project directory to scan
    
    Returns:
        Tuple of (command_string | None, detection_method, argv_list | None)
        detection_method is like: "pnpm:dev", "npm:preview", "yarn:start", "static:http.server", "not_configured"
    """
    package_json_path = working_dir / "package.json"
    
    if package_json_path.exists():
        try:
            pkg = json.loads(package_json_path.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            
            pm = _detect_package_manager(working_dir)
            
            for script_name in ("dev", "preview", "start"):
                if script_name in scripts:
                    detection_method = f"{pm}:{script_name}"
                    pm_exe = _find_executable(pm)
                    if pm_exe:
                        argv = [pm_exe, "run", script_name]
                        return f"{pm} run {script_name}", detection_method, argv
                    return f"{pm} run {script_name}", detection_method, None
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse package.json: {e}")
    
    index_html = _find_static_index_html(working_dir)
    if index_html:
        dir_path = index_html.parent
        rel_dir = dir_path.relative_to(working_dir) if dir_path != working_dir else Path(".")
        dir_str = str(rel_dir) if str(rel_dir) != "." else "."
        argv = [
            sys.executable,
            "-m", "http.server",
            "{port}",
            "--bind", "127.0.0.1",
            "--directory", dir_str,
        ]
        return f"{sys.executable} -m http.server {{port}} --bind 127.0.0.1 --directory {dir_str}", "static:http.server", argv
    
    return None, "not_configured", None


def find_free_port(start_port: int = DEFAULT_START_PORT, max_attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """Find a free localhost port starting from start_port.
    
    Args:
        start_port: Port to start scanning from
        max_attempts: Maximum number of ports to try
    
    Returns:
        First available port number
    
    Raises:
        OSError: If no free port found in range
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    
    raise OSError(f"No free port found in range {start_port}-{start_port + max_attempts - 1}")


def is_process_alive(pid: Optional[int]) -> bool:
    """Check if a process with given PID is still running.
    
    Args:
        pid: Process ID to check
    
    Returns:
        True if process is alive, False otherwise
    """
    if pid is None:
        return False
    
    try:
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                try:
                    exit_code = ctypes.c_ulong()
                    if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        return exit_code.value == STILL_ACTIVE
                finally:
                    kernel32.CloseHandle(handle)
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def get_preview_state_path(working_dir: Path) -> Path:
    """Get the path to preview state file."""
    return working_dir / ".agents" / "deploy" / PREVIEW_STATE_FILENAME


def get_preview_log_path(working_dir: Path) -> Path:
    """Get the path to preview log file."""
    return working_dir / ".agents" / "logs" / PREVIEW_LOG_FILENAME


def read_preview_state(working_dir: Path) -> Optional[Dict[str, Any]]:
    """Read preview state from disk.
    
    Args:
        working_dir: Project working directory
    
    Returns:
        Parsed state dict or None if not found
    """
    state_path = get_preview_state_path(working_dir)
    if not state_path.exists():
        return None
    
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read preview state: {e}")
        return None


def write_preview_state(working_dir: Path, state: Dict[str, Any]) -> None:
    """Persist preview state to disk.
    
    Args:
        working_dir: Project working directory
        state: State dict to persist
    """
    state_path = get_preview_state_path(working_dir)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def get_preview_status(working_dir: Path) -> Dict[str, Any]:
    """Get current preview status.
    
    Includes local_url and public_url (from tunnel) when available.
    
    Args:
        working_dir: Project working directory
    
    Returns:
        Status dict with keys: status, pid, port, local_url, public_url, 
        command, detection_method, started_at, updated_at, working_dir,
        log_file, error
    """
    state = read_preview_state(working_dir)
    log_path = get_preview_log_path(working_dir)
    
    result = {
        "status": "not_configured",
        "pid": None,
        "port": None,
        "local_url": None,
        "public_url": None,
        "command": None,
        "detection_method": None,
        "started_at": None,
        "updated_at": None,
        "working_dir": str(working_dir),
        "log_file": str(log_path) if log_path.parent.exists() else None,
        "error": None,
    }
    
    if not state:
        command, method, _ = detect_preview_command(working_dir)
        if command:
            result["command"] = command
            result["detection_method"] = method
            result["status"] = "stopped"
        else:
            result["detection_method"] = method
        return result
    
    result.update({
        "pid": state.get("pid"),
        "port": state.get("port"),
        "command": state.get("command"),
        "detection_method": state.get("detection_method"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "working_dir": state.get("working_dir", str(working_dir)),
        "log_file": state.get("log_file"),
        "error": state.get("error"),
    })
    
    pid = state.get("pid")
    port = state.get("port")
    
    if pid and is_process_alive(pid):
        result["status"] = "running"
        if port:
            result["local_url"] = f"http://127.0.0.1:{port}"
    else:
        result["status"] = "stopped"
        if pid is not None:
            result["pid"] = None
            state["pid"] = None
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_preview_state(working_dir, state)
    
    if result["status"] == "running":
        try:
            from dashboard import tunnel
            public_url = tunnel.get_tunnel_url()
            if public_url:
                result["public_url"] = public_url
        except ImportError:
            pass
    
    return result


def start_preview(working_dir: Path, port: Optional[int] = None) -> Dict[str, Any]:
    """Start a preview server for the working directory.
    
    Idempotent: if preview.json shows a running PID, returns existing status.
    
    Args:
        working_dir: Project working directory
        port: Optional specific port (auto-detected if None)
    
    Returns:
        Status dict (same as get_preview_status)
    
    Raises:
        PathCheckError: If working directory is invalid
        PreviewConfigError: If preview cannot be configured
        OSError: If no free port available
    """
    path_check = check_path_availability(working_dir)
    if not path_check["ok"]:
        raise PathCheckError(path_check["error"] or "Path check failed")
    
    existing_state = read_preview_state(working_dir)
    if existing_state:
        existing_pid = existing_state.get("pid")
        if existing_pid and is_process_alive(existing_pid):
            logger.info(f"Preview already running (PID {existing_pid}), returning status")
            return get_preview_status(working_dir)
    
    command, detection_method, argv_template = detect_preview_command(working_dir)
    if not command:
        raise PreviewConfigError(f"No preview command found (detection: {detection_method})")
    
    if port is None:
        port = find_free_port()
    
    log_path = get_preview_log_path(working_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    is_windows = platform.system() == "Windows"
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    proc = None
    
    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            if argv_template:
                argv = [arg.replace("{port}", str(port)) for arg in argv_template]
                
                if detection_method == "static:http.server":
                    proc = subprocess.Popen(
                        argv,
                        cwd=str(working_dir),
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
                        start_new_session=not is_windows,
                    )
                else:
                    proc = subprocess.Popen(
                        argv,
                        cwd=str(working_dir),
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        env=env,
                        shell=False,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
                        start_new_session=not is_windows,
                    )
            else:
                shell_cmd = command.replace("{port}", str(port))
                proc = subprocess.Popen(
                    shell_cmd,
                    cwd=str(working_dir),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
                    start_new_session=not is_windows,
                )
    except Exception as e:
        raise PreviewConfigError(f"Failed to start preview process: {e}")
    
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "pid": proc.pid,
        "port": port,
        "command": command,
        "detection_method": detection_method,
        "started_at": now,
        "updated_at": now,
        "working_dir": str(working_dir),
        "log_file": str(log_path),
        "error": None,
    }
    
    write_preview_state(working_dir, state)
    logger.info(f"Preview started (PID {proc.pid}) on port {port} for {working_dir}")
    
    return get_preview_status(working_dir)


def stop_preview(working_dir: Path) -> Dict[str, Any]:
    """Stop the preview server for the working directory.
    
    Args:
        working_dir: Project working directory
    
    Returns:
        Status dict after stopping
    """
    state = read_preview_state(working_dir)
    
    if not state:
        return get_preview_status(working_dir)
    
    pid = state.get("pid")
    if pid and is_process_alive(pid):
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
            else:
                try:
                    pgid = os.getpgid(pid)
                    import signal
                    os.killpg(pgid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    os.kill(pid, 9)
        except (OSError, subprocess.TimeoutExpired, ProcessLookupError) as e:
            logger.warning(f"Error stopping preview process {pid}: {e}")
    
    now = datetime.now(timezone.utc).isoformat()
    state["pid"] = None
    state["error"] = None
    state["updated_at"] = now
    write_preview_state(working_dir, state)
    
    logger.info(f"Preview stopped for {working_dir}")
    return get_preview_status(working_dir)


def restart_preview(working_dir: Path, port: Optional[int] = None) -> Dict[str, Any]:
    """Restart the preview server.
    
    Args:
        working_dir: Project working directory
        port: Optional specific port (reuses existing if None)
    
    Returns:
        Status dict after restart
    """
    state = read_preview_state(working_dir)
    
    if port is None and state:
        port = state.get("port")
    
    stop_preview(working_dir)
    
    return start_preview(working_dir, port)
