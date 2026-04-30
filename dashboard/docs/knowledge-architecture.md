# Knowledge System Architecture

This document describes the internal architecture of the Knowledge system for contributors extending or maintaining it.

## Module Layout

```
dashboard/knowledge/
├── __init__.py           # Public API exports
├── config.py             # Configuration and constants
├── namespace.py          # NamespaceMeta, NamespaceManager
├── service.py            # KnowledgeService (main orchestration)
├── ingestion.py          # Document ingestion pipeline
├── jobs.py               # Job status tracking
├── query.py              # Query engine (3 modes)
├── vector_store.py       # Zvec vector storage
├── embeddings.py         # Embedding generation
├── llm.py                # LLM integration for entity extraction
├── graph/                # Graph database integration
│   ├── __init__.py
│   └── index/
│       └── kuzudb.py     # Kuzu graph database
├── mcp_server.py         # MCP server implementation
├── metrics.py            # Prometheus metrics
├── backup.py             # Backup/restore
├── audit.py              # Audit logging and policies
├── stats.py              # Namespace statistics
├── retention.py          # Retention policy handling
├── bridge.py             # Memory ↔ Knowledge bridge
└── knowledge_link.py     # URI parsing for bridge links
```

## Data Flow

### Ingestion Flow

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│   Folder    │────▶│   Ingestion    │────▶│  Chunking       │
│   Import    │     │   Pipeline     │     │  (Recursive)    │
└─────────────┘     └────────────────┘     └─────────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│   Update    │◀────│    Store       │◀────│   Embedding     │
│   Manifest  │     │   Vectors      │     │   Generation    │
└─────────────┘     └────────────────┘     └─────────────────┘
       │
       ▼
┌─────────────┐     ┌────────────────┐
│   Entity    │────▶│   Graph DB     │
│   Extract   │     │   (Kuzu)       │
└─────────────┘     └────────────────┘
```

### Query Flow

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│   Query     │────▶│   Vector       │────▶│   Similarity    │
│   Text      │     │   Embedding    │     │   Search        │
└─────────────┘     └────────────────┘     └─────────────────┘
                                                   │
                           ┌───────────────────────┤
                           │                       │
                           ▼                       ▼
                    ┌─────────────┐        ┌─────────────────┐
                    │   Raw       │        │   Graph         │
                    │   Mode      │        │   Expansion     │
                    └─────────────┘        └─────────────────┘
                                                   │
                                                   ▼
                                            ┌─────────────────┐
                                            │   LLM Answer    │
                                            │   (Summarized)  │
                                            └─────────────────┘
```

## Key Components

### KnowledgeService

The main orchestration class in `service.py`. Handles:
- Namespace lifecycle
- Import job submission
- Query dispatch
- Graph and vector store access

```python
class KnowledgeService:
    def __init__(self, knowledge_dir: Path | None = None): ...

    def create_namespace(self, name: str, ...) -> NamespaceMeta: ...
    def import_folder(self, namespace: str, folder_path: str, ...) -> str: ...
    def query(self, namespace: str, query: str, mode: str, ...) -> QueryResult: ...
```

### NamespaceManager

Manages namespace metadata in `namespace.py`:
- Manifest file I/O
- Schema versioning
- Namespace validation

Each namespace stores:
```
~/.ostwin/knowledge/{namespace}/
├── manifest.json       # Namespace metadata
├── graph.kuzu/         # Kuzu graph database
├── vectors.zvec/       # Vector store
└── imports/            # Imported file cache
```

### Ingestion Pipeline

`ingestion.py` contains the document processing pipeline:
1. **File Discovery** — Recursive walk, filter by extension
2. **Content Extraction** — Markdown, HTML, JSON, plain text
3. **Chunking** — Split into semantic units (paragraphs, sections)
4. **Embedding** — Generate vectors via `embeddings.py`
5. **Entity Extraction** — LLM-based entity/relationship detection
6. **Graph Population** — Insert into Kuzu
7. **Vector Indexing** — Insert into Zvec

### Query Engine

`query.py` implements three query modes:

**Raw Mode** (`mode="raw"`):
- Vector similarity search only
- Returns chunks with scores

**Graph Mode** (`mode="graph"`):
- Vector search + graph expansion
- PageRank for entity ranking
- Returns chunks + entities

**Summarized Mode** (`mode="summarized"`):
- Graph mode + LLM synthesis
- Generates natural language answer
- Returns chunks + entities + answer + citations

### Vector Store

`vector_store.py` wraps Zvec for:
- Embedding storage
- Similarity search
- Metadata filtering

### Graph Database

`graph/index/kuzudb.py` wraps Kuzu for:
- Entity storage
- Relationship queries
- Graph traversal

### MCP Server

`mcp_server.py` implements the MCP protocol:
- Tool registration
- Request handling
- Error mapping

## Architecture Decision Records (ADRs)

### ADR-001: Namespace Isolation

Each namespace is a self-contained knowledge base with its own:
- Vector store
- Graph database
- Import history

**Rationale**: Allows independent backup/restore, quota management, and multi-tenant scenarios.

### ADR-002: Lazy Loading

Heavy dependencies (kuzu, sentence-transformers, anthropic) are imported lazily:
- Import at function call time, not module load
- `try/except ImportError` patterns
- Graceful degradation when missing

**Rationale**: Fast startup, reduced memory for minimal deployments.

### ADR-003: Background Import

Import runs in a background thread:
- Job status tracking via `jobs.py`
- Polling for completion
- Error collection without crashing

**Rationale**: Imports can take minutes; HTTP requests shouldn't block.

### ADR-004: Three Query Modes

Raw → Graph → Summarized progression:
- Each mode adds capabilities
- Higher modes have more dependencies
- User chooses based on needs

**Rationale**: Flexibility for different use cases and resource levels.

### ADR-005: Zvec for Vectors

Using Zvec (custom vector store) instead of Chroma/Pinecone:
- Single binary dependency
- No external services
- File-based persistence

**Rationale**: Simplicity for local development, single-process deployment.

### ADR-006: Kuzu for Graphs

Using Kuzu (embedded graph database):
- Cypher-like query language
- ACID transactions
- No separate server process

**Rationale**: Simplicity, embeddable, powerful queries.

### ADR-007: BGE Embeddings

Using BAAI/bge-small-en-v1.5 by default:
- 384-dimensional vectors
- Good performance/size tradeoff
- Sentence-transformers compatible

**Rationale**: Balance of quality and efficiency for semantic search.

### ADR-008: Backup as Compressed Archives

Using tar.zst for backups:
- High compression ratio
- Fast decompression
- Single file for portability

**Rationale**: Simplicity, cross-platform, streaming support.

## Extension Points

### Adding a New Document Parser

1. Add parsing logic in `ingestion.py`
2. Extend file extension filter
3. Test with fixture documents

### Adding a New Query Mode

1. Implement in `query.py` as new method
2. Add to mode enum validation
3. Update MCP tool description
4. Document in user guide

### Adding a New MCP Tool

1. Implement as async function in `mcp_server.py`
2. Register with `@mcp.tool()` decorator
3. Add error handling with structured error codes
4. Update test coverage

### Adding a New Metric

1. Define in `metrics.py` with counter/histogram/gauge
2. Increment in relevant service methods
3. Export via `/api/knowledge/metrics` endpoint

## Testing

### Test Structure

```
dashboard/tests/
├── test_knowledge_api.py           # REST API tests
├── test_knowledge_e2e_rest.py      # E2E lifecycle (REST)
├── test_knowledge_e2e_mcp.py       # E2E lifecycle (MCP)
├── test_knowledge_namespace.py     # Namespace management
├── test_knowledge_ingestion.py     # Import pipeline
├── test_knowledge_query.py         # Query modes
├── test_knowledge_backup.py        # Backup/restore
├── test_knowledge_metrics.py       # Metrics
├── test_knowledge_health.py        # Health checks
└── fixtures/
    └── knowledge_sample/           # Test documents
```

### Running Tests

```bash
# All knowledge tests
pytest dashboard/tests/test_knowledge*.py

# Fast tests only (skip slow E2E)
pytest dashboard/tests/test_knowledge*.py -m "not slow"

# With coverage
pytest dashboard/tests/test_knowledge*.py --cov=dashboard/knowledge
```

## Dependencies

### Required
- `fastapi` — REST API framework
- `pydantic` — Data validation
- `zvec-store` — Vector database

### Optional
- `kuzu` — Graph database (required for graph mode)
- `sentence-transformers` — Embedding generation
- `anthropic` — LLM for entity extraction and summarized mode

## Performance Considerations

### Embedding Batch Size
- Default: 32 documents per batch
- Tune via `OSTWIN_EMBEDDING_BATCH_SIZE`

### Graph Query Depth
- Default: 2-hop expansion
- Controlled per-query via `depth` parameter

### Vector Index
- Zvec uses HNSW algorithm
- Tunable via `ef_construction`, `M` parameters

### Memory Usage
- Peak memory during import: ~2GB for 1000 documents
- Streaming processing for large files
- Lazy loading reduces idle memory
