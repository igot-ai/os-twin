"""Backup and restore for knowledge namespaces (EPIC-004).

Provides:
    - :func:`backup_namespace` — create a compressed archive of a namespace directory
    - :func:`restore_namespace` — extract an archive and recreate the namespace
    - CLI via ``python -m dashboard.knowledge.backup``

Archive format:
    - Uses Python's built-in ``tarfile`` module
    - Compression: zstd if available (via ``zstandard`` package), falls back to gzip
    - Integrity: SHA-256 checksum embedded as ``CHECKSUM.sha256`` in the archive root

Archive structure::

    {namespace}.tar.zst (or .tar.gz)
    └── {namespace}/
        ├── manifest.json
        ├── graph.db
        ├── vectors/
        │   └── ...
        └── CHECKSUM.sha256  (SHA-256 of manifest.json for integrity check)

Thread-safety:
    - Backup reads files while holding the NamespaceManager lock briefly
    - Restore is atomic: temp extraction followed by os.replace
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from dashboard.knowledge.namespace import (
    NamespaceExistsError,
    NamespaceManager,
    NamespaceMeta,
    NamespaceNotFoundError,
)

if TYPE_CHECKING:  # pragma: no cover
    from dashboard.knowledge.service import KnowledgeService

logger = logging.getLogger(__name__)

# Attempt to import zstandard for better compression
try:
    import zstandard as zstd  # noqa: WPS433

    HAS_ZSTD = True
except ImportError:
    zstd = None  # type: ignore[assignment]
    HAS_ZSTD = False

# File name for embedded checksum in archive
CHECKSUM_FILE = "CHECKSUM.sha256"
MANIFEST_FILE = "manifest.json"


class BackupError(Exception):
    """Base class for backup/restore errors."""


class NamespaceBackupNotFoundError(BackupError):
    """Raised when the namespace to backup doesn't exist."""


class InvalidBackupArchiveError(BackupError):
    """Raised when the backup archive is corrupted or invalid."""


class BackupChecksumMismatchError(BackupError):
    """Raised when the backup archive fails integrity check."""


# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------


def _get_compression_suffix() -> str:
    """Return the file suffix for the compression mode."""
    return ".tar.zst" if HAS_ZSTD else ".tar.gz"


def _get_compression_mode() -> str:
    """Return the tarfile compression mode."""
    return "w:gz" if not HAS_ZSTD else ""  # Empty string for manual zstd handling


# ---------------------------------------------------------------------------
# Checksum helpers
# ---------------------------------------------------------------------------


def _compute_manifest_checksum(manifest_path: Path) -> str:
    """Compute SHA-256 checksum of the manifest file.

    Args:
        manifest_path: Path to manifest.json

    Returns:
        Hex-encoded SHA-256 checksum string
    """
    sha256 = hashlib.sha256()
    with manifest_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _write_checksum_file(checksum: str, target_dir: Path) -> None:
    """Write the checksum file to the target directory.

    Args:
        checksum: Hex-encoded SHA-256 checksum
        target_dir: Directory to write CHECKSUM_FILE to
    """
    checksum_path = target_dir / CHECKSUM_FILE
    checksum_path.write_text(f"{checksum}  {MANIFEST_FILE}\n", encoding="utf-8")


def _read_checksum_file(archive_dir: Path) -> Optional[str]:
    """Read and parse the checksum file from an extracted archive.

    Args:
        archive_dir: Root directory of extracted archive

    Returns:
        The checksum string, or None if file doesn't exist
    """
    checksum_path = archive_dir / CHECKSUM_FILE
    if not checksum_path.exists():
        return None
    content = checksum_path.read_text(encoding="utf-8").strip()
    # Format: "{checksum}  {filename}"
    parts = content.split()
    return parts[0] if parts else None


# ---------------------------------------------------------------------------
# Backup implementation
# ---------------------------------------------------------------------------


def backup_namespace(
    name: str,
    dest_path: Optional[Path] = None,
    namespace_manager: Optional[NamespaceManager] = None,
) -> Path:
    """Create a compressed archive of a knowledge namespace.

    The archive contains all namespace data (manifest, graph.db, vectors/)
    plus a SHA-256 checksum file for integrity verification on restore.

    Args:
        name: Namespace identifier to backup
        dest_path: Destination path for the archive. If None, creates the
            archive in the current working directory with the name
            ``{name}.tar.zst`` (or ``.tar.gz`` if zstd unavailable).
        namespace_manager: Optional NamespaceManager instance (for testing).
            If None, creates a default one.

    Returns:
        Path to the created archive file.

    Raises:
        NamespaceBackupNotFoundError: If the namespace doesn't exist.
        BackupError: If backup creation fails.
    """
    nm = namespace_manager or NamespaceManager()
    
    # Verify namespace exists
    meta = nm.get(name)
    if meta is None:
        raise NamespaceBackupNotFoundError(f"Namespace {name!r} not found")
    
    ns_dir = nm.namespace_dir(name)
    if not ns_dir.exists():
        raise NamespaceBackupNotFoundError(f"Namespace directory {ns_dir} not found")
    
    # Determine output path
    suffix = _get_compression_suffix()
    if dest_path is None:
        dest_path = Path.cwd() / f"{name}{suffix}"
    else:
        dest_path = Path(dest_path)
        # Add suffix if not present
        if not str(dest_path).endswith((".tar.zst", ".tar.gz", ".tgz")):
            dest_path = dest_path.with_suffix(suffix)
    
    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Compute manifest checksum for integrity
    manifest_path = nm.manifest_path(name)
    if manifest_path.exists():
        checksum = _compute_manifest_checksum(manifest_path)
    else:
        checksum = "no_manifest"
        logger.warning("Namespace %s has no manifest.json, using placeholder checksum", name)
    
    logger.info("Backing up namespace %r to %s", name, dest_path)
    
    if HAS_ZSTD:
        _backup_with_zstd(name, ns_dir, dest_path, checksum)
    else:
        _backup_with_gzip(name, ns_dir, dest_path, checksum)
    
    logger.info("Backup complete: %s (%.2f MB)", dest_path, dest_path.stat().st_size / 1024 / 1024)
    return dest_path


def _backup_with_zstd(name: str, ns_dir: Path, dest_path: Path, checksum: str) -> None:
    """Create backup using zstd compression (better compression ratio)."""
    # Create uncompressed tar in temp location first
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
        tmp_tar_path = Path(tmp_tar.name)
    
    try:
        # Create tar archive
        with tarfile.open(tmp_tar_path, "w") as tar:
            # Add all files from namespace directory under the namespace name
            for item in ns_dir.iterdir():
                # Skip any temp/lock files
                if item.name.startswith(".") and not item.name.startswith(".manifest"):
                    continue
                tar.add(item, arcname=f"{name}/{item.name}")
            
            # Add checksum file
            with tempfile.TemporaryDirectory() as tmpdir:
                checksum_file = Path(tmpdir) / CHECKSUM_FILE
                checksum_file.write_text(f"{checksum}  {MANIFEST_FILE}\n", encoding="utf-8")
                tar.add(checksum_file, arcname=f"{name}/{CHECKSUM_FILE}")
        
        # Compress with zstd
        cctx = zstd.ZstdCompressor(level=3)  # Level 3 is fast with good compression
        with tmp_tar_path.open("rb") as f_in:
            with dest_path.open("wb") as f_out:
                cctx.copy_stream(f_in, f_out)
    finally:
        if tmp_tar_path.exists():
            tmp_tar_path.unlink()


def _backup_with_gzip(name: str, ns_dir: Path, dest_path: Path, checksum: str) -> None:
    """Create backup using gzip compression (fallback, no extra deps)."""
    with tarfile.open(dest_path, "w:gz") as tar:
        # Add all files from namespace directory
        for item in ns_dir.iterdir():
            if item.name.startswith(".") and not item.name.startswith(".manifest"):
                continue
            tar.add(item, arcname=f"{name}/{item.name}")
        
        # Add checksum file
        with tempfile.TemporaryDirectory() as tmpdir:
            checksum_file = Path(tmpdir) / CHECKSUM_FILE
            checksum_file.write_text(f"{checksum}  {MANIFEST_FILE}\n", encoding="utf-8")
            tar.add(checksum_file, arcname=f"{name}/{CHECKSUM_FILE}")


# ---------------------------------------------------------------------------
# Restore implementation
# ---------------------------------------------------------------------------


def restore_namespace(
    archive_path: Path,
    name: Optional[str] = None,
    namespace_manager: Optional[NamespaceManager] = None,
    knowledge_service: Optional["KnowledgeService"] = None,
    overwrite: bool = False,
) -> NamespaceMeta:
    """Restore a namespace from a backup archive.

    Args:
        archive_path: Path to the backup archive file.
        name: Target namespace name. If None, uses the namespace name from
            the archive. If provided and different from archive's namespace,
            restores to the new name.
        namespace_manager: Optional NamespaceManager instance (for testing).
        knowledge_service: Optional KnowledgeService for cache eviction.
        overwrite: If True, allows overwriting an existing namespace.
            Default False raises NamespaceExistsError.

    Returns:
        The restored NamespaceMeta.

    Raises:
        NamespaceExistsError: If the target namespace already exists and
            overwrite=False.
        InvalidBackupArchiveError: If the archive format is invalid.
        BackupChecksumMismatchError: If integrity check fails.
        BackupError: If restore fails.
    """
    nm = namespace_manager or NamespaceManager()
    archive_path = Path(archive_path)
    
    if not archive_path.exists():
        raise BackupError(f"Archive not found: {archive_path}")
    
    logger.info("Restoring namespace from %s", archive_path)
    
    # Extract to temp directory first
    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir)
        
        # Extract archive
        _extract_archive(archive_path, extract_dir)
        
        # Find namespace directory in archive
        ns_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if len(ns_dirs) != 1:
            raise InvalidBackupArchiveError(
                f"Expected exactly one namespace directory in archive, found {len(ns_dirs)}"
            )
        
        archive_ns_dir = ns_dirs[0]
        archive_ns_name = archive_ns_dir.name
        
        # Determine target namespace name
        target_name = name or archive_ns_name
        nm._require_valid_id(target_name)  # noqa: SLF001
        
        # Check for existing namespace
        if nm.get(target_name) is not None:
            if not overwrite:
                raise NamespaceExistsError(
                    f"Namespace {target_name!r} already exists. Use overwrite=True or specify a different name."
                )
            # Evict caches before deletion
            if knowledge_service is not None:
                knowledge_service._evict_namespace_caches(target_name)  # noqa: SLF001
            nm.delete(target_name)
        
        # Verify integrity
        _verify_integrity(archive_ns_dir, target_name)
        
        # Move to final location
        target_dir = nm.namespace_dir(target_name)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic move
        shutil.move(str(archive_ns_dir), str(target_dir))
        
        # Update manifest with new name if different
        if name is not None and name != archive_ns_name:
            manifest_path = target_dir / MANIFEST_FILE
            if manifest_path.exists():
                manifest_data = json.loads(manifest_path.read_text())
                manifest_data["name"] = target_name
                manifest_path.write_text(json.dumps(manifest_data, indent=2, default=str))
        
        # Load and return manifest
        meta = nm.get(target_name)
        if meta is None:
            raise BackupError(f"Failed to load restored manifest for {target_name!r}")
        
        logger.info("Restored namespace %r successfully", target_name)
        return meta


def _extract_archive(archive_path: Path, dest_dir: Path) -> None:
    """Extract a backup archive to destination directory."""
    suffix = archive_path.suffix.lower()
    
    if suffix == ".zst" or str(archive_path).endswith(".tar.zst"):
        if not HAS_ZSTD:
            raise BackupError(
                "Archive uses zstd compression but zstandard package is not installed. "
                "Install it with: pip install zstandard"
            )
        # Decompress zstd first
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
            tmp_tar_path = Path(tmp_tar.name)
        
        try:
            dctx = zstd.ZstdDecompressor()
            with archive_path.open("rb") as f_in:
                with tmp_tar_path.open("wb") as f_out:
                    dctx.copy_stream(f_in, f_out)
            
            # Extract tar
            with tarfile.open(tmp_tar_path, "r") as tar:
                tar.extractall(dest_dir)
        finally:
            if tmp_tar_path.exists():
                tmp_tar_path.unlink()
    else:
        # Assume gzip or plain tar
        mode = "r:gz" if suffix in (".gz", ".tgz") else "r"
        with tarfile.open(archive_path, mode) as tar:
            tar.extractall(dest_dir)


def _verify_integrity(ns_dir: Path, target_name: str) -> None:
    """Verify the integrity of extracted namespace files.
    
    Checks:
    1. manifest.json exists
    2. SHA-256 checksum matches (if CHECKSUM.sha256 present)
    """
    manifest_path = ns_dir / MANIFEST_FILE
    if not manifest_path.exists():
        raise InvalidBackupArchiveError(
            f"Archive missing {MANIFEST_FILE}; not a valid knowledge backup"
        )
    
    # Verify checksum if present
    expected_checksum = _read_checksum_file(ns_dir)
    if expected_checksum is not None:
        actual_checksum = _compute_manifest_checksum(manifest_path)
        if actual_checksum != expected_checksum:
            raise BackupChecksumMismatchError(
                f"Checksum mismatch for {target_name}: "
                f"expected {expected_checksum[:16]}..., got {actual_checksum[:16]}..."
            )
        logger.debug("Checksum verified for %s", target_name)
    else:
        logger.warning("No checksum file in archive for %s, skipping integrity check", target_name)


# ---------------------------------------------------------------------------
# Additional utilities
# ---------------------------------------------------------------------------


def list_backup_contents(archive_path: Path) -> dict:
    """List the contents of a backup archive without extracting.
    
    Args:
        archive_path: Path to the backup archive.
    
    Returns:
        Dict with keys: namespace, files, size_bytes, compression
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise BackupError(f"Archive not found: {archive_path}")
    
    suffix = archive_path.suffix.lower()
    compression = "zstd" if suffix == ".zst" or str(archive_path).endswith(".tar.zst") else "gzip"
    
    files = []
    namespace = None
    size_bytes = archive_path.stat().st_size
    
    # Extract to temp dir just to list contents
    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir)
        _extract_archive(archive_path, extract_dir)
        
        for item in extract_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(extract_dir)
                files.append(str(rel_path))
        
        # Find namespace name (first-level directory)
        first_level_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if first_level_dirs:
            namespace = first_level_dirs[0].name
    
    return {
        "namespace": namespace,
        "files": files,
        "file_count": len(files),
        "size_bytes": size_bytes,
        "compression": compression,
    }


__all__ = [
    "BackupError",
    "BackupChecksumMismatchError",
    "InvalidBackupArchiveError",
    "NamespaceBackupNotFoundError",
    "backup_namespace",
    "restore_namespace",
    "list_backup_contents",
]


# ---------------------------------------------------------------------------
# CLI entry point (python -m dashboard.knowledge.backup)
# ---------------------------------------------------------------------------


def _cli_backup(args) -> int:
    """Handle 'backup' subcommand."""
    from dashboard.knowledge.namespace import NamespaceManager
    
    nm = NamespaceManager()
    
    # Verify namespace exists
    meta = nm.get(args.namespace)
    if meta is None:
        print(f"Error: Namespace {args.namespace!r} not found", file=__import__("sys").stderr)
        return 1
    
    try:
        dest = Path(args.dest) if args.dest else None
        archive_path = backup_namespace(args.namespace, dest_path=dest, namespace_manager=nm)
        print(f"Backup created: {archive_path}")
        print(f"Size: {archive_path.stat().st_size / 1024 / 1024:.2f} MB")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        return 1


def _cli_restore(args) -> int:
    """Handle 'restore' subcommand."""
    from dashboard.knowledge.namespace import NamespaceManager
    
    archive_path = Path(args.archive)
    if not archive_path.exists():
        print(f"Error: Archive not found: {archive_path}", file=__import__("sys").stderr)
        return 1
    
    try:
        nm = NamespaceManager()
        meta = restore_namespace(
            archive_path,
            name=args.as_name,
            namespace_manager=nm,
            overwrite=args.overwrite,
        )
        print(f"Restored namespace: {meta.name}")
        print(f"Created: {meta.created_at}")
        print(f"Stats: {meta.stats.files_indexed} files, {meta.stats.chunks} chunks")
        return 0
    except NamespaceExistsError as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        print("Use --overwrite to replace existing namespace, or --as to specify a different name")
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        return 1


def _cli_list(args) -> int:
    """Handle 'list' subcommand."""
    archive_path = Path(args.archive)
    if not archive_path.exists():
        print(f"Error: Archive not found: {archive_path}", file=__import__("sys").stderr)
        return 1
    
    try:
        info = list_backup_contents(archive_path)
        print(f"Archive: {archive_path}")
        print(f"Namespace: {info['namespace']}")
        print(f"Compression: {info['compression']}")
        print(f"Size: {info['size_bytes'] / 1024 / 1024:.2f} MB")
        print(f"Files: {info['file_count']}")
        if args.verbose:
            print("\nContents:")
            for f in sorted(info["files"]):
                print(f"  {f}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for backup/restore operations.
    
    Usage:
        python -m dashboard.knowledge.backup backup <namespace> [--dest PATH]
        python -m dashboard.knowledge.backup restore <archive> [--as NAME] [--overwrite]
        python -m dashboard.knowledge.backup list <archive> [-v]
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        prog="dashboard.knowledge.backup",
        description="Backup and restore knowledge namespaces",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # backup subcommand
    backup_parser = subparsers.add_parser(
        "backup", help="Create a backup of a namespace"
    )
    backup_parser.add_argument("namespace", help="Namespace to backup")
    backup_parser.add_argument(
        "--dest", "-d",
        help="Destination path for the archive (default: current directory)"
    )
    backup_parser.set_defaults(func=_cli_backup)
    
    # restore subcommand
    restore_parser = subparsers.add_parser(
        "restore", help="Restore a namespace from a backup archive"
    )
    restore_parser.add_argument("archive", help="Path to the backup archive")
    restore_parser.add_argument(
        "--as", "-a", dest="as_name",
        help="Restore to a different namespace name"
    )
    restore_parser.add_argument(
        "--overwrite", "-f",
        action="store_true",
        help="Overwrite existing namespace"
    )
    restore_parser.set_defaults(func=_cli_restore)
    
    # list subcommand
    list_parser = subparsers.add_parser(
        "list", help="List contents of a backup archive"
    )
    list_parser.add_argument("archive", help="Path to the backup archive")
    list_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show all files in archive"
    )
    list_parser.set_defaults(func=_cli_list)
    
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    import sys
    sys.exit(main())
