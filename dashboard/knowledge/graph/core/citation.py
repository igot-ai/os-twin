"""Shared citation utilities for the graph-RAG pipeline.

Consolidates UUID validation, chunk-metadata resolution, citation-string
formatting, and the async event-loop runner that were previously duplicated
across ``graph_rag_query_engine.py`` and ``query_executioner.py``.

All symbols are re-exported from their original modules for backward
compatibility — existing import paths continue to work.
"""

from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

FILE_METADATA_FIELDS = ["file_path", "filename", "page_range", "page_number"]


def is_uuid(value: str) -> bool:
    """Return True if *value* is a well-formed lowercase UUID string."""
    if not isinstance(value, str):
        return False
    try:
        obj = _uuid.UUID(value)
        return str(obj) == value.lower()
    except (ValueError, AttributeError):
        return False


def format_citation(metadata: dict, uuid_fallback: str = "") -> str:
    """Build a human-readable citation string from chunk metadata.

    Returns ``[filename(page)]`` when file metadata is available,
    otherwise falls back to `` `uuid` ``.
    """
    file_identifier = metadata.get("filename", "") or metadata.get("file_path", "")
    page_info = metadata.get("page_range", "") or metadata.get("page_number", "")
    page_suffix = f"({page_info})" if page_info else ""
    if file_identifier:
        return f"[{file_identifier}{page_suffix}]"
    if uuid_fallback:
        return f"`{uuid_fallback}`"
    return ""


def resolve_chunk_metadata(index: Any, uuid_key: str) -> Optional[dict]:
    """Fetch a chunk node's properties from a PropertyGraphIndex.

    Returns a dict with keys ``file_path``, ``filename``, ``info``,
    ``page_number``, ``entity_description`` when the node exists and
    carries file metadata.  Returns ``None`` otherwise.
    """
    if index is None:
        return None
    store = getattr(index, "property_graph_store", None)
    if store is None:
        return None
    try:
        nodes = store.get(ids=[uuid_key])
        for node in nodes:
            props = node.properties or {}
            if not any(k in props for k in FILE_METADATA_FIELDS):
                return None
            return {
                "file_path": props.get("file_path", ""),
                "filename": props.get("filename", ""),
                "info": node.text,
                "page_number": props.get("page_number", ""),
                "page_range": props.get("page_range", ""),
                "entity_description": props.get("entity_description", ""),
            }
    except Exception as exc:
        logger.error("Error resolving chunk metadata for %s: %s", uuid_key, exc)
    return None


@dataclass(frozen=True)
class CitationRecord:
    """Typed container for a single citation entry.

    Replaces the untyped ``dict[str, Any]`` previously used in
    ``create_citation`` return values, ensuring a consistent contract
    across all citation code paths.
    """

    citation: str
    file_path: str = ""
    filename: str = ""
    info: str = ""
    entity_description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "citation": self.citation,
            "file_path": self.file_path,
            "filename": self.filename,
            "info": self.info,
            "entity_description": self.entity_description,
        }


def build_citation_dict(
    metadata: dict,
    index: Any,
) -> Optional[dict[str, dict[str, str]]]:
    """Build a citation dict keyed by UUID for graph-node metadata.

    When *metadata* contains ``target_id`` / ``source_id`` pointing to
    chunk nodes, each UUID candidate is resolved against the property
    graph store.  Returns ``None`` when no resolvable UUID is found.
    """
    if not metadata or not isinstance(metadata, dict):
        return None

    candidates: list[str] = []
    target_id = metadata.get("target_id", "")
    source_id = metadata.get("source_id", "")

    if target_id and is_uuid(target_id):
        candidates.append(target_id)
    if source_id and is_uuid(source_id) and source_id != target_id:
        candidates.append(source_id)

    if not candidates:
        candidates = [
            v
            for v in (metadata.get("id"), metadata.get("node_id"))
            if v and is_uuid(v)
        ]

    if not candidates:
        return None

    result: dict[str, dict[str, str]] = {}
    for uuid_val in candidates:
        resolved = resolve_chunk_metadata(index, uuid_val)
        if resolved is None:
            continue
        citation_str = format_citation(resolved, uuid_fallback=uuid_val)
        record = CitationRecord(
            citation=citation_str,
            file_path=resolved.get("file_path", ""),
            filename=resolved.get("filename", ""),
            info=resolved.get("info", ""),
            entity_description=resolved.get("entity_description", ""),
        )
        result[uuid_val] = record.to_dict()

    return result if result else None


def extract_file_metadata(properties: dict) -> Optional[dict]:
    """Extract file-level metadata from a node's properties dict.

    Returns ``None`` if none of the ``FILE_METADATA_FIELDS`` are present.
    """
    if not properties or not any(key in properties for key in FILE_METADATA_FIELDS):
        return None
    return {
        "file_path": properties.get("file_path", ""),
        "filename": properties.get("filename", ""),
        "page_range": properties.get("page_range", ""),
        "page_number": properties.get("page_number", ""),
        "entity_description": properties.get("entity_description", ""),
    }


def run_async(coro):
    """Run an awaitable from sync code without disturbing the caller's loop.

    Uses ``asyncio.get_running_loop()`` to detect whether the caller is
    already inside an event loop.  If so, executes the coroutine on a
    fresh loop in a worker thread.  Otherwise drives a new loop via
    ``asyncio.run()``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    def runner():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(runner).result()
