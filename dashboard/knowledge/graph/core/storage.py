"""Legacy storage helpers (post EPIC-003 v2).

This module used to host:

* ``RAGStorage`` — a llama-index ``PropertyGraphIndex`` orchestrator.
* ``ChromaConfig`` + ``init_vector_store`` / ``init_vector_store_for_namespace``
  — chromadb persistence helpers.

Both were removed in EPIC-003 v2 because:

1. The ``Ingestor`` (engineer-3 bypass) writes vectors via
   :class:`dashboard.knowledge.vector_store.NamespaceVectorStore` (zvec)
   and entities via :class:`KuzuLabelledPropertyGraph` directly. Nothing
   in the codebase still calls ``RAGStorage`` end-to-end.
2. The ``chromadb`` dependency was dropped from ``requirements.txt`` —
   importing it would now raise ``ImportError`` in this venv.

Only :func:`delete_graph_db` and the GC ledger helpers remain because the
namespace-deletion path (``NamespaceManager.delete``) and an MCP cleanup
hook still call them.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, List

from dashboard.knowledge.config import (
    GARBAGE_COLLECTION_FILE,
    KNOWLEDGE_DIR,
)
from dashboard.knowledge.graph.index.kuzudb import (
    KuzuLabelledPropertyGraph,
    KUZU_DATABASE_PATH,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Garbage collection (kept; called by the MCP delete path)
# ---------------------------------------------------------------------------


def _read_gc_file() -> list:
    path = Path(GARBAGE_COLLECTION_FILE)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read GC file %s: %s", path, exc)
        return []


def _write_gc_file(data: list) -> None:
    path = Path(GARBAGE_COLLECTION_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def delete_vector_store(folder_id: str) -> None:
    """Schedule deletion of a vector store directory by appending to the GC ledger.

    The on-disk layout used to be ``{KNOWLEDGE_DIR}/{folder_id}/chroma/`` and
    is now ``{KNOWLEDGE_DIR}/{folder_id}/vectors/`` (zvec). The GC entry is
    just a path string; whoever consumes the ledger handles the actual rm.
    """
    try:
        persist_directory = os.path.join(str(KNOWLEDGE_DIR), folder_id, "vectors")
        data = _read_gc_file()
        data.append(persist_directory)
        _write_gc_file(data)
        logger.info("Marked vector store for deletion: %s", folder_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error during vector-store cleanup: %s", exc)


def delete_graph_db(id: str) -> None:
    """Delete Kuzu DB files associated with ``id``."""
    try:
        id_name = id.replace("-", "_")
        candidates = list(Path(KUZU_DATABASE_PATH).glob(f"{id_name}*"))
        if not candidates:
            logger.warning("No graph database files found starting with: %s", id_name)
            return

        temp_graph = KuzuLabelledPropertyGraph(
            index=id,
            ws_id="cleanup_temp",
            database_path=KUZU_DATABASE_PATH,
        )
        try:
            temp_graph.close_connection()
        except Exception:  # noqa: BLE001
            pass

        for file_path in candidates:
            if file_path.is_file():
                file_path.unlink()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to delete graph database for ID %s: %s", id, exc)


# ---------------------------------------------------------------------------
# Removed in EPIC-003 v2 — kept as raise-on-call stubs to make removal noisy
# rather than silent.
# ---------------------------------------------------------------------------


def init_vector_store(*args: Any, **kwargs: Any):  # pragma: no cover
    """Removed in EPIC-003 v2. Use :class:`NamespaceVectorStore` directly."""
    raise NotImplementedError(
        "init_vector_store was removed in EPIC-003 v2 (chromadb → zvec migration). "
        "Use dashboard.knowledge.vector_store.NamespaceVectorStore instead, "
        "or NamespaceManager.vector_dir(ns) for the on-disk path."
    )


def init_vector_store_for_namespace(*args: Any, **kwargs: Any):  # pragma: no cover
    """Removed in EPIC-003 v2. Use ``NamespaceVectorStore`` + ``NamespaceManager.vector_dir``."""
    raise NotImplementedError(
        "init_vector_store_for_namespace was removed in EPIC-003 v2 "
        "(chromadb → zvec migration). Use NamespaceVectorStore + "
        "NamespaceManager.vector_dir(ns) instead."
    )
