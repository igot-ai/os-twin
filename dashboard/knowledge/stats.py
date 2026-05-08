"""Per-namespace stats computation with caching (EPIC-005).

Provides lazy computation of:
- disk_bytes: Actual disk usage of the namespace directory
- query_count_24h: Query count in last 24 hours (from audit log)
- ingest_count_24h: Ingestion count in last 24 hours (from import records)

Cache TTL: 60 seconds by default (configurable via OSTWIN_KNOWLEDGE_STATS_CACHE_TTL).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache TTL in seconds
STATS_CACHE_TTL: float = float(os.environ.get("OSTWIN_KNOWLEDGE_STATS_CACHE_TTL", "60.0"))


class NamespaceStatsComputer:
    """Computes per-namespace stats with caching.

    Stats are computed lazily and cached for STATS_CACHE_TTL seconds.
    Thread-safe: uses locks to prevent concurrent computation for the same namespace.
    """

    def __init__(self, cache_ttl: float = STATS_CACHE_TTL) -> None:
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}  # namespace -> (timestamp, stats)
        self._lock = threading.Lock()

    def get_stats(self, namespace: str, namespace_dir: Path) -> dict[str, Any]:
        """Get stats for a namespace, using cache if fresh.

        Args:
            namespace: Namespace identifier
            namespace_dir: Path to the namespace directory

        Returns:
            Dict with: disk_bytes, query_count_24h, ingest_count_24h
        """
        now = time.monotonic()

        with self._lock:
            cached = self._cache.get(namespace)
            if cached is not None:
                timestamp, stats = cached
                if now - timestamp < self._cache_ttl:
                    return stats

        # Cache miss or expired - compute
        stats = self._compute_stats(namespace, namespace_dir)

        with self._lock:
            self._cache[namespace] = (now, stats)

        return stats

    def _compute_stats(self, namespace: str, namespace_dir: Path) -> dict[str, Any]:
        """Compute all stats for a namespace."""
        return {
            "disk_bytes": self._compute_disk_bytes(namespace_dir),
            "query_count_24h": self._compute_query_count_24h(namespace),
            "ingest_count_24h": self._compute_ingest_count_24h(namespace_dir),
        }

    def _compute_disk_bytes(self, namespace_dir: Path) -> int:
        """Compute actual disk usage in bytes.

        Uses `du -sb` on POSIX systems, falls back to recursive sum on Windows.
        """
        if not namespace_dir.exists():
            return 0

        try:
            # Try du command (fastest on POSIX)
            result = subprocess.run(
                ["du", "-sb", str(namespace_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Output format: "123456\t/path/to/dir"
                parts = result.stdout.strip().split("\t")
                if parts:
                    return int(parts[0])
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            logger.debug("du command failed for %s: %s", namespace_dir, exc)

        # Fallback: recursive sum (slower but portable)
        try:
            return self._recursive_disk_usage(namespace_dir)
        except OSError as exc:
            logger.warning("Failed to compute disk usage for %s: %s", namespace_dir, exc)
            return 0

    def _recursive_disk_usage(self, path: Path) -> int:
        """Recursively compute disk usage (fallback method)."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def _compute_query_count_24h(self, namespace: str) -> int:
        """Count queries in last 24 hours from audit log."""
        try:
            from dashboard.knowledge.audit import get_audit_log_path  # noqa: WPS433

            audit_file = get_audit_log_path()
            if not audit_file.exists():
                return 0

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            count = 0

            with open(audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        import json

                        entry = json.loads(line)
                        if entry.get("namespace") != namespace:
                            continue
                        if entry.get("op") != "query":
                            continue
                        timestamp_str = entry.get("timestamp", "")
                        if timestamp_str:
                            try:
                                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                if timestamp >= cutoff:
                                    count += 1
                            except ValueError:
                                pass
                    except json.JSONDecodeError:
                        continue

            return count
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to count queries for %s: %s", namespace, exc)
            return 0

    def _compute_ingest_count_24h(self, namespace_dir: Path) -> int:
        """Count ingestions in last 24 hours from manifest import records."""
        manifest_path = namespace_dir / "manifest.json"
        if not manifest_path.exists():
            return 0

        try:
            import json

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            imports = manifest.get("imports", [])
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            count = 0

            for imp in imports:
                started_at_str = imp.get("started_at", "")
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                        if started_at >= cutoff:
                            count += 1
                    except ValueError:
                        pass

            return count
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to count ingests for %s: %s", namespace_dir, exc)
            return 0

    def invalidate(self, namespace: str) -> None:
        """Invalidate cached stats for a namespace."""
        with self._lock:
            self._cache.pop(namespace, None)

    def invalidate_all(self) -> None:
        """Invalidate all cached stats."""
        with self._lock:
            self._cache.clear()


# Global singleton
_stats_computer: Optional[NamespaceStatsComputer] = None
_stats_computer_lock = threading.Lock()


def get_stats_computer() -> NamespaceStatsComputer:
    """Get the global stats computer singleton."""
    global _stats_computer
    if _stats_computer is not None:
        return _stats_computer
    with _stats_computer_lock:
        if _stats_computer is not None:
            return _stats_computer
        _stats_computer = NamespaceStatsComputer()
        return _stats_computer


__all__ = [
    "NamespaceStatsComputer",
    "get_stats_computer",
    "STATS_CACHE_TTL",
]
