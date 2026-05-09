#!/usr/bin/env python3
"""Global Knowledge MCP Server — provides cross-namespace knowledge access for the manager role.

This MCP server gives the manager agent read-only access to knowledge bases
across ALL namespaces in the Ostwin system, enabling it to:

1. Query documentation and reference materials
2. Search across all imported knowledge bases
3. Find relevant information regardless of namespace
4. Monitor knowledge ingestion progress

Mounted at: /api/global-knowledge/mcp (remote MCP over HTTP)
Tools provided: global_knowledge_query, global_knowledge_list_namespaces,
                global_knowledge_search_all, global_knowledge_get_stats

The manager can use this to answer questions like:
- "What documentation exists about our API?"
- "What knowledge bases are available?"
- "Search all docs for 'authentication'"
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _ostwin_home() -> Path:
    configured = os.environ.get("OSTWIN_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".ostwin"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KNOWLEDGE_BASE_DIR: Path = Path(
    os.environ.get("OSTWIN_KNOWLEDGE_DIR", str(_ostwin_home() / "knowledge"))
)

# ---------------------------------------------------------------------------
# Lazy-loaded knowledge service
# ---------------------------------------------------------------------------
_knowledge_service = None
_knowledge_lock = threading.Lock()


def _get_knowledge_service() -> Any:
    """Lazily load and return the KnowledgeService singleton."""
    global _knowledge_service
    
    if _knowledge_service is not None:
        return _knowledge_service
    
    with _knowledge_lock:
        if _knowledge_service is None:
            try:
                # Add dashboard to path
                dashboard_path = Path(__file__).resolve().parent.parent.parent / "dashboard"
                if dashboard_path.is_dir() and str(dashboard_path) not in sys.path:
                    sys.path.insert(0, str(dashboard_path.parent))
                
                from dashboard.knowledge.namespace import NamespaceManager
                from dashboard.knowledge.service import KnowledgeService
                
                if KNOWLEDGE_BASE_DIR.is_dir():
                    nm = NamespaceManager(base_dir=KNOWLEDGE_BASE_DIR)
                    _knowledge_service = KnowledgeService(namespace_manager=nm)
                else:
                    _knowledge_service = KnowledgeService()
                
                logger.info("Knowledge service initialized")
            except Exception as e:
                logger.exception("Failed to initialize knowledge service")
                raise RuntimeError(f"Failed to initialize knowledge service: {e}")
        
        return _knowledge_service


# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "ostwin-global-knowledge",
    instructions="""You have READ-ONLY access to the global knowledge system that contains
all imported documentation and reference materials across ALL namespaces.

Use this to:

1. Query documentation and technical references
2. Search across all knowledge bases at once
3. Find relevant information regardless of which namespace it's in
4. Discover what knowledge bases exist

This is a READ-ONLY view. To import new documents, use the knowledge-curator
tools or the dashboard API.

Query modes:
- "raw": Fast vector search only
- "graph": Vector + graph neighbors for context
- "summarized": LLM-aggregated answer with citations

Query examples:
- "How does the authentication flow work?"
- "What are the database schema conventions?"
- "Explain the deployment process"
- "What APIs are available for user management?"
""",
)


@mcp.tool()
def global_knowledge_list_namespaces() -> str:
    """List all knowledge namespaces with their stats.

    Returns information about each namespace including file counts,
    chunk counts, and entity counts.

    Returns:
        JSON array of namespace metadata.
    """
    try:
        ks = _get_knowledge_service()
        namespaces = ks.list_namespaces()
        return json.dumps(
            {"namespaces": [m.model_dump(mode="json") for m in namespaces]},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("global_knowledge_list_namespaces failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def global_knowledge_query(
    query: str,
    mode: str = "raw",
    top_k: int = 10,
    namespaces: Optional[list[str]] = None,
) -> str:
    """Query knowledge bases across ALL namespaces.

    Searches across all knowledge bases and aggregates results, or
    searches specific namespaces if provided.

    Args:
        query: Natural language question or search phrase.
        mode: Query mode - "raw" (fast), "graph" (with neighbors), 
              "summarized" (LLM-aggregated with citations).
        top_k: Max results per namespace (default 10).
        namespaces: Optional list of specific namespaces to search.
                   If None, searches all namespaces.

    Returns:
        JSON with chunks, entities, and optional answer/citations.
    """
    logger.info("global_knowledge_query: query=%r mode=%s top_k=%d", query, mode, top_k)
    
    try:
        ks = _get_knowledge_service()
        
        # Get namespaces to search
        if namespaces:
            ns_to_search = namespaces
        else:
            all_ns = ks.list_namespaces()
            ns_to_search = [ns.name for ns in all_ns]
        
        # Aggregate results
        all_chunks = []
        all_entities = []
        aggregated_answer = None
        warnings = []
        
        for ns_name in ns_to_search:
            try:
                result = ks.query(ns_name, query, mode=mode, top_k=top_k, actor="manager")
                
                # Add namespace context to chunks
                for chunk in result.chunks:
                    chunk_dict = chunk.model_dump(mode="json") if hasattr(chunk, 'model_dump') else dict(chunk)
                    chunk_dict["namespace"] = ns_name
                    all_chunks.append(chunk_dict)
                
                # Collect entities
                for entity in (result.entities or []):
                    entity_dict = entity.model_dump(mode="json") if hasattr(entity, 'model_dump') else dict(entity)
                    entity_dict["namespace"] = ns_name
                    all_entities.append(entity_dict)
                
                # Use first summarized answer if available
                if result.answer and not aggregated_answer:
                    aggregated_answer = result.answer
                
                if result.warnings:
                    warnings.extend(result.warnings)
                    
            except Exception as e:
                logger.warning("Failed to query namespace %s: %s", ns_name, e)
                warnings.append(f"namespace_{ns_name}_error: {str(e)}")
        
        # Sort chunks by score
        all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
        
        return json.dumps({
            "query": query,
            "mode": mode,
            "namespaces_searched": ns_to_search,
            "chunks": all_chunks[:top_k * 2],  # Return more since aggregated
            "entities": all_entities[:50],
            "answer": aggregated_answer,
            "warnings": warnings if warnings else None,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.exception("global_knowledge_query failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def global_knowledge_search_all(query: str, top_k: int = 5) -> str:
    """Fast vector search across ALL namespaces.

    A simplified query that searches all namespaces with raw mode
    (vector search only, no LLM), returning the most relevant chunks.

    Args:
        query: Natural language search query.
        top_k: Max results per namespace (default 5).

    Returns:
        JSON array of matching chunks with namespace context.
    """
    return global_knowledge_query(query, mode="raw", top_k=top_k)


@mcp.tool()
def global_knowledge_get_stats() -> str:
    """Get aggregate statistics about all knowledge bases.

    Returns total files, chunks, entities, and vectors across all namespaces.

    Returns:
        JSON with per-namespace and aggregate statistics.
    """
    try:
        ks = _get_knowledge_service()
        namespaces = ks.list_namespaces()
        
        stats = {
            "knowledge_base_dir": str(KNOWLEDGE_BASE_DIR),
            "namespaces": [],
            "aggregate": {
                "total_files": 0,
                "total_chunks": 0,
                "total_entities": 0,
                "total_vectors": 0,
                "namespace_count": len(namespaces),
            }
        }
        
        for ns in namespaces:
            ns_dict = ns.model_dump(mode="json")
            ns_stats = ns_dict.get("stats", {})
            
            stats["namespaces"].append({
                "name": ns.name,
                "files_indexed": ns_stats.get("files_indexed", 0),
                "chunks": ns_stats.get("chunks", 0),
                "entities": ns_stats.get("entities", 0),
                "vectors": ns_stats.get("vectors", 0),
                "language": ns_dict.get("language"),
                "description": ns_dict.get("description"),
            })
            
            stats["aggregate"]["total_files"] += ns_stats.get("files_indexed", 0)
            stats["aggregate"]["total_chunks"] += ns_stats.get("chunks", 0)
            stats["aggregate"]["total_entities"] += ns_stats.get("entities", 0)
            stats["aggregate"]["total_vectors"] += ns_stats.get("vectors", 0)
        
        return json.dumps(stats, ensure_ascii=False)
        
    except Exception as e:
        logger.exception("global_knowledge_get_stats failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def global_knowledge_get_namespace(namespace: str) -> str:
    """Get detailed information about a specific namespace.

    Args:
        namespace: The namespace name to query.

    Returns:
        JSON with namespace metadata, stats, and import history.
    """
    try:
        ks = _get_knowledge_service()
        namespaces = ks.list_namespaces()
        
        for ns in namespaces:
            if ns.name == namespace:
                return json.dumps(ns.model_dump(mode="json"), ensure_ascii=False)
        
        return json.dumps({"error": f"Namespace '{namespace}' not found"}, ensure_ascii=False)
        
    except Exception as e:
        logger.exception("global_knowledge_get_namespace failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def global_knowledge_find_relevant(query: str, top_k: int = 3) -> str:
    """Find the most relevant namespace for a query.

    Searches each namespace with the query and returns which namespaces
    have the most relevant content.

    Args:
        query: Natural language query.
        top_k: Results per namespace for scoring.

    Returns:
        JSON with ranked namespaces by relevance score.
    """
    try:
        ks = _get_knowledge_service()
        namespaces = ks.list_namespaces()
        
        ns_scores = []
        
        for ns in namespaces:
            try:
                result = ks.query(ns.name, query, mode="raw", top_k=top_k, actor="manager")
                
                if result.chunks:
                    # Calculate average score
                    avg_score = sum(
                        c.score if hasattr(c, 'score') else 0 
                        for c in result.chunks
                    ) / len(result.chunks)
                    max_score = max(
                        c.score if hasattr(c, 'score') else 0 
                        for c in result.chunks
                    )
                    
                    ns_scores.append({
                        "namespace": ns.name,
                        "avg_score": round(avg_score, 4),
                        "max_score": round(max_score, 4),
                        "chunk_count": len(result.chunks),
                    })
            except Exception as e:
                logger.debug("Failed to score namespace %s: %s", ns.name, e)
        
        # Sort by max score, then avg score
        ns_scores.sort(key=lambda x: (x["max_score"], x["avg_score"]), reverse=True)
        
        return json.dumps({
            "query": query,
            "ranked_namespaces": ns_scores,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.exception("global_knowledge_find_relevant failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport: stdio (default) or sse",
    )
    parser.add_argument("--port", type=int, default=6471)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
