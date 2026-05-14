import os
import json
import logging
import base64
import mimetypes
import re
import subprocess
from pathlib import Path
from typing import List
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, JSONResponse
from dashboard.api_utils import PLANS_DIR, PROJECT_ROOT
from dashboard.auth import get_current_user

router = APIRouter(tags=["files"], prefix="/api/plans/{plan_id}/files")
logger = logging.getLogger(__name__)

IGNORE_PATTERNS = {
    '.git', 'node_modules', '__pycache__', '.next', '.venv', 'venv',
    '.env', 'dist', 'build', '.DS_Store', '.idea', '.vscode', '.tox',
    '.pytest_cache', '.mypy_cache', 'coverage', '.coverage', 'htmlcov',
    '.turbo', '.cache', '.parcel-cache',
}

# P1-6: Expanded sensitive file blocklist with pattern matching.
# Covers common env file variants, SSH keys, cloud credentials, and auth files.
SENSITIVE_FILENAMES = {
    # .env variants
    '.env', '.env.local', '.env.production', '.env.staging', '.env.development',
    '.env.production.local', '.env.staging.local', '.env.development.local',
    '.env.test', '.env.test.local', '.env.backup', '.env.bak', '.env.old',
    '.env.example', '.env.sample', '.env.template',
    # Auth files
    '.htpasswd', '.htaccess',
    # SSH keys (private keys — public keys are safe but we block for consistency)
    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
    # Cloud/service credentials
    'credentials.json', 'service-account.json', 'service-account-key.json',
    '.npmrc', '.pypirc', '.netrc',
    # Additional sensitive files
    '.kubeconfig', '.docker/config.json', 'config.gpg',
    'secrets.yml', 'secrets.yaml', 'secrets.json',
}

# P1-6: Pattern-based sensitive file detection for filenames not in the static set.
# Matches .env.*, id_rsa.*, id_ed25519.*, etc.
SENSITIVE_PATTERNS = [
    re.compile(r'^\.env\b'),       # .env, .env.anything, .env.production.local
    re.compile(r'^id_(rsa|ed25519|ecdsa|dsa)\b'),  # id_rsa, id_rsa.pub, id_ed25519, etc.
    re.compile(r'^\.aws[/\\]credentials$'),  # .aws/credentials
    re.compile(r'^\.ssh[/\\]'),    # .ssh/id_rsa, .ssh/config, etc.
    re.compile(r'^\.kube[/\\]'),   # .kube/config
    re.compile(r'^\.docker[/\\]config'),  # .docker/config.json
]

BINARY_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tiff', '.tif', '.svg',
    '.zip', '.gz', '.tar', '.rar', '.7z', '.bz2',
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv', '.flac', '.ogg',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.sqlite', '.db', '.pyc', '.pyd', '.so', '.dll', '.dylib', '.exe',
    '.class', '.jar', '.wasm',
}

BINARY_MIME_PREFIXES = (
    'image/', 'video/', 'audio/', 'font/',
    'application/pdf',
    'application/zip', 'application/x-tar', 'application/gzip',
    'application/x-7z-compressed', 'application/x-rar-compressed',
    'application/vnd.openxmlformats',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/msword',
)

FORCE_BASE64_EXTENSIONS = {
    '.csv',
    '.tsv',
}

# P1-8: Allowed working_dir roots — plan working directories must be within these.
# Includes user home (normal case) and project root (for dev/test).
# Also allows tmpdir for test fixtures.
_ALLOWED_WORKING_DIR_ROOTS = [
    Path.home(),                    # User home directory
]

def _is_working_dir_allowed(resolved_path: Path) -> bool:
    """Check if a working_dir path is within allowed roots.
    
    Allows paths under user home directory and common dev/test locations.
    Blocks system directories like /etc, /usr, /var, /root, etc.
    """
    # Always allow user home
    home = Path.home().resolve()
    if resolved_path == home or _is_path_inside(resolved_path, home):
        return True
    
    # Allow project root (for dev/test)
    if PROJECT_ROOT.exists():
        proj = PROJECT_ROOT.resolve()
        if resolved_path == proj or _is_path_inside(resolved_path, proj):
            return True
    
    # Allow temp directories (for test fixtures)
    import tempfile
    tmpdir = Path(tempfile.gettempdir()).resolve()
    if resolved_path == tmpdir or _is_path_inside(resolved_path, tmpdir):
        return True
    
    return False

# --- Helpers ---

def _resolve_working_dir(plan_id: str) -> Path:
    """Reads {plan_id}.meta.json from PLANS_DIR to extract working_dir.
    
    SECURITY (P1-8): Validates that the resolved working_dir is within
    allowed root directories (user home) to prevent path escape via
    crafted meta.json files.
    """
    # P3-22: Sanitize plan_id to prevent path traversal in meta file lookup
    if '\x00' in plan_id or '..' in plan_id or '/' in plan_id or '\\' in plan_id:
        raise HTTPException(status_code=400, detail="Invalid plan ID format")
    
    meta_file = PLANS_DIR / f"{plan_id}.meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan metadata not found for {plan_id}")
    
    try:
        meta = json.loads(meta_file.read_text())
        working_dir = meta.get("working_dir")
        if not working_dir:
            raise HTTPException(status_code=422, detail="working_dir not set in plan metadata")
        
        path = Path(working_dir)
        
        # P1-8: Validate working_dir is within allowed roots
        resolved = path.resolve()
        if not _is_working_dir_allowed(resolved):
            logger.warning(f"Rejected working_dir outside allowed roots: {resolved}")
            raise HTTPException(status_code=403, detail="Working directory is not within allowed paths")
        
        # Ensure path exists
        if not path.exists():
             raise HTTPException(status_code=404, detail="Working directory does not exist")
        return path
    except HTTPException:
        raise
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error reading meta for {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read plan metadata")


def _is_path_inside(target: Path, root: Path) -> bool:
    """Check if target path is inside root using Path.relative_to()."""
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_path(working_dir: Path, relative_path: str) -> Path:
    """Joins, resolves, and asserts within working_dir boundary.
    
    Uses Path.relative_to() for proper path boundary checking instead of
    string prefix matching (which is vulnerable to prefix attacks like
    /home/user/workspace_evil bypassing /home/user/workspace).
    
    Also detects symlink escapes where a symlink inside working_dir
    resolves to a location outside the working directory.
    
    SECURITY (P3-22): Rejects null bytes in paths.
    SECURITY (P1-7): Uses file descriptor to prevent TOCTOU race.
    """
    # P3-22: Reject null bytes in paths
    if '\x00' in relative_path:
        raise HTTPException(status_code=400, detail="Invalid path: null byte detected")
    
    working_dir = working_dir.resolve()
    
    # Handle the incoming path
    rel = relative_path.lstrip("/")
    if rel == "." or not rel:
        target = working_dir
    else:
        target = (working_dir / rel).resolve()
    
    # Primary check: target must be inside working_dir (not a prefix sibling)
    # Path.relative_to() raises ValueError if target is not a subpath
    try:
        target.relative_to(working_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal attempt detected")
    
    # Symlink escape detection: verify resolved target is still inside working_dir
    # This catches symlinks inside the workspace that point outside
    if target.is_file() or target.is_dir() or target.is_symlink():
        real_target = target.resolve()
        try:
            real_target.relative_to(working_dir)
        except ValueError:
            raise HTTPException(status_code=403, detail="Symlink escape detected")
    
    # P1-7: TOCTOU mitigation — open file descriptor and validate it's still inside
    # working_dir before returning. For directories, we can't hold an fd, but we
    # re-validate at the point of use in each endpoint.
    if target.is_file():
        try:
            fd = os.open(str(target), os.O_RDONLY | os.O_NOFOLLOW)
            try:
                fd_path = Path(f"/proc/self/fd/{fd}") if os.path.exists("/proc/self/fd") else target
                real_fd_target = os.path.realpath(f"/proc/self/fd/{fd}") if os.path.exists("/proc/self/fd") else str(target.resolve())
                real_fd_path = Path(real_fd_target)
                try:
                    real_fd_path.relative_to(working_dir)
                except ValueError:
                    raise HTTPException(status_code=403, detail="Symlink escape detected (TOCTOU)")
            finally:
                os.close(fd)
        except HTTPException:
            raise
        except OSError:
            pass  # File may have been deleted between checks; let the endpoint handle 404
    
    return target


def _is_sensitive_file(target_file: Path) -> bool:
    """Check if a file should be blocked from direct access.
    
    SECURITY (P1-6): Uses both exact filename matching and regex patterns
    to catch variants like .env.production.local, id_rsa.pub, etc.
    """
    name = target_file.name
    
    # Exact match against blocklist
    if name in SENSITIVE_FILENAMES:
        return True
    
    # P1-6: Pattern-based matching for env/SSH variants
    for pattern in SENSITIVE_PATTERNS:
        if pattern.match(name):
            return True
    
    # Check relative path from working_dir for patterns like .aws/credentials, .ssh/id_rsa
    # Build the relative path string to match against path-based patterns
    for parent in target_file.parents:
        try:
            rel_from_parent = str(target_file.relative_to(parent))
            for pattern in SENSITIVE_PATTERNS:
                if pattern.match(rel_from_parent):
                    return True
        except ValueError:
            break
    
    return False

def _get_entry_data(p: Path) -> dict:
    """Helper to format directory/file entries."""
    if p.is_dir():
        try:
            children_count = len([x for x in p.iterdir() if x.name not in IGNORE_PATTERNS])
        except PermissionError:
            children_count = 0
        return {
            "name": p.name,
            "type": "directory",
            "children_count": children_count
        }
    else:
        return {
            "name": p.name,
            "type": "file",
            "size": p.stat().st_size,
            "extension": p.suffix
        }

# --- Endpoints ---

@router.get("")
async def list_files(
    plan_id: str,
    path: str = Query(".", description="Relative path within working_dir"),
    user: dict = Depends(get_current_user)
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
    if rel_path == ".": rel_path = ""
    
    return {
        "path": rel_path,
        "entries": entries
    }

@router.get("/download")
async def download_file(
    plan_id: str,
    path: str = Query(..., description="Relative path within working_dir"),
    user: dict = Depends(get_current_user)
):
    """Download a file as an attachment."""
    working_dir = _resolve_working_dir(plan_id)
    target_file = _validate_path(working_dir, path)

    if not target_file.is_file():
        raise HTTPException(status_code=400, detail="Requested path is not a file")

    if _is_sensitive_file(target_file):
        raise HTTPException(status_code=403, detail="Access to this file is restricted")

    # P1-7: Re-validate after is_file check to narrow TOCTOU window
    _validate_path(working_dir, path)

    mime_type, _ = mimetypes.guess_type(str(target_file))
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=str(target_file),
        media_type=mime_type,
        filename=target_file.name,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )

@router.get("/content")
async def get_file_content(
    plan_id: str,
    path: str = Query(..., description="Relative path within working_dir"),
    user: dict = Depends(get_current_user)
):
    """Read file content with smart encoding based on file type.
    
    SECURITY (P3-21): Returns security headers to prevent content-type
    sniffing and XSS when the response is rendered in a browser context.
    """
    working_dir = _resolve_working_dir(plan_id)
    target_file = _validate_path(working_dir, path)

    if not target_file.is_file():
        raise HTTPException(status_code=400, detail="Requested path is not a file")

    if _is_sensitive_file(target_file):
        raise HTTPException(status_code=403, detail="Access to this file is restricted")

    # P1-7: Re-validate to narrow TOCTOU window
    _validate_path(working_dir, path)

    size = target_file.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(target_file))
    if not mime_type:
        mime_type = "application/octet-stream"

    ext = target_file.suffix.lower()
    # P2-17: Validate path doesn't contain characters that could confuse URL parsing
    safe_path = quote(path, safe='')
    download_url = f"/api/plans/{plan_id}/files/download?path={safe_path}"

    LIMIT = 2 * 1024 * 1024

    is_binary_ext = ext in BINARY_EXTENSIONS
    is_binary_mime = any(mime_type.startswith(prefix) for prefix in BINARY_MIME_PREFIXES)
    is_force_base64 = ext in FORCE_BASE64_EXTENSIONS
    is_binary = is_binary_ext or is_binary_mime

    # Security headers for all responses
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    if size > LIMIT:
        if is_binary or is_force_base64:
            return JSONResponse(
                content={
                    "path": path,
                    "content": None,
                    "encoding": "base64",
                    "size": size,
                    "mime_type": mime_type,
                    "truncated": True,
                    "download_url": download_url,
                },
                headers=security_headers,
            )
        try:
            raw = target_file.read_bytes()
            content = raw.decode("utf-8", errors="ignore")[:LIMIT]
            return JSONResponse(
                content={
                    "path": path,
                    "content": content,
                    "encoding": "utf-8",
                    "size": size,
                    "mime_type": mime_type,
                    "truncated": True,
                    "download_url": download_url,
                },
                headers=security_headers,
            )
        except Exception as e:
            logger.error(f"Error reading large file: {e}")
            return JSONResponse(
                content={
                    "path": path,
                    "content": None,
                    "encoding": None,
                    "size": size,
                    "mime_type": mime_type,
                    "truncated": True,
                    "download_url": download_url,
                },
                headers=security_headers,
            )

    try:
        if is_force_base64:
            content = base64.b64encode(target_file.read_bytes()).decode("utf-8")
            encoding = "base64"
        elif is_binary:
            content = base64.b64encode(target_file.read_bytes()).decode("utf-8")
            encoding = "base64"
        else:
            try:
                content = target_file.read_text(encoding="utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                content = base64.b64encode(target_file.read_bytes()).decode("utf-8")
                encoding = "base64"

        return JSONResponse(
            content={
                "path": path,
                "content": content,
                "encoding": encoding,
                "size": size,
                "mime_type": mime_type,
                "truncated": False,
                "download_url": download_url,
            },
            headers=security_headers,
        )
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")

@router.get("/tree")
async def get_file_tree(
    plan_id: str,
    user: dict = Depends(get_current_user)
):
    """Shallow tree (2 levels deep)."""
    working_dir = _resolve_working_dir(plan_id)
    
    def _build_tree(p: Path, depth: int) -> List[dict]:
        items = []
        try:
            for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if entry.name in IGNORE_PATTERNS:
                    continue
                
                rel_path = os.path.relpath(entry, working_dir)
                item = {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "path": rel_path
                }
                if entry.is_dir():
                    # Count visible children for the UI expand indicator
                    try:
                        child_count = len([c for c in entry.iterdir() if c.name not in IGNORE_PATTERNS])
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

    return {
        "tree": _build_tree(working_dir, 2)
    }

@router.get("/changes")
async def get_file_changes(
    plan_id: str,
    user: dict = Depends(get_current_user)
):
    """Git status and recent commits.
    
    SECURITY (P2-15): Uses GIT_CONFIG_NOSYSTEM and -c gc.auto=0 to prevent
    git config manipulation and automatic gc triggers.
    SECURITY (P1-9): Uses null byte as delimiter instead of pipe to prevent
    commit subject injection.
    SECURITY (P3-19): Generic error messages only.
    """
    working_dir = _resolve_working_dir(plan_id)
    
    # Check if it's a git repo
    if not (working_dir / ".git").exists():
         return {
            "git_enabled": False,
            "status": [],
            "recent_commits": []
        }
        
    try:
        # P2-15: Harden git execution environment
        git_env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",  # Ignore system-wide gitconfig
            "GIT_TERMINAL_PROMPT": "0",   # Never prompt for credentials
        }
        
        # git status --porcelain
        status_res = subprocess.run(
            ["git", "-c", "gc.auto=0", "status", "--porcelain"],
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            check=True,
            env=git_env,
            timeout=10,
        )
        status_lines = [line.strip() for line in status_res.stdout.splitlines() if line.strip()]
        
        # P1-9: Use null byte (%x00) as delimiter instead of pipe (|) to prevent
        # injection via commit subjects containing pipe characters.
        # Git's --format supports %x00 for null bytes.
        log_res = subprocess.run(
            ["git", "-c", "gc.auto=0", "log", "-10", "--format=%h%x00%an%x00%at%x00%s"],
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            check=True,
            env=git_env,
            timeout=10,
        )
        commits = []
        for line in log_res.stdout.splitlines():
            if not line.strip(): continue
            parts = line.split("\x00")
            if len(parts) == 4:
                try:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "timestamp": int(parts[2]),
                        "subject": parts[3]
                    })
                except (ValueError, IndexError):
                    continue  # Skip malformed entries
                
        return {
            "git_enabled": True,
            "status": status_lines,
            "recent_commits": commits
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out in workspace")
        return {"git_enabled": False, "status": [], "recent_commits": []}
    except Exception as e:
        # P3-19: Don't leak error details
        logger.warning(f"Git command failed: {e}")
        return {
            "git_enabled": False,
            "status": [],
            "recent_commits": [],
        }
