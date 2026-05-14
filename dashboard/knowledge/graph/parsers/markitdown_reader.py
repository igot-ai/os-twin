"""Universal document reader using Microsoft's MarkItDown library.

Reads any supported file from a local path, converts it to markdown, chunks
the resulting text, and returns ``Document`` objects suitable for ingestion.

Heavy `markitdown` import is deferred until the first ``.read()`` call.

Chunking is delegated to :mod:`dashboard.knowledge.chunking` so the
sliding-window algorithm and metadata shape are shared with the
ingestion pipeline.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core.schema import Document

from dashboard.knowledge.chunking import (
    SlidingWindowChunker,
    flat_chunk_text,
)
from dashboard.knowledge.config import (
    SLIDING_WINDOW_OVERLAP,
    SLIDING_WINDOW_SIZE,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)
from dashboard.knowledge.graph.parsers.base import DocParser

logger = logging.getLogger(__name__)

MARKITDOWN_FILE = "markitdown"

_CHUNK_SIZE = 1024
_CHUNK_OVERLAP = 200

_SLIDING_WINDOW_THRESHOLD = _CHUNK_SIZE * 10


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
        """Lazy-instantiate the MarkItDown converter (alias of :meth:`_get_markitdown`)."""
        if self._converter is not None:
            return self._converter
        self._converter = self._get_markitdown()
        return self._converter

    def _get_markitdown(self) -> Any:
        """Lazy-construct a MarkItDown client with provider-aware LLM support.

        Uses :func:`dashboard.llm_client.create_openai_sync_client` to build
        an OpenAI-compatible sync client from the configured LLM model.
        This works with all providers (OpenAI, Google/Gemini, Ollama, etc.)
        because it resolves the provider-specific ``base_url`` and ``api_key``
        and wraps them in the standard ``openai.OpenAI`` SDK interface that
        MarkItDown's ``ImageConverter`` expects.

        When no LLM model or API key is configured, returns a plain
        ``MarkItDown()`` — image converters fall back to alt-text only.
        """
        from markitdown import MarkItDown  # noqa: WPS433 — lazy import

        from dashboard.knowledge.config import LLM_MODEL

        if not LLM_MODEL:
            return MarkItDown()

        try:
            from dashboard.llm_client import create_openai_sync_client  # noqa: WPS433

            sync_client = create_openai_sync_client(model=LLM_MODEL)

            if sync_client is None:
                logger.debug(
                    "No API key resolved for %s; MarkItDown vision disabled.",
                    LLM_MODEL,
                )
                return MarkItDown()

            return MarkItDown(llm_client=sync_client, llm_model=LLM_MODEL)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to initialize vision client for MarkItDown "
                "(provider=%s): %s; image files will produce empty markdown.",
                LLM_MODEL,
                exc,
            )
        return MarkItDown()

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

    # -- Text → Document helpers ----------------------------------------

    def _sliding_window_chunk(
        self,
        text: str,
        file_url: str,
        ws_id: Optional[str],
        node_id: Optional[str],
        extra: Dict[str, Any],
        window_size: int = SLIDING_WINDOW_SIZE,
        overlap: int = SLIDING_WINDOW_OVERLAP,
    ) -> List[Document]:
        """Chunk ``text`` using :class:`SlidingWindowChunker` with page-range metadata.

        Delegates the actual windowing algorithm to the shared chunker
        so metadata shape (``page_range``, ``window_start``,
        ``total_pages``, etc.) is consistent with the ingestion pipeline.
        """
        chunker = SlidingWindowChunker(
            window_size=window_size,
            overlap=overlap,
            page_chars=_CHUNK_SIZE,
        )
        raw_chunks = chunker.chunk(text)
        if not raw_chunks:
            return []

        path = Path(file_url)
        docs: List[Document] = []
        for raw in raw_chunks:
            metadata: Dict[str, Any] = {
                "file_path": str(file_url),
                "filename": path.name,
                "processor": MARKITDOWN_FILE,
            }
            metadata.update(raw["metadata"])
            if ws_id:
                metadata["ws_id"] = ws_id
            if node_id:
                metadata["node_id"] = node_id
            for k in ("mime_type", "file_size", "mtime"):
                if k in extra:
                    metadata[k] = extra[k]
            docs.append(Document(text=raw["text"], id_=str(uuid.uuid4()), metadata=metadata))
        return docs

    def _docs_from_text(
        self,
        text: str,
        file_url: str,
        ws_id: Optional[str],
        node_id: Optional[str],
        extra: Dict[str, Any],
    ) -> List[Document]:
        """Chunk ``text`` and wrap each chunk in a Document.

        For large documents (> ``_SLIDING_WINDOW_THRESHOLD`` chars) this
        delegates to :meth:`_sliding_window_chunk` to produce page-ranged
        Documents with richer provenance metadata.  Small documents use
        the simpler flat char-chunker so the overhead of page-splitting
        is avoided.
        """
        if not text or not text.strip():
            return []

        if len(text) > _SLIDING_WINDOW_THRESHOLD:
            return self._sliding_window_chunk(
                text,
                file_url=file_url,
                ws_id=ws_id,
                node_id=node_id,
                extra=extra,
            )

        path = Path(file_url)
        chunks = flat_chunk_text(text, chunk_size=_CHUNK_SIZE, overlap=_CHUNK_OVERLAP)
        docs: List[Document] = []
        for index, chunk in enumerate(chunks):
            metadata: Dict[str, Any] = {
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
