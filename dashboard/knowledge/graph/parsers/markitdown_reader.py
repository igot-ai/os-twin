"""Universal document reader using Microsoft's MarkItDown library.

Reads any supported file from a local path, converts it to markdown, chunks
the resulting text, and returns ``Document`` objects suitable for ingestion.

Heavy `markitdown` import is deferred until the first ``.read()`` call.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core.schema import Document

from dashboard.knowledge.config import SUPPORTED_DOCUMENT_EXTENSIONS
from dashboard.knowledge.graph.parsers.base import DocParser

logger = logging.getLogger(__name__)

MARKITDOWN_FILE = "markitdown"

# Hardcoded chunking defaults (per TASK-009 guidance — was SettingService).
_CHUNK_SIZE = 1024
_CHUNK_OVERLAP = 200


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks of approximately ``chunk_size`` chars."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: List[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(text):
            break
    return chunks


class MarkitdownReader(DocParser):
    """Read a file from disk and return chunked Document objects."""

    def __init__(
        self,
        extract_images: bool = True,
        preserve_tables: bool = True,
        include_metadata: bool = True,
        **kwargs,
    ) -> None:
        super().__init__()
        self.type = MARKITDOWN_FILE
        self.extract_images = extract_images
        self.preserve_tables = preserve_tables
        self.include_metadata = include_metadata
        self.supported_extensions = SUPPORTED_DOCUMENT_EXTENSIONS
        self._converter: Any | None = None  # cached MarkItDown instance

    # -- Internals ------------------------------------------------------

    def _get_converter(self) -> Any:
        """Lazy-instantiate the MarkItDown converter."""
        if self._converter is not None:
            return self._converter
        from markitdown import MarkItDown  # noqa: WPS433 — lazy import

        self._converter = MarkItDown()
        return self._converter

    # -- Public API -----------------------------------------------------

    def read(
        self,
        file: Dict[str, Any],
        ws_id: Optional[str] = None,
        node_id: Optional[str] = None,
        **kwargs,
    ) -> List[Document]:
        """Read and convert a local file to chunked Documents.

        Args:
            file: dict with at least a "url" key (treated as a local file path).
                  Also accepts an optional pre-extracted "content" string.
            ws_id: Optional workspace ID for tracking (passed in metadata).
            node_id: Optional node ID for tracking (passed in metadata).

        Returns:
            List of Document instances, one per chunk. Empty list on failure.
        """
        file_url = file.get("url") if isinstance(file, dict) else None
        if not file_url:
            logger.warning("MarkitdownReader.read: no 'url' provided")
            return []

        # Pre-extracted content path
        if isinstance(file, dict) and file.get("content"):
            return self._docs_from_text(
                str(file["content"]),
                file_url=file_url,
                ws_id=ws_id,
                node_id=node_id,
                extra=file,
            )

        # Drop URL inputs — local files only for now (per TASK-009 guidance)
        if file_url.startswith(("http://", "https://", "data:")):
            logger.warning("MarkitdownReader: HTTP/data URLs not supported in v1: %s", file_url)
            return []

        if not os.path.exists(file_url):
            logger.warning("MarkitdownReader: file does not exist: %s", file_url)
            return []

        try:
            converter = self._get_converter()
            result = converter.convert(file_url)
            text = getattr(result, "text_content", None) or getattr(result, "text", None) or ""
            if not text:
                logger.info("MarkitdownReader: no content extracted from %s", file_url)
                return []
            return self._docs_from_text(text, file_url=file_url, ws_id=ws_id, node_id=node_id, extra=file)
        except Exception as exc:  # noqa: BLE001
            logger.error("MarkitdownReader: failed to process %s: %s", file_url, exc)
            return []

    # -- Helpers --------------------------------------------------------

    def _docs_from_text(
        self,
        text: str,
        file_url: str,
        ws_id: Optional[str],
        node_id: Optional[str],
        extra: Dict[str, Any],
    ) -> List[Document]:
        """Chunk ``text`` and wrap each chunk in a Document."""
        path = Path(file_url)
        chunks = _chunk_text(text)
        docs: List[Document] = []
        for index, chunk in enumerate(chunks):
            metadata = {
                "file_path": str(file_url),
                "filename": path.name,
                "chunk_index": index,
                "total_chunks": len(chunks),
                "processor": MARKITDOWN_FILE,
            }
            if ws_id:
                metadata["ws_id"] = ws_id
            if node_id:
                metadata["node_id"] = node_id
            for k in ("mime_type", "file_size", "mtime"):
                if k in extra:
                    metadata[k] = extra[k]
            docs.append(Document(text=chunk, id_=str(uuid.uuid4()), metadata=metadata))
        return docs
