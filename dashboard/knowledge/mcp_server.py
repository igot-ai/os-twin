"""FastMCP server exposing knowledge-management tools (EPIC-006).

Mounted at ``/mcp`` in :mod:`dashboard.api`. External MCP clients
(opencode, claude-desktop, custom) can connect, list tools, and call them.

All tools return JSON-serialisable dicts. Errors come back as
``{"error": "...", "code": "..."}`` — the tool body NEVER raises an
exception, so the MCP transport always sees a well-formed response.

Lazy-import discipline: importing this module must NOT pull in
``kuzu``/``zvec``/``sentence_transformers``/``markitdown``/``anthropic``.
The :class:`KnowledgeService` is constructed on the first tool call (or
the first call to :func:`get_mcp_app`), so dashboard cold-boot stays fast.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)

# Singleton KnowledgeService — lazy-init on first tool call so module
# import stays cheap (no kuzu / zvec / sentence-transformers / markitdown /
# anthropic loaded at startup).
_service: Optional[Any] = None
_service_lock = threading.Lock()


def _get_service() -> Any:
    """Return the lazily-constructed singleton :class:`KnowledgeService`.

    Tests reset the singleton by setting ``mcp_server._service = None``
    (e.g. when changing ``OSTWIN_KNOWLEDGE_DIR`` between tests). When the
    env var is set at construction time, we build a :class:`NamespaceManager`
    rooted at that path so each test's isolated tmp dir is honoured —
    without this, the module-level ``KNOWLEDGE_DIR`` (captured once at
    import) would leak between tests.
    """
    global _service
    if _service is not None:
        return _service
    with _service_lock:
        if _service is None:
            import os as _os
            from pathlib import Path as _Path

            from dashboard.knowledge.namespace import NamespaceManager  # noqa: WPS433
            from dashboard.knowledge.service import KnowledgeService  # noqa: WPS433

            override = _os.environ.get("OSTWIN_KNOWLEDGE_DIR")
            if override:
                nm = NamespaceManager(base_dir=_Path(override))
                _service = KnowledgeService(namespace_manager=nm)
            else:
                _service = KnowledgeService()
        return _service


def _err(code: str, msg: str) -> dict:
    """Build the canonical error envelope returned by every tool on failure."""
    return {"error": msg, "code": code}


def _get_mcp_actor() -> str | None:
    """Get the current MCP actor from environment or session context.
    
    The actor is set via:
    - OSTWIN_MCP_ACTOR environment variable (set by the agent runtime)
    - Session header (for HTTP-based MCP clients)
    
    Returns None if no actor is identified (non-curator session).
    """
    import os
    return os.environ.get("OSTWIN_MCP_ACTOR")


def _requires_confirmation() -> bool:
    """Check if the current session requires confirmation for destructive ops.
    
    Returns True if OSTWIN_MCP_ACTOR is set to "knowledge-curator".
    Other actors and anonymous sessions do NOT require confirmation.
    """
    actor = _get_mcp_actor()
    return actor == "knowledge-curator"


# The FastMCP instance — module-level so the @mcp.tool() decorators run at
# import time. The instance itself is cheap (no transport / network setup
# happens until ``get_mcp_app()`` is called).
#
# ``stateless_http=True`` is critical when the streamable-HTTP app is mounted
# as a sub-app inside FastAPI (see ``dashboard/api.py``). The default mode
# uses a long-running session manager whose task group is started by the
# inner app's lifespan — which FastAPI does NOT propagate to mounted
# sub-apps. Without stateless mode, the first POST to ``/mcp/...`` crashes
# with ``RuntimeError: Task group is not initialized``. Stateless mode
# spins up a per-request transport and avoids the problem entirely. Our
# tools are pure functions with no per-session state, so this is safe.
# DNS-rebinding protection: FastMCP auto-enables it when host is the default
# 127.0.0.1, with a default allow-list of {127.0.0.1:*, localhost:*, [::1]:*}.
# This rejects requests with arbitrary Host headers (e.g. ``testserver`` from
# FastAPI's TestClient) with HTTP 421. Since we are mounted inside the
# parent FastAPI application, the parent app is the right layer to enforce
# host policy (via CORS / reverse-proxy / etc.) — pass a permissive
# transport-security settings object so the inner FastMCP transport accepts
# any Host. We still disable DNS-rebinding-protection (the default for
# ``TransportSecuritySettings`` when explicitly constructed without
# ``enable_dns_rebinding_protection=True``).
_mcp_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

# ``streamable_http_path="/"`` makes the FastMCP transport serve at the
# root of its sub-app (so the externally-reachable URL is ``/mcp/`` —
# matching the path the parent FastAPI mounts us at). The default is
# ``/mcp`` which would push the real endpoint to ``/mcp/mcp`` — confusing
# for users who follow the install snippet that just says ``/mcp``.
mcp = FastMCP(
    "ostwin-knowledge",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_mcp_transport_security,
)


# ---------------------------------------------------------------------------
# Tool: knowledge_list_namespaces
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_list_namespaces() -> dict:
    """List all knowledge namespaces with their stats.

    Returns a dict with key ``namespaces`` containing one entry per
    namespace: ``{name, created_at, updated_at, language, description,
    stats: {files_indexed, chunks, entities, relations, vectors}, imports}``.

    Use when: the user asks "what knowledge bases are available?", or to
    discover namespace ids before querying or importing.

    Example: ``knowledge_list_namespaces()``
    """
    try:
        ks = _get_service()
        items = ks.list_namespaces()
        return {"namespaces": [m.model_dump(mode="json") for m in items]}
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge_list_namespaces failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_create_namespace
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_create_namespace(
    name: str,
    language: str = "English",
    description: str = "",
) -> dict:
    """Create a new knowledge namespace.

    Args:
        name: lowercase alphanumeric + dashes/underscores, 1–64 chars.
            Must start with a letter or digit. Examples: ``project_docs``,
            ``api-reference``, ``client-handbook-2024``.
        language: human language of expected content (default ``"English"``).
            Used by the LLM during entity extraction.
        description: optional free-form description.

    Returns the created NamespaceMeta as a dict, OR
    ``{"error", "code"}`` on failure (codes: ``INVALID_NAMESPACE_ID``,
    ``NAMESPACE_EXISTS``, ``MAX_NAMESPACES_REACHED``, ``INTERNAL_ERROR``).

    Use when: starting a new knowledge base. NOT needed before
    ``knowledge_import_folder`` — that auto-creates the namespace if missing.

    Example: ``knowledge_create_namespace("project_docs", "English",
    "Internal product handbook v3")``
    """
    try:
        ks = _get_service()
        meta = ks.create_namespace(name, language=language, description=description or None, actor="anonymous")
        return meta.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import (  # noqa: WPS433
            InvalidNamespaceIdError,
            NamespaceExistsError,
        )
        from dashboard.knowledge.audit import (  # noqa: WPS433
            ImportInProgressError,
            MaxNamespacesReachedError,
        )

        if isinstance(exc, InvalidNamespaceIdError):
            return _err("INVALID_NAMESPACE_ID", str(exc))
        if isinstance(exc, NamespaceExistsError):
            return _err("NAMESPACE_EXISTS", str(exc))
        if isinstance(exc, MaxNamespacesReachedError):
            return _err("MAX_NAMESPACES_REACHED", str(exc))
        if isinstance(exc, ImportInProgressError):
            return _err("IMPORT_IN_PROGRESS", str(exc))
        logger.exception("knowledge_create_namespace failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_delete_namespace
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_delete_namespace(name: str, confirm: bool = False) -> dict:
    """Delete a knowledge namespace and all its data permanently.

    Args:
        name: Namespace to delete.
        confirm: Required when called by knowledge-curator to prevent accidental
            deletion. Must be explicitly set to True to proceed.

    Returns ``{"deleted": bool}`` — ``false`` if the namespace did not exist
    (no error), ``true`` if it was removed. On unexpected failure returns
    ``{"error", "code": "INTERNAL_ERROR"}``.

    DANGEROUS: this is irreversible. Confirm with the user before calling.

    Example: ``knowledge_delete_namespace("temp_test_kb")``
    Example (curator): ``knowledge_delete_namespace("temp_test_kb", confirm=True)``
    """
    try:
        # EPIC-006: Confirmation gate for knowledge-curator sessions
        if _requires_confirmation() and not confirm:
            return _err(
                "CONFIRMATION_REQUIRED",
                f"knowledge_delete_namespace requires confirm=True when called by knowledge-curator. "
                f"Explicitly set confirm=True to proceed with deleting namespace '{name}'."
            )
        
        ks = _get_service()
        return {"deleted": ks.delete_namespace(name, actor="anonymous")}
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge_delete_namespace failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_import_folder
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_import_folder(
    namespace: str,
    folder_path: str,
    force: bool = False,
) -> dict:
    """Import all supported files from an absolute folder path into a namespace.

    Supported file types: docx, pdf, xlsx, pptx, doc, ppt, xls, html, htm,
    txt, md, csv, json, xml, yaml, yml, rtf, png, jpg, jpeg, gif, bmp, tiff,
    webp. Image OCR uses Anthropic vision (requires ``ANTHROPIC_API_KEY`` in
    the dashboard environment); without the key, images are walked but
    skipped silently with a warning logged per file.

    Args:
        namespace: target namespace. Auto-created if it doesn't exist.
        folder_path: ABSOLUTE local filesystem path to a directory.
            Relative paths are rejected with code ``INVALID_FOLDER_PATH``.
        force: when ``True``, re-process files whose content hash already
            exists in the namespace (default: skip already-indexed files).

    Returns ``{"job_id": str, "status": "submitted", "message": str}`` on
    success, OR ``{"error", "code"}`` on failure (codes:
    ``INVALID_FOLDER_PATH``, ``FOLDER_NOT_FOUND``, ``NOT_A_DIRECTORY``,
    ``INVALID_NAMESPACE_ID``, ``IMPORT_IN_PROGRESS``, ``INTERNAL_ERROR``).

    The import runs in the background — poll
    ``knowledge_get_import_status`` with the returned ``job_id`` to track
    progress through ``pending → running → completed | failed | cancelled``.

    Example: ``knowledge_import_folder("project_docs", "/Users/me/projects/docs")``
    """
    try:
        from pathlib import Path

        p = Path(folder_path)
        if not p.is_absolute():
            return _err(
                "INVALID_FOLDER_PATH",
                f"folder_path must be absolute, got: {folder_path}",
            )
        if not p.exists():
            return _err("FOLDER_NOT_FOUND", f"folder does not exist: {folder_path}")
        if not p.is_dir():
            return _err("NOT_A_DIRECTORY", f"path is not a directory: {folder_path}")
        ks = _get_service()
        job_id = ks.import_folder(namespace, str(p), options={"force": force}, actor="anonymous")
        return {
            "job_id": job_id,
            "status": "submitted",
            "message": f"Importing {folder_path} into {namespace}",
        }
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import InvalidNamespaceIdError  # noqa: WPS433
        from dashboard.knowledge.audit import ImportInProgressError  # noqa: WPS433

        if isinstance(exc, InvalidNamespaceIdError):
            return _err("INVALID_NAMESPACE_ID", str(exc))
        if isinstance(exc, ImportInProgressError):
            return _err("IMPORT_IN_PROGRESS", str(exc))
        if isinstance(exc, FileNotFoundError):
            return _err("FOLDER_NOT_FOUND", str(exc))
        if isinstance(exc, NotADirectoryError):
            return _err("NOT_A_DIRECTORY", str(exc))
        logger.exception("knowledge_import_folder failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_get_import_status
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_get_import_status(namespace: str, job_id: str) -> dict:
    """Get the status of a knowledge import job.

    Args:
        namespace: namespace where the import was started (informational —
            kept for symmetry with the REST API; the job is looked up by
            ``job_id`` alone).
        job_id: the id returned by :func:`knowledge_import_folder`.

    Returns the JobStatus as a dict (``state``, ``progress_current``,
    ``progress_total``, ``message``, ``errors``, ``result``). ``state`` is
    one of ``pending | running | completed | failed | interrupted |
    cancelled``. On unknown job: ``{"error", "code": "JOB_NOT_FOUND"}``.

    Use after :func:`knowledge_import_folder` to poll progress.

    Example: ``knowledge_get_import_status("project_docs", "abc-123-uuid")``
    """
    try:
        ks = _get_service()
        status = ks.get_job(job_id)
        if status is None:
            return _err("JOB_NOT_FOUND", f"no job with id {job_id}")
        return status.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge_get_import_status failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_query
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_query(
    namespace: str,
    query: str,
    mode: str = "raw",
    top_k: int = 10,
) -> dict:
    """Query a knowledge namespace.

    Args:
        namespace: target namespace.
        query: natural-language question or search phrase.
        mode: one of:

            * ``"raw"`` — vector hits only (fast, no LLM).
            * ``"graph"`` — vector + graph neighbours, PageRank-reranked.
            * ``"summarized"`` — graph + LLM-aggregated answer with
              citations (slowest; requires ``ANTHROPIC_API_KEY``).

        top_k: max number of chunk hits to return (default 10).

    Returns the QueryResult dict with ``chunks``, ``entities``, optional
    ``answer``, ``citations``, ``latency_ms``, and ``warnings``. On
    namespace-missing: ``{"error", "code": "NAMESPACE_NOT_FOUND"}``. On
    invalid mode: ``{"error", "code": "BAD_REQUEST"}``.

    When ``ANTHROPIC_API_KEY`` is unset and ``mode="summarized"``, the
    response includes ``warnings: ["llm_unavailable"]`` and ``answer: null``
    but still returns chunks — never crashes.

    Use ``"raw"`` when you just need relevant snippets; ``"summarized"``
    when you want a synthesised answer with citations.

    Example: ``knowledge_query("project_docs", "How does auth work?",
    mode="summarized", top_k=5)``
    """
    try:
        ks = _get_service()
        result = ks.query(namespace, query, mode=mode, top_k=top_k, actor="anonymous")
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import NamespaceNotFoundError  # noqa: WPS433

        if isinstance(exc, NamespaceNotFoundError):
            return _err("NAMESPACE_NOT_FOUND", str(exc))
        if isinstance(exc, ValueError):
            return _err("BAD_REQUEST", str(exc))
        logger.exception("knowledge_query failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_get_graph
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_get_graph(namespace: str, limit: int = 100) -> dict:
    """Get the entity-relation graph for a namespace (for visualisation).

    Args:
        namespace: target namespace.
        limit: max number of nodes to return (default 100). Edges are
            filtered to those whose endpoints are in the returned node set.

    Returns ``{"nodes": [...], "edges": [...], "stats": {"node_count":
    N, "edge_count": M}}``. Empty namespace OR no LLM available during
    ingest → empty ``nodes`` / ``edges`` (not an error).

    On namespace-missing: ``{"error", "code": "NAMESPACE_NOT_FOUND"}``.

    Example: ``knowledge_get_graph("project_docs", limit=200)``
    """
    try:
        ks = _get_service()
        return ks.get_graph(namespace, limit=limit, actor="anonymous")
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import NamespaceNotFoundError  # noqa: WPS433

        if isinstance(exc, NamespaceNotFoundError):
            return _err("NAMESPACE_NOT_FOUND", str(exc))
        logger.exception("knowledge_get_graph failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_backup_namespace (EPIC-004)
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_backup_namespace(name: str) -> dict:
    """Create a backup archive of a knowledge namespace.

    Args:
        name: namespace to backup.

    Returns ``{"archive_path": str, "size_bytes": int, "compression": str}``
    on success, OR ``{"error", "code"}`` on failure (codes:
    ``NAMESPACE_NOT_FOUND``, ``INTERNAL_ERROR``).

    The archive is created in the default backup location (typically
    the current working directory). Use the returned path to download
    or transfer the backup.

    Example: ``knowledge_backup_namespace("project_docs")``
    """
    try:
        from pathlib import Path
        from dashboard.knowledge.backup import backup_namespace as do_backup
        
        ks = _get_service()
        
        # Verify namespace exists
        meta = ks.get_namespace(name)
        if meta is None:
            return _err("NAMESPACE_NOT_FOUND", f"Namespace {name!r} not found")
        
        archive_path = do_backup(name, namespace_manager=ks._nm)  # noqa: SLF001
        
        return {
            "archive_path": str(archive_path),
            "size_bytes": archive_path.stat().st_size,
            "compression": "zstd" if str(archive_path).endswith(".zst") else "gzip",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge_backup_namespace failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_restore_namespace (EPIC-004)
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_restore_namespace(
    archive_path: str,
    as_name: Optional[str] = None,
    overwrite: bool = False,
    confirm: bool = False,
) -> dict:
    """Restore a knowledge namespace from a backup archive.

    Args:
        archive_path: absolute path to the backup archive file.
        as_name: optional target namespace name (defaults to archive's
            original namespace name).
        overwrite: if True, allows overwriting an existing namespace
            (default: False).
        confirm: Required when overwrite=True and called by knowledge-curator.
            Must be explicitly set to True to proceed with overwrite.

    Returns the restored NamespaceMeta as a dict, OR ``{"error", "code"}``
    on failure (codes: ``NAMESPACE_EXISTS``, ``INVALID_BACKUP_ARCHIVE``,
    ``BACKUP_CHECKSUM_MISMATCH``, ``INTERNAL_ERROR``).

    DANGEROUS: with overwrite=True, existing namespace data is permanently
    deleted. Confirm with the user before setting overwrite=True.

    Example: ``knowledge_restore_namespace("/backups/docs.tar.zst")``
    Example (curator with overwrite): ``knowledge_restore_namespace("/backups/docs.tar.zst", overwrite=True, confirm=True)``
    """
    try:
        from pathlib import Path
        from dashboard.knowledge.backup import (
            restore_namespace as do_restore,
            BackupError,
            BackupChecksumMismatchError,
            InvalidBackupArchiveError,
            NamespaceBackupNotFoundError,
        )
        
        # EPIC-006: Confirmation gate for knowledge-curator sessions
        if overwrite and _requires_confirmation() and not confirm:
            return _err(
                "CONFIRMATION_REQUIRED",
                f"knowledge_restore_namespace with overwrite=True requires confirm=True when called by knowledge-curator. "
                f"Explicitly set confirm=True to proceed with overwriting the namespace."
            )
        
        ks = _get_service()
        p = Path(archive_path)
        
        if not p.is_absolute():
            return _err("INVALID_PATH", f"archive_path must be absolute, got: {archive_path}")
        if not p.exists():
            return _err("FILE_NOT_FOUND", f"Archive not found: {archive_path}")
        
        meta = do_restore(
            p,
            name=as_name,
            namespace_manager=ks._nm,  # noqa: SLF001
            knowledge_service=ks,
            overwrite=overwrite,
        )
        return meta.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import NamespaceExistsError  # noqa: WPS433
        from dashboard.knowledge.backup import (
            BackupChecksumMismatchError,
            InvalidBackupArchiveError,
        )
        
        if isinstance(exc, NamespaceExistsError):
            return _err("NAMESPACE_EXISTS", str(exc))
        if isinstance(exc, BackupChecksumMismatchError):
            return _err("BACKUP_CHECKSUM_MISMATCH", str(exc))
        if isinstance(exc, InvalidBackupArchiveError):
            return _err("INVALID_BACKUP_ARCHIVE", str(exc))
        logger.exception("knowledge_restore_namespace failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: knowledge_refresh_namespace (EPIC-004)
# ---------------------------------------------------------------------------


@mcp.tool()
def knowledge_refresh_namespace(name: str) -> dict:
    """Refresh a namespace by re-importing all source folders.

    Triggers a new import job for each completed import in the namespace's
    history. Useful when source files have been updated and you want to
    re-index them.

    Args:
        name: namespace to refresh.

    Returns ``{"job_ids": [...], "imports_count": N}`` on success, OR
    ``{"error", "code": "NAMESPACE_NOT_FOUND"}`` if the namespace doesn't
    exist.

    Example: ``knowledge_refresh_namespace("project_docs")``
    """
    try:
        ks = _get_service()
        
        # Get namespace
        meta = ks.get_namespace(name)
        if meta is None:
            return _err("NAMESPACE_NOT_FOUND", f"Namespace {name!r} not found")
        
        # Get imports to refresh
        imports = meta.imports
        if not imports:
            return {"job_ids": [], "imports_count": 0}
        
        # Trigger re-import for each completed folder
        job_ids = []
        for imp in imports:
            if imp.status != "completed":
                continue
            try:
                job_id = ks.import_folder(
                    name,
                    imp.folder_path,
                    {"force": True},
                    actor="anonymous",
                )
                job_ids.append(job_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh import %s: %s", imp.folder_path, exc)
        
        return {"job_ids": job_ids, "imports_count": len(job_ids)}
    except Exception as exc:  # noqa: BLE001
        from dashboard.knowledge.namespace import NamespaceNotFoundError  # noqa: WPS433
        
        if isinstance(exc, NamespaceNotFoundError):
            return _err("NAMESPACE_NOT_FOUND", str(exc))
        logger.exception("knowledge_refresh_namespace failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# Tool: find_notes_by_knowledge_link (EPIC-007)
# ---------------------------------------------------------------------------


@mcp.tool()
def find_notes_by_knowledge_link(
    namespace: str,
    file_hash: str,
    chunk_idx: Optional[int] = None,
) -> dict:
    """Find memory notes that link to a specific knowledge chunk.

    This is part of the Memory ↔ Knowledge Bridge (EPIC-007) that enables
    bidirectional linking between memory notes and knowledge chunks.

    Args:
        namespace: The knowledge namespace to search.
        file_hash: SHA256 hash of the source file.
        chunk_idx: Optional chunk index. If provided, returns notes that link
            to this specific chunk. If None, returns notes that link to ANY
            chunk in the file.

    Returns:
        ``{"note_ids": [...], "count": N}`` on success, OR
        ``{"error", "code": "BRIDGE_DISABLED"}`` if the bridge is not enabled,
        OR ``{"error", "code": "INTERNAL_ERROR"}`` on other failures.

    Example:
        # Find notes linking to a specific chunk
        ``find_notes_by_knowledge_link("docs", "abc123def456", 0)``

        # Find notes linking to any chunk in a file
        ``find_notes_by_knowledge_link("docs", "abc123def456")``
    """
    try:
        from dashboard.knowledge.bridge import (
            BridgeIndex,
            BridgeConfig,
            is_bridge_enabled,
        )
        
        if not is_bridge_enabled():
            return _err(
                "BRIDGE_DISABLED",
                "Memory-Knowledge bridge is not enabled. "
                "Set OSTWIN_KNOWLEDGE_MEMORY_BRIDGE=1 to enable.",
            )
        
        # Create bridge index instance
        config = BridgeConfig.from_env()
        bridge = BridgeIndex(config=config)
        
        # Perform lookup
        note_ids = bridge.lookup(namespace, file_hash, chunk_idx)
        
        # Close the bridge connection
        bridge.close()
        
        return {
            "note_ids": note_ids,
            "count": len(note_ids),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("find_notes_by_knowledge_link failed")
        return _err("INTERNAL_ERROR", str(exc))


# ---------------------------------------------------------------------------
# ASGI app helper
# ---------------------------------------------------------------------------


def get_mcp_app() -> Any:
    """Return the ASGI app for mounting in ``dashboard/api.py``.

    Tries the modern ``streamable_http_app()`` first (mcp[cli] >= 1.1.x),
    falling back to ``sse_app()`` for older releases. The exact attribute
    name has shifted across mcp[cli] versions, so isolating the choice
    here keeps :mod:`dashboard.api` decoupled.

    Note: the underlying ``StreamableHTTPSessionManager`` may only run
    once per instance — if you need a brand-new MCP app (e.g. across
    successive ``TestClient(app)`` contexts inside one process), call
    :func:`reset_mcp_session_manager` first to drop the spent session
    manager so the next ``streamable_http_app()`` creates a fresh one.
    """
    if hasattr(mcp, "streamable_http_app"):
        return mcp.streamable_http_app()
    if hasattr(mcp, "sse_app"):
        return mcp.sse_app()
    raise RuntimeError(
        f"FastMCP instance has no known ASGI mount method; available: {dir(mcp)}"
    )


def reset_mcp_session_manager() -> None:
    """Drop the FastMCP ``_session_manager`` so the next ASGI app gets a fresh one.

    Required between successive ``TestClient(app)`` lifespan cycles in the
    same process — :class:`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
    is single-use and raises ``RuntimeError`` on a second ``run()`` call.

    Production (single uvicorn run) never needs this — the lifespan runs
    exactly once. The function is a no-op if the session manager has not
    been created yet.
    """
    if getattr(mcp, "_session_manager", None) is not None:
        mcp._session_manager = None  # type: ignore[attr-defined]


__all__ = [
    "mcp",
    "get_mcp_app",
    "knowledge_list_namespaces",
    "knowledge_create_namespace",
    "knowledge_delete_namespace",
    "knowledge_import_folder",
    "knowledge_get_import_status",
    "knowledge_query",
    "knowledge_get_graph",
    # EPIC-004
    "knowledge_backup_namespace",
    "knowledge_restore_namespace",
    "knowledge_refresh_namespace",
    # EPIC-007
    "find_notes_by_knowledge_link",
]
