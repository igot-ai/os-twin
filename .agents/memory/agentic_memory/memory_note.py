"""MemoryNote — the canonical on-disk shape for a single memory.

Extracted from memory_system.py so it can be imported by lightweight
consumers (like the dashboard) without dragging in the heavy retriever
stack (sentence_transformers, chromadb, nltk, litellm).

Anything that wants to read or write a memory note's markdown file should
go through this class.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Optional


class MemoryNote:
    """A memory note that represents a single unit of information in the memory system.

    This class encapsulates all metadata associated with a memory, including:
    - Core content and identifiers
    - Temporal information (creation and access times)
    - Semantic metadata (keywords, context, tags)
    - Relationship data (links to other memories)
    - Usage statistics (retrieval count)
    - Evolution tracking (history of changes)
    """

    def __init__(
        self,
        content: str,
        id: Optional[str] = None,
        name: Optional[str] = None,
        path: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        retrieval_count: Optional[int] = None,
        timestamp: Optional[str] = None,
        last_accessed: Optional[str] = None,
        last_modified: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        **kwargs,
    ):
        """Initialize a new memory note with its associated metadata.

        Args:
            content: The main text content of the memory
            id: Unique identifier for the memory. If None, a UUID will be generated
            name: Human-readable name for the memory (used as filename)
            path: Directory path for organizing memory in a tree
                (e.g. "devops/kubernetes", "backend/database")
            keywords: Key terms extracted from the content
            links: Active references to other memories (can be added/removed)
            retrieval_count: Number of times this memory has been accessed
            timestamp: Creation time in format YYYYMMDDHHMM
            last_accessed: Last access time in format YYYYMMDDHHMM
            last_modified: Last content modification time in format YYYYMMDDHHMM.
                Tracks when the note's content or metadata was last changed
                (as opposed to last_accessed which tracks retrieval).
            context: The broader context or domain of the memory
            tags: Additional classification tags
            summary: Short summary for embedding when content exceeds token limit
            **kwargs: Additional fields. Supported keys:
                category: Classification category (default: "Uncategorized")
                backlinks: Passive references from other memories (auto-maintained)
                evolution_history: Record of how the memory has evolved
        """
        # Core content and ID
        self.content = content
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.path = path

        # Semantic metadata
        self.keywords = keywords or []
        self.links = links or []
        self.backlinks: List[str] = kwargs.get("backlinks") or []
        self.context = context or "General"
        self.category = kwargs.get("category") or "Uncategorized"
        self.tags = tags or []

        # Temporal information
        current_time = datetime.now().strftime("%Y%m%d%H%M")
        self.timestamp = timestamp or current_time
        self.last_accessed = last_accessed or current_time
        # last_modified defaults to timestamp for backwards compat with
        # existing notes that don't have this field yet.
        self.last_modified = last_modified or self.timestamp

        # Usage and evolution data
        self.retrieval_count = retrieval_count or 0
        self.evolution_history: List = kwargs.get("evolution_history") or []

        # Summary for long content embedding
        self.summary = summary

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a filesystem-safe slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug.strip("-")

    @property
    def filename(self) -> str:
        """Generate a filesystem-safe filename from the name, falling back to id."""
        if not self.name:
            return self.id
        return self._slugify(self.name) or self.id

    @property
    def filepath(self) -> str:
        """Generate the relative file path including directory tree.

        Returns path like 'devops/kubernetes/container-orchestration.md'
        or just 'container-orchestration.md' if no path is set.
        """
        name_slug = self.filename
        if self.path:
            # Slugify each segment of the path
            segments = [
                self._slugify(s) for s in self.path.strip("/").split("/") if s.strip()
            ]
            segments = [s for s in segments if s]  # remove empty
            if segments:
                return os.path.join(*segments, f"{name_slug}.md")
        return f"{name_slug}.md"

    def to_markdown(self) -> str:
        """Serialize this note to a markdown string with YAML frontmatter."""
        frontmatter = {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "keywords": self.keywords,
            "links": self.links,
            "retrieval_count": self.retrieval_count,
            "timestamp": self.timestamp,
            "last_accessed": self.last_accessed,
            "last_modified": self.last_modified,
            "context": self.context,
            "evolution_history": self.evolution_history,
            "category": self.category,
            "tags": self.tags,
        }
        if self.summary:
            frontmatter["summary"] = self.summary

        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        lines.append("---")
        lines.append("")
        lines.append(self.content)
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "MemoryNote":
        """Deserialize a MemoryNote from a markdown string with YAML frontmatter."""
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid markdown format: missing frontmatter")

        frontmatter_str = parts[1].strip()
        content = parts[2].strip()

        metadata = {}
        for line in frontmatter_str.split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                try:
                    metadata[key.strip()] = json.loads(value)
                except json.JSONDecodeError:
                    # Tolerate hand-written notes whose values aren't strict
                    # JSON (e.g. unquoted strings). Strip surrounding quotes
                    # if present.
                    metadata[key.strip()] = value.strip().strip('"').strip("'")

        return cls(
            content=content,
            id=metadata.get("id"),
            name=metadata.get("name"),
            path=metadata.get("path"),
            keywords=metadata.get("keywords"),
            links=metadata.get("links"),
            retrieval_count=metadata.get("retrieval_count"),
            timestamp=metadata.get("timestamp"),
            last_accessed=metadata.get("last_accessed"),
            last_modified=metadata.get("last_modified"),
            context=metadata.get("context"),
            evolution_history=metadata.get("evolution_history"),
            category=metadata.get("category"),
            tags=metadata.get("tags"),
            summary=metadata.get("summary"),
        )

    @classmethod
    def from_file(cls, path) -> "MemoryNote":
        """Read a MemoryNote from a markdown file on disk."""
        from pathlib import Path

        return cls.from_markdown(Path(path).read_text(encoding="utf-8"))
