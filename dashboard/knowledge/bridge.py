"""Memory ↔ Knowledge Bridge Index.

This module provides the BridgeIndex class that maintains a reverse index
from knowledge chunks to memory notes. It enables:
- "Show me all notes related to this document" (reverse lookup)
- "What knowledge backs this claim?" (forward lookup)

The index is SQLite-backed for O(1) lookups and is lazily rebuilt when
the memory store is modified (detected via stat-time comparison).

Environment Variables:
    OSTWIN_KNOWLEDGE_MEMORY_BRIDGE: Set to "1" to enable the bridge.
        Default is disabled ("0").

Storage:
    The bridge index is stored at ~/.ostwin/knowledge/_bridge.sqlite
    with a single table:
        CREATE TABLE backlinks (
            namespace TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            note_id TEXT NOT NULL,
            PRIMARY KEY (namespace, file_hash, chunk_idx, note_id)
        )
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def is_bridge_enabled() -> bool:
    """Check if the memory-knowledge bridge is enabled.
    
    Returns:
        True if OSTWIN_KNOWLEDGE_MEMORY_BRIDGE=1, False otherwise.
    """
    return os.getenv("OSTWIN_KNOWLEDGE_MEMORY_BRIDGE", "0") == "1"


@dataclass
class BridgeConfig:
    """Configuration for the bridge index.
    
    Attributes:
        bridge_db_path: Path to the SQLite database file
        memory_persist_dir: Path to the memory notes directory
        enabled: Whether the bridge is enabled
    """
    bridge_db_path: str = ""
    memory_persist_dir: str = ""
    enabled: bool = field(default_factory=is_bridge_enabled)
    
    @classmethod
    def from_env(cls) -> "BridgeConfig":
        """Create config from environment variables."""
        home = os.path.expanduser("~")
        ostwin_dir = os.path.join(home, ".ostwin")
        
        bridge_db_path = os.getenv(
            "OSTWIN_BRIDGE_DB_PATH",
            os.path.join(ostwin_dir, "knowledge", "_bridge.sqlite")
        )
        
        # Try to find memory persist dir
        memory_persist_dir = os.getenv(
            "MEMORY_PERSIST_DIR",
            os.path.join(ostwin_dir, ".memory")
        )
        
        return cls(
            bridge_db_path=bridge_db_path,
            memory_persist_dir=memory_persist_dir,
            enabled=is_bridge_enabled(),
        )


class BridgeIndex:
    """SQLite-backed reverse index from knowledge chunks to memory notes.
    
    The index maps (namespace, file_hash, chunk_idx) -> list[note_id]
    and supports efficient lookup of all notes that cite a given knowledge
    chunk.
    
    The index is lazily rebuilt when the memory store is modified (detected
    via stat-time comparison of the notes directory).
    """
    
    def __init__(self, config: Optional[BridgeConfig] = None):
        """Initialize the bridge index.
        
        Args:
            config: Optional configuration. If None, uses environment defaults.
        """
        self.config = config or BridgeConfig.from_env()
        self._conn: Optional[sqlite3.Connection] = None
        self._last_rebuild_time: float = 0.0
        self._memory_mtime: float = 0.0
        
        if self.config.enabled:
            self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Ensure the database exists and has the correct schema."""
        if not self.config.enabled:
            return
            
        db_path = self.config.bridge_db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS backlinks (
                namespace TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                chunk_idx INTEGER NOT NULL,
                note_id TEXT NOT NULL,
                PRIMARY KEY (namespace, file_hash, chunk_idx, note_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_backlinks_lookup
            ON backlinks (namespace, file_hash, chunk_idx)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_backlinks_file
            ON backlinks (namespace, file_hash)
        """)
        self._conn.commit()
        logger.info("Bridge index initialized at %s", db_path)
    
    def _get_memory_mtime(self) -> float:
        """Get the modification time of the memory notes directory.
        
        Returns the max mtime of any .md file in the notes directory,
        or 0 if the directory doesn't exist.
        """
        notes_dir = os.path.join(self.config.memory_persist_dir, "notes")
        if not os.path.isdir(notes_dir):
            return 0.0
        
        max_mtime = 0.0
        try:
            for root, _dirs, files in os.walk(notes_dir):
                for f in files:
                    if f.endswith(".md"):
                        path = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(path)
                            max_mtime = max(max_mtime, mtime)
                        except OSError:
                            pass
        except OSError:
            pass
        return max_mtime
    
    def needs_rebuild(self) -> bool:
        """Check if the index needs to be rebuilt.
        
        Returns True if:
        - The bridge is enabled
        - The memory notes directory has been modified since last rebuild
        - The index has never been built
        """
        if not self.config.enabled:
            return False
        
        current_mtime = self._get_memory_mtime()
        return current_mtime > self._memory_mtime
    
    def lookup(
        self,
        namespace: str,
        file_hash: str,
        chunk_idx: Optional[int] = None,
    ) -> list[str]:
        """Look up all notes that cite a given knowledge chunk.
        
        Args:
            namespace: The knowledge namespace
            file_hash: SHA256 hash of the source file
            chunk_idx: Optional chunk index. If None, returns notes for all chunks.
        
        Returns:
            List of note IDs that cite the specified chunk(s).
        """
        if not self.config.enabled or self._conn is None:
            return []
        
        # Check if we need to rebuild
        if self.needs_rebuild():
            logger.info("Bridge index stale, triggering rebuild")
            self.rebuild()
        
        try:
            if chunk_idx is not None:
                cursor = self._conn.execute(
                    "SELECT note_id FROM backlinks WHERE namespace=? AND file_hash=? AND chunk_idx=?",
                    (namespace, file_hash, chunk_idx)
                )
            else:
                cursor = self._conn.execute(
                    "SELECT DISTINCT note_id FROM backlinks WHERE namespace=? AND file_hash=?",
                    (namespace, file_hash)
                )
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("Bridge lookup failed: %s", e)
            return []
    
    def rebuild(self) -> dict:
        """Rebuild the entire index from memory notes.
        
        Scans all memory notes, extracts knowledge:// links, and populates
        the reverse index.
        
        Returns:
            Dict with 'notes_scanned', 'links_found', 'errors' counts.
        """
        if not self.config.enabled or self._conn is None:
            return {"error": "Bridge not enabled"}
        
        start_time = time.time()
        notes_scanned = 0
        links_found = 0
        errors = 0
        
        # Clear existing data
        self._conn.execute("DELETE FROM backlinks")
        
        # Scan notes directory
        notes_dir = os.path.join(self.config.memory_persist_dir, "notes")
        if not os.path.isdir(notes_dir):
            logger.warning("Memory notes directory not found: %s", notes_dir)
            self._conn.commit()
            return {"notes_scanned": 0, "links_found": 0, "errors": 0}
        
        # Parse all notes and extract knowledge links
        for root, _dirs, files in os.walk(notes_dir):
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                    
                filepath = os.path.join(root, filename)
                try:
                    note_links = self._extract_knowledge_links(filepath)
                    notes_scanned += 1
                    
                    for link_data in note_links:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO backlinks (namespace, file_hash, chunk_idx, note_id) VALUES (?, ?, ?, ?)",
                            (
                                link_data["namespace"],
                                link_data["file_hash"],
                                link_data["chunk_idx"],
                                link_data["note_id"],
                            )
                        )
                        links_found += 1
                        
                except Exception as e:
                    logger.warning("Failed to process %s: %s", filepath, e)
                    errors += 1
        
        self._conn.commit()
        
        # Update timestamps
        self._memory_mtime = self._get_memory_mtime()
        self._last_rebuild_time = time.time()
        
        elapsed = time.time() - start_time
        logger.info(
            "Bridge rebuild complete: %d notes, %d links, %d errors in %.2fs",
            notes_scanned,
            links_found,
            errors,
            elapsed,
        )
        
        return {
            "notes_scanned": notes_scanned,
            "links_found": links_found,
            "errors": errors,
            "elapsed_seconds": elapsed,
        }
    
    def _extract_knowledge_links(self, filepath: str) -> list[dict]:
        """Extract knowledge:// links from a memory note file.
        
        Uses the MemoryNote class for robust parsing of YAML frontmatter,
        including tolerance for unquoted string values in hand-written notes.
        
        Args:
            filepath: Path to the .md file
            
        Returns:
            List of dicts with namespace, file_hash, chunk_idx, note_id
        """
        results = []
        
        try:
            # Use MemoryNote.from_file for robust parsing
            from agentic_memory.memory_note import MemoryNote
            note = MemoryNote.from_file(filepath)
            
            # Extract knowledge links using the dedicated method
            knowledge_links = note.get_knowledge_links()
            
            for kl in knowledge_links:
                results.append({
                    "namespace": kl.namespace,
                    "file_hash": kl.file_hash,
                    "chunk_idx": kl.chunk_idx,
                    "note_id": note.id,
                })
        except Exception as e:
            logger.debug("Failed to parse note %s: %s", filepath, e)
        
        return results
    
    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self) -> "BridgeIndex":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# Singleton instance for convenience
_bridge_index: Optional[BridgeIndex] = None


def get_bridge_index() -> BridgeIndex:
    """Get the singleton BridgeIndex instance.
    
    Returns:
        The global BridgeIndex instance.
    """
    global _bridge_index
    if _bridge_index is None:
        _bridge_index = BridgeIndex()
    return _bridge_index


__all__ = [
    "BridgeConfig",
    "BridgeIndex",
    "is_bridge_enabled",
    "get_bridge_index",
]
