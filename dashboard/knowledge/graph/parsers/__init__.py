"""Document parsers (MarkItDown only after EPIC-001 cleanup).

The legacy DOCX/sheet/raw parsers were removed (ADR-09); MarkItDown handles
those formats natively.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from llama_index.core.schema import Document

from dashboard.knowledge.graph.parsers.markitdown_reader import (
    MARKITDOWN_FILE,
    MarkitdownReader,
)

logger = logging.getLogger(__name__)


class ReadResolver:
    """Routes file requests to the (single, MarkItDown-based) reader.

    The DocumentProcessingRouter that used to live in `app.core.processing`
    was removed; everything goes through MarkItDown now.
    """

    def __init__(self) -> None:
        self._reader = {MARKITDOWN_FILE: MarkitdownReader()}

    def read(
        self,
        files: List[Dict[str, Any]] = None,
        ws_id: Optional[str] = None,
        node_id: Optional[str] = None,
        **kwargs,
    ) -> Sequence[Document]:
        """Read and process multiple files."""
        if files is None and "files" in kwargs:
            files = kwargs.pop("files")
        if files is None:
            return []

        docs: list[Document] = []
        for file_info in files:
            try:
                logger.info("Processing file %s", file_info.get("url"))
                reader = self._reader[MARKITDOWN_FILE]
                file_docs = reader.read(file_info, ws_id, node_id, **kwargs)
                docs.extend(file_docs)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error processing file %s: %s", file_info.get("url"), exc)
                continue
        return docs

    def files_to_unit_of_works(
        self,
        files: List[Dict[str, Any]],
        ws_id: Optional[str] = None,
        node_id: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Convert files to unit-of-work items for parallel processing."""
        uows: list[dict] = []
        for file_info in files:
            try:
                reader = self._reader[MARKITDOWN_FILE]
                file_uows = reader.read(file_info, ws_id, node_id, **kwargs)
                uows.extend(file_uows)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error creating UoW for file %s: %s", file_info.get("url"), exc)
                continue
        return uows


__all__ = [
    "ReadResolver",
    "MarkitdownReader",
    "MARKITDOWN_FILE",
]
