"""Configuration constants and path helpers for the knowledge package.

All values are env-overridable. No heavy deps imported at module load.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Core paths -------------------------------------------------------------

KNOWLEDGE_DIR: Path = Path(
    os.environ.get("OSTWIN_KNOWLEDGE_DIR", str(Path.home() / ".ostwin" / "knowledge"))
)

# --- Model defaults ---------------------------------------------------------

EMBEDDING_MODEL: str = os.environ.get(
    "OSTWIN_KNOWLEDGE_EMBED_MODEL", "BAAI/bge-small-en-v1.5"
)
EMBEDDING_DIMENSION: int = int(os.environ.get("OSTWIN_KNOWLEDGE_EMBED_DIM", "384"))
LLM_MODEL: str = os.environ.get(
    "OSTWIN_KNOWLEDGE_LLM_MODEL", "claude-sonnet-4-5-20251022"
)

# --- Retrieval / graph tunables --------------------------------------------

PAGERANK_SCORE_THRESHOLD: float = float(
    os.environ.get("OSTWIN_KNOWLEDGE_PR_THRESHOLD", "0.001")
)
KUZU_MIGRATE: bool = os.environ.get("OSTWIN_KNOWLEDGE_KUZU_MIGRATE", "1") == "1"

# --- Per-namespace path helpers --------------------------------------------
#
# These module-level helpers are **deprecated** for any code path that needs to
# honour a custom ``base_dir`` (notably tests). They unconditionally root
# everything under :data:`KNOWLEDGE_DIR`, which means a
# :class:`~dashboard.knowledge.namespace.NamespaceManager` constructed with a
# different ``base_dir`` will see its manifest in the right place but its
# vectors / graph in the global location — the bug QA flagged in EPIC-003.
#
# Prefer the **instance methods** on :class:`NamespaceManager`:
#   * ``nm.namespace_dir(ns)``   == ``base / ns``
#   * ``nm.kuzu_db_path(ns)``    == ``base / ns / "graph.db"``
#   * ``nm.vector_dir(ns)``      == ``base / ns / "vectors"``
#   * ``nm.manifest_path(ns)``   == ``base / ns / "manifest.json"``
#
# The functions below remain as a convenience for the (still-correct) default
# case where ``base_dir == KNOWLEDGE_DIR``.


def namespace_dir(namespace: str) -> Path:
    """Return the on-disk directory for a namespace under :data:`KNOWLEDGE_DIR`.

    Deprecated for code that needs to respect a custom ``NamespaceManager.base_dir``;
    use ``NamespaceManager.namespace_dir(ns)`` instead.
    """
    return KNOWLEDGE_DIR / namespace


def kuzu_db_path(namespace: str) -> Path:
    """Return the Kuzu single-file DB path for a namespace.

    Deprecated for code that needs to respect a custom ``NamespaceManager.base_dir``;
    use ``NamespaceManager.kuzu_db_path(ns)`` instead.
    """
    return namespace_dir(namespace) / "graph.db"


def vector_dir(namespace: str) -> Path:
    """Return the per-namespace zvec collection directory.

    The on-disk layout is ``{KNOWLEDGE_DIR}/{namespace}/vectors/`` (was
    ``chroma/`` prior to the EPIC-003 v2 migration to zvec). Deprecated for
    code that needs to respect a custom ``NamespaceManager.base_dir``; use
    ``NamespaceManager.vector_dir(ns)`` instead.
    """
    return namespace_dir(namespace) / "vectors"


def chroma_dir(namespace: str) -> Path:
    """Deprecated alias of :func:`vector_dir`.

    Kept ONLY for backwards-compatibility with one or two test imports that
    have not been updated; new code MUST use :func:`vector_dir` (or, better,
    ``NamespaceManager.vector_dir``). This wrapper still returns the new
    ``vectors/`` path — there is no longer a ``chroma/`` directory anywhere.
    """
    return vector_dir(namespace)


def manifest_path(namespace: str) -> Path:
    """Return the manifest.json path for a namespace.

    Deprecated for code that needs to respect a custom ``NamespaceManager.base_dir``;
    use ``NamespaceManager.manifest_path(ns)`` instead.
    """
    return namespace_dir(namespace) / "manifest.json"


# --- File-type constants (moved from app.utils.constant) -------------------

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".doc",
    ".ppt",
    ".xls",
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".rtf",
}

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
}

# --- Misc -------------------------------------------------------------------

# Garbage-collection ledger file (kept for compat with storage.delete_vector_store)
GARBAGE_COLLECTION_FILE: str = str(KNOWLEDGE_DIR / "_gc.json")
