"""Knowledge link utilities for Memory ↔ Knowledge Bridge.

This module provides utilities for parsing, validating, and working with
`knowledge://` links that connect memory notes to knowledge chunks.

Link format: `knowledge://ns/<file_hash>#<chunk_idx>`

Where:
- ns: namespace name (e.g., "docs", "api", "spec")
- file_hash: SHA256 hash of the source file (truncated to 16 chars)
- chunk_idx: zero-based chunk index within the file

Examples:
    knowledge://docs/abc123def456#0
    knowledge://api/feedbeefcafe#3
"""

from __future__ import annotations

import dataclasses
import re
from typing import Optional


# Regex pattern for knowledge:// links
# Format: knowledge://<namespace>/<file_hash>#<chunk_idx>
KNOWLEDGE_LINK_PATTERN = re.compile(
    r"^knowledge://"
    r"(?P<namespace>[a-zA-Z0-9_-]+)/"
    r"(?P<file_hash>[a-f0-9]+)"
    r"#(?P<chunk_idx>\d+)$"
)


@dataclasses.dataclass(frozen=True)
class KnowledgeLink:
    """A parsed knowledge:// link.
    
    Attributes:
        namespace: The knowledge namespace (e.g., "docs", "api")
        file_hash: SHA256 hash of the source file (truncated)
        chunk_idx: Zero-based chunk index within the file
        raw: The original raw link string
    """
    namespace: str
    file_hash: str
    chunk_idx: int
    raw: str
    
    @classmethod
    def parse(cls, link: str) -> Optional["KnowledgeLink"]:
        """Parse a knowledge:// link string.
        
        Args:
            link: The raw link string to parse
            
        Returns:
            KnowledgeLink if valid, None if not a knowledge:// link or malformed
        """
        if not link.startswith("knowledge://"):
            return None
            
        match = KNOWLEDGE_LINK_PATTERN.match(link)
        if not match:
            return None
            
        return cls(
            namespace=match.group("namespace"),
            file_hash=match.group("file_hash"),
            chunk_idx=int(match.group("chunk_idx")),
            raw=link,
        )
    
    def to_uri(self) -> str:
        """Convert back to URI format."""
        return f"knowledge://{self.namespace}/{self.file_hash}#{self.chunk_idx}"
    
    def __str__(self) -> str:
        return self.to_uri()


def parse_knowledge_links(links: list[str]) -> list[KnowledgeLink]:
    """Extract all valid knowledge:// links from a list of link strings.
    
    Args:
        links: List of link strings (may contain regular memory IDs too)
        
    Returns:
        List of parsed KnowledgeLink objects
    """
    result = []
    for link in links:
        parsed = KnowledgeLink.parse(link)
        if parsed is not None:
            result.append(parsed)
    return result


def is_knowledge_link(link: str) -> bool:
    """Check if a link string is a valid knowledge:// link.
    
    Args:
        link: The link string to check
        
    Returns:
        True if it's a valid knowledge:// link
    """
    return link.startswith("knowledge://") and KNOWLEDGE_LINK_PATTERN.match(link) is not None


def categorize_links(links: list[str]) -> dict:
    """Categorize links into memory IDs and knowledge links.
    
    Args:
        links: List of link strings (mixed types)
        
    Returns:
        Dict with 'memory_ids' (list of UUIDs) and 'knowledge_links' (list of KnowledgeLink)
    """
    memory_ids = []
    knowledge_links = []
    
    for link in links:
        if is_knowledge_link(link):
            parsed = KnowledgeLink.parse(link)
            if parsed:
                knowledge_links.append(parsed)
        else:
            # Assume it's a memory ID (UUID format)
            memory_ids.append(link)
    
    return {
        "memory_ids": memory_ids,
        "knowledge_links": knowledge_links,
    }


__all__ = [
    "KnowledgeLink",
    "parse_knowledge_links",
    "is_knowledge_link",
    "categorize_links",
    "KNOWLEDGE_LINK_PATTERN",
]
