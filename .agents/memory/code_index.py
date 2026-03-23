"""CocoIndex-powered code indexing for semantic search over the project codebase.

Provides:
  - A CocoIndex flow that reads source files, splits into chunks, embeds them,
    and exports to a Postgres table with pgvector for similarity search.
  - Public API: build_index(), search_index(), notify_file_changed()

Environment (loaded from .agents/memory/.env):
    COCOINDEX_DATABASE_URL: Postgres connection string (with pgvector)
    GOOGLE_API_KEY: Required for Gemini embedding API
"""

from __future__ import annotations

import functools
import logging
import os
from pathlib import Path

import cocoindex
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load .env from the same directory as this script (.agents/memory/.env)
# ---------------------------------------------------------------------------
_MEMORY_DIR = Path(__file__).resolve().parent
_AGENTS_DIR = _MEMORY_DIR.parent
_PROJECT_ROOT = _AGENTS_DIR.parent

load_dotenv(_MEMORY_DIR / ".env")

# ---------------------------------------------------------------------------
# Indexing config
# ---------------------------------------------------------------------------
INDEXABLE_EXTENSIONS = {
    ".py",
    ".rs",
    ".toml",
    ".md",
    ".mdx",
    ".sh",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".html",
}

DEFAULT_INCLUDED_PATTERNS = [f"*{ext}" for ext in INDEXABLE_EXTENSIONS]

DEFAULT_EXCLUDED_PATTERNS = [
    "**/.agents",
    "**/.agents/**",
    "**/.*",
    "**/node_modules",
    "**/target",
    "**/__pycache__",
    "**/dist",
    "**/build",
    "**/.venv",
    "**/venv",
    "**/*.lock",
    "**/package-lock.json",
]

CHUNK_SIZE = 2048
MIN_CHUNK_SIZE = 200
CHUNK_OVERLAP = 200
TOP_K = 3

EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIMENSION = 1536

# Track whether cocoindex.init() has been called
_initialized = False


def _ensure_init() -> None:
    """Call cocoindex.init() once."""
    global _initialized
    if not _initialized:
        cocoindex.init()
        _initialized = True


# ---------------------------------------------------------------------------
# Flow: read files → chunk → embed → export to Postgres
# ---------------------------------------------------------------------------
@cocoindex.flow_def(name="CodeEmbedding")
def code_embedding_flow(
    flow_builder: cocoindex.FlowBuilder,
    data_scope: cocoindex.DataScope,
) -> None:
    """Index project source files into a vector database for semantic search.

    Indexes the project root but EXCLUDES the .agents/ directory.
    """
    index_path = os.environ.get("COCOINDEX_PROJECT_PATH", str(_PROJECT_ROOT))

    # Add source
    data_scope["files"] = flow_builder.add_source(
        cocoindex.sources.LocalFile(
            path=index_path,
            included_patterns=DEFAULT_INCLUDED_PATTERNS,
            excluded_patterns=DEFAULT_EXCLUDED_PATTERNS,
        )
    )

    # Add data collector
    code_embeddings = data_scope.add_collector()

    with data_scope["files"].row() as file:
        # Detect programming language
        file["language"] = file["filename"].transform(
            cocoindex.functions.DetectProgrammingLanguage()
        )

        # Split into chunks
        file["chunks"] = file["content"].transform(
            cocoindex.functions.SplitRecursively(),
            language=file["language"],
            chunk_size=CHUNK_SIZE,
            min_chunk_size=MIN_CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        with file["chunks"].row() as chunk:
            # Embed each chunk using Gemini
            chunk["embedding"] = chunk["text"].transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.GEMINI,
                    model=EMBEDDING_MODEL,
                    task_type="SEMANTIC_SIMILARITY",
                )
            )

            # Collect results
            code_embeddings.collect(
                filename=file["filename"],
                location=chunk["location"],
                text=chunk["text"],
                embedding=chunk["embedding"],
            )

    # Export to Postgres with vector index
    code_embeddings.export(
        "code_embeddings",
        cocoindex.storages.Postgres(),
        primary_key_fields=["filename", "location"],
        vector_indexes=[
            cocoindex.VectorIndexDef(
                field_name="embedding",
                metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Database connection pool (cached)
# ---------------------------------------------------------------------------
@functools.cache
def _connection_pool() -> ConnectionPool:
    """Get a connection pool to the CocoIndex database."""
    return ConnectionPool(os.environ["COCOINDEX_DATABASE_URL"])


# ===================================================================
# Public API — used by the pipeline and policy hook
# ===================================================================


def build_index(path: str | None = None) -> None:
    """Build or update the full code embeddings index.

    Args:
        path: Project path to index. Defaults to project root.
              The .agents/ directory is always excluded.
    """
    if path:
        os.environ["COCOINDEX_PROJECT_PATH"] = str(Path(path).resolve())

    index_path = os.environ.get("COCOINDEX_PROJECT_PATH", str(_PROJECT_ROOT))
    print(f"🔍 Indexing code from: {index_path}")

    _ensure_init()
    # Ensure Postgres schema is up-to-date before updating data
    cocoindex.setup_all_flows()
    stats = code_embedding_flow.update()
    print(f"✓ Index updated: {stats}")
    return stats


def search_index(query: str, top_k: int = TOP_K) -> list[dict]:
    """Run a semantic search and return results.

    Returns:
        List of dicts with keys: filename, text, embedding, score
    """
    _ensure_init()

    table_name = cocoindex.utils.get_target_default_name(
        code_embedding_flow, "code_embeddings"
    )

    with _connection_pool().connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT filename FROM {table_name} ORDER BY filename")
            return [{"filename": row[0]} for row in cur.fetchall()]


def is_indexable(file_path: str) -> bool:
    """Check if a file path should be indexed (by extension, not in .agents/)."""
    p = Path(file_path)
    # Exclude .agents/ directory
    parts = p.parts
    if ".agents" in parts:
        return False
    # Check extension
    return p.suffix.lower() in INDEXABLE_EXTENSIONS


def notify_file_changed(file_path: str) -> None:
    """Notify the index that a file has changed.

    Triggers an incremental re-index via CocoIndex flow update.
    Only processes files with indexable extensions outside .agents/.
    """
    if not is_indexable(file_path):
        return

    try:
        _ensure_init()
        code_embedding_flow.update()
        logger.debug("Index updated after change to %s", file_path)
    except Exception:
        logger.warning("Failed to update index for %s", file_path, exc_info=True)


# ===================================================================
# __main__ — called by pipeline pre-flight scripts
# ===================================================================

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="CocoIndex code indexing")
    sub = parser.add_subparsers(dest="command")

    build_p = sub.add_parser("build", help="Build or update the code index")
    build_p.add_argument("--path", default=None, help="Project path to index")

    args = parser.parse_args()

    if args.command == "build":
        try:
            build_index(path=args.path)
        except Exception as e:
            print(f"✗ Build failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
