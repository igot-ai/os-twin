"""Tests for knowledge backup/restore functionality (EPIC-004).

Coverage:
- backup_namespace: creates archive, includes all files, computes checksum
- restore_namespace: extracts archive, recreates namespace, verifies integrity
- CLI: backup and restore commands work
- Round-trip: backup -> restore produces identical namespace
- Cross-compatibility: gzip fallback when zstd unavailable
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from dashboard.knowledge.backup import (
    BackupError,
    BackupChecksumMismatchError,
    InvalidBackupArchiveError,
    NamespaceBackupNotFoundError,
    backup_namespace,
    restore_namespace,
    list_backup_contents,
    main as backup_cli,
    _compute_manifest_checksum,
    _get_compression_suffix,
    HAS_ZSTD,
)
from dashboard.knowledge.namespace import (
    NamespaceManager,
    NamespaceMeta,
    NamespaceExistsError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_knowledge_dir(tmp_path: Path) -> Path:
    """Create a temporary knowledge directory."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    return knowledge_dir


@pytest.fixture
def namespace_manager(temp_knowledge_dir: Path) -> NamespaceManager:
    """Create a NamespaceManager with a temp directory."""
    return NamespaceManager(base_dir=temp_knowledge_dir)


@pytest.fixture
def populated_namespace(namespace_manager: NamespaceManager) -> str:
    """Create a namespace with some files for testing."""
    ns_name = "test-backup"
    namespace_manager.create(ns_name, description="Test namespace for backup")
    
    # Add some fake data files
    ns_dir = namespace_manager.namespace_dir(ns_name)
    
    # Create a fake vector directory
    vectors_dir = ns_dir / "vectors"
    vectors_dir.mkdir(exist_ok=True)
    (vectors_dir / "index.bin").write_bytes(b"\x00\x01\x02\x03" * 100)
    
    # Create a fake graph database
    (ns_dir / "graph.db").write_bytes(b"fake graph data")
    
    # Update stats
    namespace_manager.update_stats(ns_name, files_indexed=5, chunks=100, vectors=100)
    
    return ns_name


# ---------------------------------------------------------------------------
# Basic backup tests
# ---------------------------------------------------------------------------


def test_backup_namespace_creates_archive(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that backup_namespace creates an archive file."""
    dest = tmp_path / "backup"
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=dest,
        namespace_manager=namespace_manager,
    )
    
    assert archive_path.exists()
    assert archive_path.suffix in (".zst", ".gz")


def test_backup_namespace_includes_all_files(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that backup includes manifest, vectors, and graph.db."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Extract and check contents
    with tempfile.TemporaryDirectory() as extract_dir:
        # Handle zstd vs gzip
        if str(archive_path).endswith(".zst"):
            # Need to decompress zstd first
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                with archive_path.open("rb") as f_in:
                    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
                        dctx.copy_stream(f_in, tmp_tar)
                        tmp_tar_path = Path(tmp_tar.name)
                
                with tarfile.open(tmp_tar_path, "r") as tar:
                    tar.extractall(extract_dir)
                
                tmp_tar_path.unlink()
            except ImportError:
                pytest.skip("zstandard package required for .tar.zst archives")
        else:
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(extract_dir)
        
        extracted = Path(extract_dir) / populated_namespace
        
        # Check manifest exists
        assert (extracted / "manifest.json").exists()
        
        # Check vectors directory
        assert (extracted / "vectors").is_dir()
        assert (extracted / "vectors" / "index.bin").exists()
        
        # Check graph.db
        assert (extracted / "graph.db").exists()
        
        # Check checksum file
        assert (extracted / "CHECKSUM.sha256").exists()


def test_backup_namespace_includes_checksum(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that backup includes SHA-256 checksum of manifest."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Extract and verify checksum
    with tempfile.TemporaryDirectory() as extract_dir:
        # Handle zstd vs gzip
        if str(archive_path).endswith(".zst"):
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                with archive_path.open("rb") as f_in:
                    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
                        dctx.copy_stream(f_in, tmp_tar)
                        tmp_tar_path = Path(tmp_tar.name)
                
                with tarfile.open(tmp_tar_path, "r") as tar:
                    tar.extractall(extract_dir)
                
                tmp_tar_path.unlink()
            except ImportError:
                pytest.skip("zstandard package required for .tar.zst archives")
        else:
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(extract_dir)
        
        extracted = Path(extract_dir) / populated_namespace
        
        # Read checksum file
        checksum_file = extracted / "CHECKSUM.sha256"
        assert checksum_file.exists()
        
        content = checksum_file.read_text()
        assert "manifest.json" in content
        
        # Verify it's a valid SHA-256 hex string
        checksum = content.split()[0]
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)


def test_backup_nonexistent_namespace_raises(
    namespace_manager: NamespaceManager,
    tmp_path: Path,
):
    """Test that backing up a non-existent namespace raises an error."""
    with pytest.raises(NamespaceBackupNotFoundError):
        backup_namespace(
            "nonexistent",
            dest_path=tmp_path / "backup",
            namespace_manager=namespace_manager,
        )


# ---------------------------------------------------------------------------
# Restore tests
# ---------------------------------------------------------------------------


def test_restore_namespace_recreates_namespace(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that restore creates a namespace from an archive."""
    # Create backup
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Delete original namespace
    namespace_manager.delete(populated_namespace)
    assert namespace_manager.get(populated_namespace) is None
    
    # Restore
    meta = restore_namespace(
        archive_path,
        namespace_manager=namespace_manager,
    )
    
    assert meta.name == populated_namespace
    assert namespace_manager.get(populated_namespace) is not None


def test_restore_with_different_name(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test restoring to a different namespace name."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    new_name = "restored-copy"
    meta = restore_namespace(
        archive_path,
        name=new_name,
        namespace_manager=namespace_manager,
    )
    
    assert meta.name == new_name
    assert namespace_manager.get(new_name) is not None
    # Original should still exist
    assert namespace_manager.get(populated_namespace) is not None


def test_restore_existing_namespace_fails(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that restoring over an existing namespace fails without overwrite."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    with pytest.raises(NamespaceExistsError):
        restore_namespace(
            archive_path,
            namespace_manager=namespace_manager,
        )


def test_restore_with_overwrite(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that restore with overwrite=True replaces existing namespace."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Modify the original namespace
    namespace_manager.update_stats(populated_namespace, chunks=999)
    
    # Restore with overwrite
    meta = restore_namespace(
        archive_path,
        namespace_manager=namespace_manager,
        overwrite=True,
    )
    
    # Stats should be from backup (100 chunks)
    assert meta.stats.chunks == 100


def test_restore_invalid_archive_raises(
    namespace_manager: NamespaceManager,
    tmp_path: Path,
):
    """Test that restoring an invalid archive raises an error."""
    # Create a fake archive without manifest
    fake_archive = tmp_path / "fake.tar.gz"
    with tarfile.open(fake_archive, "w:gz") as tar:
        # Add a random file
        fake_file = tmp_path / "random.txt"
        fake_file.write_text("not a valid backup")
        tar.add(fake_file, arcname="random.txt")
    
    with pytest.raises(InvalidBackupArchiveError):
        restore_namespace(
            fake_archive,
            namespace_manager=namespace_manager,
        )


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_backup_restore_roundtrip_preserves_data(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that backup -> restore preserves all data."""
    # Get original manifest
    original_meta = namespace_manager.get(populated_namespace)
    assert original_meta is not None
    
    # Backup
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Delete and restore
    namespace_manager.delete(populated_namespace)
    restored_meta = restore_namespace(
        archive_path,
        namespace_manager=namespace_manager,
    )
    
    # Compare key fields
    assert restored_meta.name == original_meta.name
    assert restored_meta.stats.files_indexed == original_meta.stats.files_indexed
    assert restored_meta.stats.chunks == original_meta.stats.chunks
    assert restored_meta.stats.vectors == original_meta.stats.vectors
    assert restored_meta.embedding_model == original_meta.embedding_model


def test_backup_restore_idempotent(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that restoring the same archive twice produces equivalent namespaces."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Restore first copy
    meta1 = restore_namespace(
        archive_path,
        name="restore-1",
        namespace_manager=namespace_manager,
    )
    
    # Restore second copy
    meta2 = restore_namespace(
        archive_path,
        name="restore-2",
        namespace_manager=namespace_manager,
    )
    
    # Both should have same stats
    assert meta1.stats.chunks == meta2.stats.chunks
    assert meta1.stats.vectors == meta2.stats.vectors


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_backup(namespace_manager: NamespaceManager, populated_namespace: str, tmp_path: Path):
    """Test CLI backup command."""
    import sys
    
    dest = tmp_path / "backup.tar.gz"
    
    with patch.object(sys, "argv", [
        "dashboard.knowledge.backup",
        "backup",
        populated_namespace,
        "--dest", str(dest),
    ]):
        with patch("dashboard.knowledge.backup.NamespaceManager", return_value=namespace_manager):
            exit_code = backup_cli()
    
    assert exit_code == 0
    assert dest.exists() or dest.with_suffix(".tar.zst").exists()


def test_cli_restore(namespace_manager: NamespaceManager, populated_namespace: str, tmp_path: Path, capsys):
    """Test CLI restore command."""
    import sys
    
    # Create backup
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    # Restore via CLI with overwrite
    with patch.object(sys, "argv", [
        "dashboard.knowledge.backup",
        "restore",
        str(archive_path),
        "--overwrite",
    ]):
        with patch("dashboard.knowledge.backup.NamespaceManager", return_value=namespace_manager):
            exit_code = backup_cli()
    
    # Check exit code and output
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Restored namespace:" in captured.out


def test_cli_list(namespace_manager: NamespaceManager, populated_namespace: str, tmp_path: Path):
    """Test CLI list command."""
    import sys
    
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    with patch.object(sys, "argv", [
        "dashboard.knowledge.backup",
        "list",
        str(archive_path),
        "-v",
    ]):
        exit_code = backup_cli()
    
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------


def test_list_backup_contents(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test list_backup_contents utility."""
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    info = list_backup_contents(archive_path)
    
    assert info["namespace"] == populated_namespace
    assert info["file_count"] > 0
    assert info["size_bytes"] > 0
    assert info["compression"] in ("zstd", "gzip")


def test_compute_manifest_checksum(namespace_manager: NamespaceManager, populated_namespace: str):
    """Test manifest checksum computation."""
    manifest_path = namespace_manager.manifest_path(populated_namespace)
    
    checksum = _compute_manifest_checksum(manifest_path)
    
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


def test_compression_suffix():
    """Test that compression suffix is correct."""
    suffix = _get_compression_suffix()
    
    if HAS_ZSTD:
        assert suffix == ".tar.zst"
    else:
        assert suffix == ".tar.gz"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


def test_backup_empty_namespace(namespace_manager: NamespaceManager, tmp_path: Path):
    """Test backing up an empty namespace (no files except manifest)."""
    ns_name = "empty-ns"
    namespace_manager.create(ns_name)
    
    archive_path = backup_namespace(
        ns_name,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    assert archive_path.exists()


def test_backup_size_reasonable(
    namespace_manager: NamespaceManager,
    populated_namespace: str,
    tmp_path: Path,
):
    """Test that backup size is reasonable (< 200% of source)."""
    ns_dir = namespace_manager.namespace_dir(populated_namespace)
    
    # Calculate source size
    source_size = sum(f.stat().st_size for f in ns_dir.rglob("*") if f.is_file())
    
    archive_path = backup_namespace(
        populated_namespace,
        dest_path=tmp_path / "backup",
        namespace_manager=namespace_manager,
    )
    
    archive_size = archive_path.stat().st_size
    
    # Archive should be smaller than 200% of source (usually much smaller due to compression)
    assert archive_size < source_size * 2


def test_restore_missing_archive_raises(namespace_manager: NamespaceManager, tmp_path: Path):
    """Test that restoring from non-existent archive raises error."""
    with pytest.raises(BackupError, match="Archive not found"):
        restore_namespace(
            tmp_path / "nonexistent.tar.gz",
            namespace_manager=namespace_manager,
        )
