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

# Sliding-window defaults (ported from FileExtraction pattern).
# A page is a paragraph-sized segment; window_size pages are grouped per Document.
_SLIDING_WINDOW_SIZE = 3
_SLIDING_WINDOW_OVERLAP = 1

# When content exceeds this many chars, use sliding-window to emit page-ranged
# Documents (richer metadata) instead of flat char chunks.
_SLIDING_WINDOW_THRESHOLD = _CHUNK_SIZE * 10  # ~10 KB


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


def _split_into_pages(text: str, max_page_chars: int = _CHUNK_SIZE) -> List[str]:
    """Split text into 'pages' for sliding-window processing.

    Prefers double-newline paragraph boundaries (like natural document pages);
    falls back to hard char splitting if paragraphs are too large.

    Returns a non-empty list of non-empty page strings.
    """
    if not text:
        return []
    # Split on paragraph boundaries first
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        paras = [text.strip()]

    # Merge very short paras and split very long ones so each page ~ max_page_chars
    pages: List[str] = []
    buf = ""
    for para in paras:
        if len(buf) + len(para) + 2 <= max_page_chars:
            buf = f"{buf}\n\n{para}".strip() if buf else para
        else:
            if buf:
                pages.append(buf)
            if len(para) > max_page_chars:
                # Hard split long paragraphs
                for i in range(0, len(para), max_page_chars):
                    chunk = para[i : i + max_page_chars].strip()
                    if chunk:
                        pages.append(chunk)
            else:
                buf = para
            buf = "" if len(para) > max_page_chars else para
    if buf:
        pages.append(buf)
    return pages if pages else [text.strip()]


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

        Uses :func:`dashboard.llm_client.create_client` for provider
        detection and ``base_url`` resolution.  All client types returned
        by ``create_client`` expose a ``base_url`` attribute.

        MarkItDown's ``ImageConverter`` uses the **sync** OpenAI SDK
        interface, so we build a sync ``openai.OpenAI`` client using
        the ``base_url`` that ``create_client`` resolved.

        When no LLM model or API key is configured, returns a plain
        ``MarkItDown()`` — image converters fall back to alt-text only.
        """
        from markitdown import MarkItDown  # noqa: WPS433 — lazy import

        from dashboard.knowledge.config import LLM_MODEL

        if not LLM_MODEL:
            return MarkItDown()

        try:
            from dashboard.llm_client import (  # noqa: WPS433
                PROVIDER_API_KEYS,
                _detect_provider_from_model,
                create_client,
            )

            # Resolve the API key from the provider-specific env var.
            provider = _detect_provider_from_model(LLM_MODEL)
            env_name = PROVIDER_API_KEYS.get(provider)
            api_key = os.environ.get(env_name) if env_name else None

            if not api_key:
                logger.debug(
                    "No API key for provider %r (%s); MarkItDown vision disabled.",
                    provider,
                    env_name,
                )
                return MarkItDown()

            # create_client resolves provider + base_url for us.
            # All client types (OpenAIClient, GoogleClient) expose a
            # ``base_url`` attribute suitable for building a sync
            # OpenAI SDK client that MarkItDown's ImageConverter needs.
            llm_client = create_client(model=LLM_MODEL, api_key=api_key)
            base_url = getattr(llm_client, "base_url", None)

            if not base_url:
                logger.debug(
                    "create_client(%s) has no base_url; MarkItDown vision disabled.",
                    LLM_MODEL,
                )
                return MarkItDown()

            from openai import OpenAI  # noqa: WPS433

            sync_client = OpenAI(api_key=api_key, base_url=base_url)
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

    # -- Helpers --------------------------------------------------------

    # -- Sliding-window helpers -----------------------------------------

    @staticmethod
    def _create_sliding_windows(
        total_pages: int,
        window_size: int = _SLIDING_WINDOW_SIZE,
        overlap: int = _SLIDING_WINDOW_OVERLAP,
    ) -> List[tuple]:
        """Create sliding windows over a range of page indices.

        Ported from ``FileExtraction._create_sliding_windows`` (file_extraction.py)
        to provide the same page-window semantics for text-based documents.

        Parameters
        ----------
        total_pages:
            Total number of pages (or page-sized segments) in the document.
        window_size:
            Number of pages to include in each window.
        overlap:
            Number of pages to share between consecutive windows.

        Returns
        -------
        List of ``(window_start, [page_indices])`` tuples, sorted by window_start.

        Raises
        ------
        ValueError
            If ``window_size < 1``, ``overlap < 0`` or ``overlap >= window_size``.
        """
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= window_size:
            raise ValueError("overlap must be less than window_size")

        windows: List[tuple] = []
        step_size = window_size - overlap

        if total_pages <= window_size:
            windows.append((0, list(range(0, total_pages))))
        else:
            i = 0
            while i < total_pages:
                window_end = min(i + window_size, total_pages)
                window_pages = list(range(i, window_end))
                windows.append((i, window_pages))
                if window_end == total_pages:
                    break
                i += step_size
                if i + window_size > total_pages and i < total_pages:
                    final_start = max(i, total_pages - window_size)
                    existing_starts = {start for start, _ in windows}
                    if final_start not in existing_starts:
                        windows.append((final_start, list(range(final_start, total_pages))))
                    break

        return windows

    def _sliding_window_chunk(
        self,
        text: str,
        file_url: str,
        ws_id: Optional[str],
        node_id: Optional[str],
        extra: Dict[str, Any],
        window_size: int = _SLIDING_WINDOW_SIZE,
        overlap: int = _SLIDING_WINDOW_OVERLAP,
    ) -> List[Document]:
        """Chunk ``text`` using a sliding-window approach with page-range metadata.

        Large documents are split into 'page' segments (by paragraph boundary),
        then groups of pages are combined into overlapping windows — matching
        the ``FileExtraction._extract_pdf_content`` pattern.

        Each output ``Document`` gets ``page_range``, ``window_start``, and
        ``total_pages`` metadata entries in addition to the standard fields.
        """
        pages = _split_into_pages(text)
        total_pages = len(pages)
        windows = self._create_sliding_windows(total_pages, window_size, overlap)

        path = Path(file_url)
        docs: List[Document] = []
        for window_start, page_indices in windows:
            window_text = "\n\n".join(pages[i] for i in page_indices).strip()
            if not window_text:
                continue
            page_range = f"{page_indices[0] + 1}-{page_indices[-1] + 1}"
            metadata: Dict[str, Any] = {
                "file_path": str(file_url),
                "filename": path.name,
                "processor": MARKITDOWN_FILE,
                "window_start": window_start,
                "page_range": page_range,
                "page_number": page_indices[0] + 1,
                "total_pages": total_pages,
                "window_size": window_size,
                "overlap": overlap,
                "chunk_index": windows.index((window_start, page_indices)),
                "total_chunks": len(windows),
            }
            if ws_id:
                metadata["ws_id"] = ws_id
            if node_id:
                metadata["node_id"] = node_id
            for k in ("mime_type", "file_size", "mtime"):
                if k in extra:
                    metadata[k] = extra[k]
            docs.append(Document(text=window_text, id_=str(uuid.uuid4()), metadata=metadata))
        return docs

    # -- Text → Document helpers ----------------------------------------

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
        Documents with richer provenance metadata (``page_range``,
        ``window_start``, ``total_pages``).  Small documents use the simpler
        flat char-chunker so the overhead of page-splitting is avoided.
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
        chunks = _chunk_text(text)
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
