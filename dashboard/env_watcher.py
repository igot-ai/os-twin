"""
env_watcher — hot-reload ~/.ostwin/.env into os.environ without restart.

Two public entry-points:

* ``reload_env_file()`` — synchronous, immediate re-read.  Returns a dict
  describing what changed (added / changed / removed key names).
* ``watch_env_file()`` — async coroutine suitable for ``asyncio.create_task``.
  Polls the file's mtime every ``_POLL_INTERVAL`` seconds; on change it
  calls ``reload_env_file()`` and broadcasts an ``env_reloaded`` event to
  all connected WebSocket / SSE clients.

Design notes
~~~~~~~~~~~~
* Only keys **defined in the .env file** are managed.  Keys set by the
  shell, Docker, CI, etc. are never touched.
* Commented-out lines (``# KEY=value``) are treated as "removed from .env"
  — if we previously loaded that key, we clear it from ``os.environ``.
* ``DASHBOARD_PORT`` and ``DASHBOARD_HOST`` changes are logged as warnings
  because the listening socket can't be rebound at runtime.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

_ENV_FILE = Path.home() / ".ostwin" / ".env"
_POLL_INTERVAL = 3  # seconds

# Keys we previously loaded from .env — lets us detect removals.
_loaded_keys: Set[str] = set()

# Last observed mtime (float epoch seconds).
_last_mtime: float = 0.0

# Keys that require a full restart — we warn instead of silently updating.
_RESTART_REQUIRED_KEYS = frozenset({"DASHBOARD_PORT", "DASHBOARD_HOST"})


# ── Parsing ────────────────────────────────────────────────────────────


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file into {KEY: value} for enabled (uncommented) lines."""
    result: Dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            result[key] = value
    return result


# ── Reload ─────────────────────────────────────────────────────────────


def reload_env_file(
    path: Optional[Path] = None,
) -> Dict[str, list]:
    """Re-read the .env file and update ``os.environ`` accordingly.

    Returns ``{"added": [...], "changed": [...], "removed": [...]}``
    with the key names (never values) that were affected.
    """
    global _loaded_keys, _last_mtime

    env_path = path or _ENV_FILE
    new_vars = _parse_env_file(env_path)

    added: list[str] = []
    changed: list[str] = []
    removed: list[str] = []
    restart_needed: list[str] = []

    # Detect added / changed
    for key, value in new_vars.items():
        old = os.environ.get(key)
        if old is None:
            os.environ[key] = value
            added.append(key)
        elif old != value:
            os.environ[key] = value
            changed.append(key)
            if key in _RESTART_REQUIRED_KEYS:
                restart_needed.append(key)

    # Detect removed (was in _loaded_keys but no longer in file)
    for key in _loaded_keys - set(new_vars.keys()):
        if key in os.environ:
            del os.environ[key]
            removed.append(key)

    # Update tracking state
    _loaded_keys = set(new_vars.keys())
    try:
        if env_path.is_file():
            _last_mtime = env_path.stat().st_mtime
    except OSError:
        pass

    if restart_needed:
        logger.warning(
            "These keys changed but require a dashboard restart to take effect: %s",
            restart_needed,
        )

    return {"added": added, "changed": changed, "removed": removed}


# ── Async watcher ──────────────────────────────────────────────────────


async def watch_env_file() -> None:
    """Poll ``~/.ostwin/.env`` for mtime changes and hot-reload.

    Intended to be run as a long-lived ``asyncio.create_task`` alongside
    the existing ``poll_war_rooms`` coroutine.
    """
    global _last_mtime

    # Seed the initial state so the first real edit is detected as a diff.
    try:
        if _ENV_FILE.is_file():
            _last_mtime = _ENV_FILE.stat().st_mtime
            # Pre-populate _loaded_keys from current file
            initial = _parse_env_file(_ENV_FILE)
            _loaded_keys.update(initial.keys())
    except OSError:
        pass

    logger.info("env_watcher started — polling %s every %ss", _ENV_FILE, _POLL_INTERVAL)

    while True:
        try:
            await asyncio.sleep(_POLL_INTERVAL)

            if not _ENV_FILE.is_file():
                continue

            current_mtime = _ENV_FILE.stat().st_mtime
            if current_mtime == _last_mtime:
                continue

            # File changed — reload
            result = reload_env_file()

            all_changes = result["added"] + result["changed"] + result["removed"]
            if all_changes:
                logger.info(
                    "Reloaded .env: added=%s changed=%s removed=%s",
                    result["added"] or "[]",
                    result["changed"] or "[]",
                    result["removed"] or "[]",
                )

                # Broadcast to connected clients
                try:
                    import dashboard.global_state as gs

                    await gs.broadcaster.broadcast(
                        "env_reloaded",
                        {
                            "added": result["added"],
                            "changed": result["changed"],
                            "removed": result["removed"],
                        },
                    )
                except Exception as exc:
                    logger.debug("Failed to broadcast env_reloaded: %s", exc)
            else:
                logger.debug(".env mtime changed but no effective key changes")

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("env_watcher error: %s", exc, exc_info=True)
            await asyncio.sleep(_POLL_INTERVAL)
