import os
import json
import logging
import base64
import mimetypes
import subprocess
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from dashboard.api_utils import PLANS_DIR, read_json_utf8
from dashboard.auth import get_current_user

router = APIRouter(tags=["files"], prefix="/api/plans/{plan_id}/files")
logger = logging.getLogger(__name__)

IGNORE_PATTERNS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".next",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".DS_Store",
    ".idea",
    ".vscode",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    "coverage",
    ".coverage",
    "htmlcov",
    ".turbo",
    ".cache",
    ".parcel-cache",
}

# --- Helpers ---


def _resolve_working_dir(plan_id: str) -> Path:
    """Reads {plan_id}.meta.json from PLANS_DIR to extract working_dir."""
    meta_file = PLANS_DIR / f"{plan_id}.meta.json"
    if not meta_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Plan metadata not found for {plan_id}"
        )

    try:
        meta = read_json_utf8(meta_file)
        working_dir = meta.get("working_dir")
        if not working_dir:
            raise HTTPException(
                status_code=422, detail="working_dir not set in plan metadata"
            )

        path = Path(working_dir)
        # Ensure path exists
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Working directory {working_dir} does not exist",
            )
        return path
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error reading meta for {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read plan metadata")


def _validate_path(working_dir: Path, relative_path: str) -> Path:
    """Joins, resolves, and asserts within working_dir boundary."""
    # Ensure working_dir is absolute and resolved
    working_dir = working_dir.resolve()

    # Handle the incoming path
    rel = relative_path.lstrip("/")
    if rel == "." or not rel:
        target = working_dir
    else:
        target = (working_dir / rel).resolve()

    # Security check: must start with working_dir
    if not str(target).startswith(str(working_dir)):
        raise HTTPException(status_code=403, detail="Path traversal attempt detected")

    return target


def _get_entry_data(p: Path) -> dict:
    """Helper to format directory/file entries."""
    if p.is_dir():
        try:
            children_count = len(
                [x for x in p.iterdir() if x.name not in IGNORE_PATTERNS]
            )
        except PermissionError:
            children_count = 0
        return {"name": p.name, "type": "directory", "children_count": children_count}
    else:
        return {
            "name": p.name,
            "type": "file",
            "size": p.stat().st_size,
            "extension": p.suffix,
        }


# --- Endpoints ---


@router.get("")
async def list_files(
    plan_id: str,
    path: str = Query(".", description="Relative path within working_dir"),
    user: dict = Depends(get_current_user),
):
    """List entries (files + dirs) in a directory."""
    working_dir = _resolve_working_dir(plan_id)
    target_dir = _validate_path(working_dir, path)

    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Requested path is not a directory")

    entries = []
    try:
        for p in target_dir.iterdir():
            if p.name in IGNORE_PATTERNS:
                continue
            entries.append(_get_entry_data(p))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Sorted: dirs first, then alpha
    entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

    # Calculate relative path for response
    rel_path = os.path.relpath(target_dir, working_dir)
    if rel_path == ".":
        rel_path = ""

    return {"path": rel_path, "entries": entries}


@router.get("/content")
async def get_file_content(
    plan_id: str,
    path: str = Query(..., description="Relative path within working_dir"),
    user: dict = Depends(get_current_user),
):
    """Read file content."""
    working_dir = _resolve_working_dir(plan_id)
    target_file = _validate_path(working_dir, path)

    if not target_file.is_file():
        raise HTTPException(status_code=400, detail="Requested path is not a file")

    size = target_file.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(target_file))
    if not mime_type:
        mime_type = "application/octet-stream"

    # 2 MB limit
    LIMIT = 2 * 1024 * 1024
    if size > LIMIT:
        return {
            "path": path,
            "content": None,
            "encoding": None,
            "size": size,
            "mime_type": mime_type,
            "truncated": True,
        }

    try:
        # Try reading as UTF-8
        try:
            content = target_file.read_text(encoding="utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            # Fallback to base64 for binary
            content = base64.b64encode(target_file.read_bytes()).decode("utf-8")
            encoding = "base64"

        return {
            "path": path,
            "content": content,
            "encoding": encoding,
            "size": size,
            "mime_type": mime_type,
            "truncated": False,
        }
    except Exception as e:
        logger.error(f"Error reading file {target_file}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.get("/tree")
async def get_file_tree(plan_id: str, user: dict = Depends(get_current_user)):
    """Shallow tree (2 levels deep)."""
    working_dir = _resolve_working_dir(plan_id)

    def _build_tree(p: Path, depth: int) -> List[dict]:
        items = []
        try:
            for entry in sorted(
                p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
            ):
                if entry.name in IGNORE_PATTERNS:
                    continue

                rel_path = os.path.relpath(entry, working_dir)
                item = {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "path": rel_path,
                }
                if entry.is_dir():
                    # Count visible children for the UI expand indicator
                    try:
                        child_count = len(
                            [
                                c
                                for c in entry.iterdir()
                                if c.name not in IGNORE_PATTERNS
                            ]
                        )
                    except PermissionError:
                        child_count = 0
                    item["children_count"] = child_count

                    if depth > 1:
                        # Still within budget — recurse
                        item["children"] = _build_tree(entry, depth - 1)
                    # else: omit "children" key entirely → frontend will lazy-fetch
                else:
                    item["size"] = entry.stat().st_size
                    item["extension"] = entry.suffix
                items.append(item)
        except PermissionError:
            pass
        return items

    return {"tree": _build_tree(working_dir, 2)}


@router.get("/changes")
async def get_file_changes(plan_id: str, user: dict = Depends(get_current_user)):
    """Git status and recent commits."""
    working_dir = _resolve_working_dir(plan_id)

    # Check if it's a git repo
    if not (working_dir / ".git").exists():
        return {"git_enabled": False, "status": [], "recent_commits": []}

    try:
        # git status --porcelain
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        status_lines = [
            line.strip() for line in status_res.stdout.splitlines() if line.strip()
        ]

        # git log -10 --format="%h|%an|%at|%s"
        log_res = subprocess.run(
            ["git", "log", "-10", "--format=%h|%an|%at|%s"],
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        commits = []
        for line in log_res.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) == 4:
                commits.append(
                    {
                        "hash": parts[0],
                        "author": parts[1],
                        "timestamp": int(parts[2]),
                        "subject": parts[3],
                    }
                )

        return {"git_enabled": True, "status": status_lines, "recent_commits": commits}
    except Exception as e:
        logger.warning(f"Git command failed in {working_dir}: {e}")
        return {
            "git_enabled": False,
            "status": [],
            "recent_commits": [],
            "error": str(e),
        }
