"""Shared filesystem paths for dashboard runtime state."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def ostwin_home() -> Path:
    """Return the configured Ostwin install root."""
    configured = os.environ.get("OSTWIN_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".ostwin"


def ostwin_path(*parts: str) -> Path:
    """Return a path under the configured Ostwin install root."""
    return ostwin_home().joinpath(*parts)


def bash_path(path: str | os.PathLike[str]) -> str:
    """Convert a Windows path to the active bash path format when needed."""
    raw = str(path)
    if os.name != "nt":
        return raw

    normalized = raw.replace("/", "\\")
    if len(normalized) < 3 or normalized[1:3] != ":\\":
        return raw.replace("\\", "/")

    drive = normalized[0].lower()
    rest = normalized[3:].replace("\\", "/")
    bash_exe = (shutil.which("bash") or "").lower()
    if bash_exe.endswith("\\system32\\bash.exe"):
        return f"/mnt/{drive}/{rest}"
    return f"/{drive}/{rest}"
