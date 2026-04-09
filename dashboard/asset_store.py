"""
Asset Store — persists uploaded content (images, files) to $PROJECT_DIR/assets/.

When users attach images during ideation, they are saved as real files so
that downstream agents can reference them in plans and war-rooms. The data URI
is decoded and written to disk; a stable file path is returned for storage
in the thread message (replacing the inline base64 blob).
"""

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from dashboard.api_utils import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Resolve assets root — always under the project
ASSETS_DIR = PROJECT_ROOT / "assets"


def _ensure_assets_dir(subdir: Optional[str] = None) -> Path:
    """Create and return the assets directory (optionally with a subdirectory)."""
    target = ASSETS_DIR / subdir if subdir else ASSETS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _data_uri_to_bytes(data_uri: str) -> tuple[bytes, str]:
    """Parse a data URI and return (raw_bytes, extension).

    Supports:  data:image/jpeg;base64,/9j/4AAQ...
    """
    m = re.match(r"data:([^;]+);base64,(.+)", data_uri, re.DOTALL)
    if not m:
        raise ValueError("Invalid data URI format")

    mime = m.group(1)       # e.g. "image/jpeg"
    b64_data = m.group(2)
    raw = base64.b64decode(b64_data)

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime, ".bin")
    return raw, ext


def persist_image(
    data_uri: str,
    original_name: str = "",
    thread_id: str = "",
) -> dict:
    """Save a data-URI image to disk and return asset metadata.

    Args:
        data_uri: The full data:image/...;base64,... string.
        original_name: Original filename from the user (used for display).
        thread_id: Thread ID for namespacing (stored under assets/threads/<id>/).

    Returns:
        dict with:
          - path: relative path from PROJECT_ROOT (e.g. "assets/threads/pt-abc/img-a1b2.jpg")
          - url:  absolute file path for serving
          - name: original filename
          - type: MIME type
          - size: file size in bytes
    """
    raw_bytes, ext = _data_uri_to_bytes(data_uri)

    # Content-hash the first 4 bytes for a short unique name
    digest = hashlib.sha256(raw_bytes).hexdigest()[:8]

    # Derive a clean filename
    if original_name:
        stem = Path(original_name).stem
        # Sanitize: only alphanumeric, dash, underscore
        stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:40]
        filename = f"{stem}-{digest}{ext}"
    else:
        filename = f"img-{digest}{ext}"

    # Namespace by thread
    subdir = f"threads/{thread_id}" if thread_id else "uploads"
    target_dir = _ensure_assets_dir(subdir)
    file_path = target_dir / filename

    # Write (skip if identical file already exists)
    if not file_path.exists():
        file_path.write_bytes(raw_bytes)
        logger.info("Persisted asset: %s (%d bytes)", file_path, len(raw_bytes))
    else:
        logger.debug("Asset already exists: %s", file_path)

    # Return relative path from project root
    rel_path = str(file_path.relative_to(PROJECT_ROOT))

    # Determine MIME from extension
    mime_map = {".jpg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    mime = mime_map.get(ext, "application/octet-stream")

    return {
        "path": rel_path,
        "url": str(file_path),
        "name": original_name or filename,
        "type": mime,
        "size": len(raw_bytes),
    }


def persist_images_from_message(
    images: list[dict],
    thread_id: str = "",
) -> list[dict]:
    """Persist all images from a message, replacing data URIs with file paths.

    Each image dict is expected to have {url, name, type}.
    Returns a new list where `url` is replaced with the file path,
    and a `data_uri` key is added for the LLM multimodal call.

    Args:
        images: List of {url: "data:image/...", name: "...", type: "..."}.
        thread_id: Thread ID for asset namespacing.

    Returns:
        List of {url: "data:...", path: "assets/...", name: "...", type: "...", size: N}.
    """
    result = []
    for img in images:
        data_uri = img.get("url", "")
        if not data_uri.startswith("data:"):
            # Already a file path or URL — pass through
            result.append(img)
            continue

        try:
            asset = persist_image(
                data_uri=data_uri,
                original_name=img.get("name", ""),
                thread_id=thread_id,
            )
            # Keep the data_uri for the LLM call, but store the path for persistence
            result.append({
                "url": data_uri,          # kept for multimodal LLM calls
                "path": asset["path"],    # on-disk location
                "name": asset["name"],
                "type": asset["type"],
                "size": asset["size"],
            })
        except Exception as e:
            logger.error("Failed to persist image %s: %s", img.get("name", "?"), e)
            result.append(img)  # fallback: keep original

    return result


def list_thread_assets(thread_id: str) -> list[dict]:
    """List all persisted assets for a given thread.

    Returns:
        List of {path, name, type, size} for each file.
    """
    target_dir = ASSETS_DIR / "threads" / thread_id
    if not target_dir.exists():
        return []

    assets = []
    for f in sorted(target_dir.iterdir()):
        if f.is_file():
            ext = f.suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
            assets.append({
                "path": str(f.relative_to(PROJECT_ROOT)),
                "name": f.name,
                "type": mime_map.get(ext, "application/octet-stream"),
                "size": f.stat().st_size,
            })
    return assets
