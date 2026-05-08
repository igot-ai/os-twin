"""Knowledge link parsing and validation for Memory ↔ Knowledge Bridge (EPIC-007).

This module provides utilities for parsing and validating `knowledge://` URIs
that appear in memory note links. The format is:

    knowledge://<namespace>/<file_hash>#<chunk_idx>

Example:
    knowledge://docs/abc123def456#0

Components:
- namespace: Knowledge namespace identifier (alphanumeric, underscores, dashes)
- file_hash: SHA256 hash of the source file (hex string)
- chunk_idx: Zero-based chunk index within the file

Validation:
- Namespace existence check (requires KnowledgeService)
- File hash resolution (requires NamespaceVectorStore)
- Chunk index bounds check
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Pattern for knowledge:// URIs
# Format: knowledge://<namespace>/<file_hash>#<chunk_idx>
# - namespace: alphanumeric, underscores, dashes (1-64 chars)
# - file_hash: hex string (typically SHA256 = 64 chars, but allow variable)
# - chunk_idx: non-negative integer
KNOWLEDGE_LINK_PATTERN = re.compile(
    r"^knowledge://"
    r"(?P<namespace>[a-zA-Z0-9_-]{1,64})"
    r"/"
    r"(?P<file_hash>[a-fA-F0-9]+)"
    r"#"
    r"(?P<chunk_idx>\d+)"
    r"$"
)


@dataclass(frozen=True)
class KnowledgeLink:
    """A parsed knowledge:// URI.

    Attributes:
        namespace: The knowledge namespace identifier
        file_hash: SHA256 hash of the source file
        chunk_idx: Zero-based chunk index within the file
        raw: The original URI string
    """

    namespace: str
    file_hash: str
    chunk_idx: int
    raw: str

    @classmethod
    def parse(cls, uri: str) -> Optional["KnowledgeLink"]:
        """Parse a knowledge:// URI string.

        Args:
            uri: The URI string to parse

        Returns:
            A KnowledgeLink instance if valid, None if invalid format
        """
        match = KNOWLEDGE_LINK_PATTERN.match(uri)
        if not match:
            return None

        return cls(
            namespace=match.group("namespace"),
            file_hash=match.group("file_hash"),
            chunk_idx=int(match.group("chunk_idx")),
            raw=uri,
        )

    def to_uri(self) -> str:
        """Convert this KnowledgeLink back to a URI string."""
        return f"knowledge://{self.namespace}/{self.file_hash}#{self.chunk_idx}"

    def validate(
        self,
        *,
        check_namespace: bool = True,
        check_file_hash: bool = True,
        check_chunk_idx: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Validate this knowledge link against the knowledge store.

        Args:
            check_namespace: Whether to verify namespace exists
            check_file_hash: Whether to verify file hash exists in namespace
            check_chunk_idx: Whether to verify chunk index is valid

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        try:
            # Lazy import to avoid circular dependencies
            from dashboard.knowledge.service import KnowledgeService
            from dashboard.knowledge.namespace import NamespaceNotFoundError

            service = KnowledgeService()

            if check_namespace:
                meta = service.get_namespace(self.namespace)
                if meta is None:
                    return False, f"Namespace '{self.namespace}' does not exist"

            if check_file_hash or check_chunk_idx:
                try:
                    # Get vector store to check file/chunk
                    vs = service._get_vector_store(self.namespace)
                    if vs is None:
                        return False, f"Could not access vector store for namespace '{self.namespace}'"

                    # Check if file hash exists using the available method
                    if check_file_hash:
                        has_file = vs.has_file_hash(self.file_hash)
                        if not has_file:
                            return False, f"File hash '{self.file_hash}' not found in namespace '{self.namespace}'"

                    # Check chunk index bounds
                    if check_chunk_idx:
                        chunk_count = vs.count_by_file_hash(self.file_hash)
                        if self.chunk_idx < 0 or self.chunk_idx >= chunk_count:
                            return False, (
                                f"Chunk index {self.chunk_idx} out of bounds "
                                f"(file has {chunk_count} chunks)"
                            )

                except NamespaceNotFoundError:
                    return False, f"Namespace '{self.namespace}' not found"
                except Exception as e:
                    logger.warning("Validation error: %s", e)
                    return False, f"Validation error: {e}"

            return True, None

        except Exception as e:
            logger.exception("Knowledge link validation failed")
            return False, f"Validation failed: {e}"


def is_knowledge_link(uri: str) -> bool:
    """Check if a string is a valid knowledge:// URI.

    Args:
        uri: The string to check

    Returns:
        True if the string matches the knowledge:// URI format
    """
    return KNOWLEDGE_LINK_PATTERN.match(uri) is not None


def parse_knowledge_links(uris: list[str]) -> list[KnowledgeLink]:
    """Parse all knowledge:// URIs from a list.

    Args:
        uris: List of URI strings (may contain non-knowledge URIs)

    Returns:
        List of parsed KnowledgeLink instances (non-knowledge URIs are skipped)
    """
    result = []
    for uri in uris:
        parsed = KnowledgeLink.parse(uri)
        if parsed is not None:
            result.append(parsed)
    return result


def categorize_links(uris: list[str]) -> dict[str, list[str]]:
    """Categorize URIs into memory IDs and knowledge links.

    Args:
        uris: List of URI strings

    Returns:
        Dict with:
        - "memory_ids": list of non-knowledge URIs (assumed to be memory note IDs)
        - "knowledge_links": list of knowledge:// URI strings
    """
    memory_ids = []
    knowledge_links = []

    for uri in uris:
        if is_knowledge_link(uri):
            knowledge_links.append(uri)
        else:
            memory_ids.append(uri)

    return {
        "memory_ids": memory_ids,
        "knowledge_links": knowledge_links,
    }


__all__ = [
    "KNOWLEDGE_LINK_PATTERN",
    "KnowledgeLink",
    "is_knowledge_link",
    "parse_knowledge_links",
    "categorize_links",
]
